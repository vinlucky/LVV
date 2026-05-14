import json
import logging
import asyncio
from openai import OpenAI
from ..config import get_fallback_chain, get_provider_config, get_api_key, get_base_url, get_settings, load_models_config, FILE_DIR

logger = logging.getLogger(__name__)

_settings = get_settings()
MAX_FALLBACK_RETRIES = _settings.get("max_fallback_retries", 5)
REQUEST_TIMEOUT = _settings.get("request_timeout", 120)
TEMPERATURE_ACTOR = _settings.get("temperature_actor", 0.7)
TEMPERATURE_CRITIC = _settings.get("temperature_critic", 0.3)
ACTOR_CRITIC_MAX_ITER = _settings.get("actor_critic_max_iterations", 3)


def _get_client_for_model(model_name: str):
    config = load_models_config()
    for provider_id, provider_cfg in config.get("providers", {}).items():
        models = provider_cfg.get("models", [])
        if model_name in models:
            api_key = get_api_key(provider_id)
            base_url = get_base_url(provider_id)
            return OpenAI(api_key=api_key, base_url=base_url, timeout=REQUEST_TIMEOUT), provider_id, model_name
    api_key = get_api_key("qwen")
    base_url = get_base_url("qwen")
    return OpenAI(api_key=api_key, base_url=base_url, timeout=REQUEST_TIMEOUT), "qwen", model_name


def _try_completion_with_model(model_name: str, messages: list, temperature: float = 0.7,
                                max_tokens: int = 4096, stream: bool = False):
    client, provider_id, actual_model = _get_client_for_model(model_name)
    return client.chat.completions.create(
        model=actual_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
    ), provider_id, actual_model


def _get_fallback_models(chain_name: str) -> list[str]:
    chain = get_fallback_chain(chain_name)
    if not chain:
        chain = get_fallback_chain("actor")
    models = chain.get("models", [])
    if not models:
        config = load_models_config()
        all_models = config.get("providers", {}).get("qwen", {}).get("models", [])
        return all_models[:MAX_FALLBACK_RETRIES]
    return models[:MAX_FALLBACK_RETRIES]


def chat_completion_with_fallback(chain_name: str, system_prompt: str, user_message: str,
                                   temperature: float | None = None) -> dict:
    if temperature is None:
        temperature = TEMPERATURE_ACTOR if chain_name == "actor" else TEMPERATURE_CRITIC

    api_key = get_api_key("qwen")
    if not api_key:
        return {
            "success": False,
            "content": "API Key 未配置！请在 .env 文件中设置 QWEN_API_KEY。\n获取 API Key: https://dashscope.console.aliyun.com/apiKey",
            "model": "",
            "provider": "",
            "chain": chain_name,
            "error": "QWEN_API_KEY is empty",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    models = _get_fallback_models(chain_name)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    last_error = None
    for model_name in models:
        try:
            logger.info(f"[{chain_name}] Trying model: {model_name}")
            response, provider_id, actual_model = _try_completion_with_model(
                model_name, messages, temperature=temperature
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            return {
                "success": True,
                "content": content,
                "model": actual_model,
                "provider": provider_id,
                "chain": chain_name,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                },
            }
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[{chain_name}] Model {model_name} failed: {last_error}")
            continue

    return {
        "success": False,
        "content": "",
        "model": "",
        "provider": "",
        "chain": chain_name,
        "error": last_error or "All models in fallback chain failed",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def chat_completion_stream_with_fallback(chain_name: str, system_prompt: str, user_message: str,
                                                temperature: float | None = None):
    if temperature is None:
        temperature = TEMPERATURE_ACTOR if chain_name == "actor" else TEMPERATURE_CRITIC

    api_key = get_api_key("qwen")
    if not api_key:
        yield {
            "type": "error",
            "error": "API Key 未配置！请在 .env 文件中设置 QWEN_API_KEY。获取 API Key: https://dashscope.console.aliyun.com/apiKey",
            "chain": chain_name,
        }
        return

    models = _get_fallback_models(chain_name)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    last_error = None
    for model_name in models:
        try:
            logger.info(f"[{chain_name}] Streaming with model: {model_name}")
            client, provider_id, actual_model = _get_client_for_model(model_name)
            stream = client.chat.completions.create(
                model=actual_model,
                messages=messages,
                temperature=temperature,
                max_tokens=16384,
                stream=True,
            )
            yield {
                "type": "model_info",
                "model": actual_model,
                "provider": provider_id,
                "chain": chain_name,
            }
            full_content = ""
            loop = asyncio.get_event_loop()
            chunk_queue: asyncio.Queue = asyncio.Queue()
            stream_done = False

            def _drain_stream():
                nonlocal stream_done
                try:
                    for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            loop.call_soon_threadsafe(chunk_queue.put_nowait, content)
                finally:
                    stream_done = True
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

            import threading
            drain_thread = threading.Thread(target=_drain_stream, daemon=True)
            drain_thread.start()

            while True:
                content = await chunk_queue.get()
                if content is None:
                    break
                full_content += content
                yield {"type": "chunk", "content": content}

            drain_thread.join(timeout=5)
            yield {"type": "done", "full_content": full_content, "model": actual_model, "provider": provider_id}
            return
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[{chain_name}] Model {model_name} streaming failed: {last_error}")
            yield {"type": "model_switch", "from_model": model_name, "to_chain": chain_name, "error": last_error}
            continue

    yield {"type": "error", "error": last_error or "All streaming models failed", "chain": chain_name}


def get_available_providers() -> list[dict]:
    config = load_models_config()
    providers = []
    for pid, pcfg in config.get("providers", {}).items():
        api_key = get_api_key(pid)
        masked = ''
        if api_key:
            if len(api_key) > 8:
                masked = api_key[:6] + '****' + api_key[-4:]
            else:
                masked = '****'
        providers.append({
            "id": pid,
            "name": pcfg.get("name", pid),
            "description": pcfg.get("description", ""),
            "available": bool(api_key),
            "has_api_key": bool(api_key),
            "masked_api_key": masked,
            "model_count": len(pcfg.get("models", [])),
            "model_counts": {
                "llm": len([m for m in pcfg.get("models", []) if not any(m.lower().startswith(p) for p in ('qwen-vl', 'gpt-4o', 'claude-3', 'gemini-2.0-flash', 'hunyuan-', 'vision'))]),
                "omni": len([m for m in pcfg.get("models", []) if any(m.lower().startswith(p) for p in ('qwen-vl', 'gpt-4o', 'claude-3', 'gemini-2.0-flash', 'hunyuan-', 'vision'))]),
                "embedding": len([m for m in pcfg.get("models", []) if 'embed' in m.lower()]),
            },
        })
    return providers


def get_models_for_provider(provider: str) -> list[str]:
    provider_cfg = get_provider_config(provider)
    return provider_cfg.get("models", [])


def get_all_models() -> list[dict]:
    config = load_models_config()
    result = []
    for pid, pcfg in config.get("providers", {}).items():
        for model in pcfg.get("models", []):
            result.append({"provider": pid, "model": model})
    return result


def get_task_model_map() -> dict:
    return {
        "chat": _get_fallback_models("actor")[0] if _get_fallback_models("actor") else "",
        "meeting": _get_fallback_models("actor")[0] if _get_fallback_models("actor") else "",
        "literature": _get_fallback_models("actor")[0] if _get_fallback_models("actor") else "",
        "polish": _get_fallback_models("actor")[0] if _get_fallback_models("actor") else "",
        "ppt": _get_fallback_models("actor")[0] if _get_fallback_models("actor") else "",
    }


def _get_vision_models() -> list[str]:
    chain = get_fallback_chain("vision")
    if chain:
        models = chain.get("models", [])
        if models:
            return models[:MAX_FALLBACK_RETRIES]
    return ["qwen3-vl-plus", "qwen3-vl-flash", "qwen-vl-max"]


def vision_ocr_with_fallback(image_b64: str, page_num: int = 1, total_pages: int = 1) -> str:
    models = _get_vision_models()
    if not models:
        logger.warning("[vision_ocr] No vision models configured")
        return ""

    api_key = get_api_key("qwen")
    if not api_key:
        logger.warning("[vision_ocr] API Key not configured")
        return ""

    for model_name in models:
        try:
            logger.info(f"[vision_ocr] Processing page {page_num}/{total_pages} with model: {model_name}")
            client, provider_id, actual_model = _get_client_for_model(model_name)
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": "请将这张图片中的所有文字完整提取出来，保持原始格式和排版。只输出提取的文字，不要添加任何说明。"},
                ],
            }]

            response = client.chat.completions.create(
                model=actual_model,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
            )

            content = response.choices[0].message.content or ""
            if content.strip():
                return content
        except Exception as e:
            logger.warning(f"[vision_ocr] Model {model_name} failed for page {page_num}: {e}")
            continue

    return ""


def _get_omni_models() -> list[str]:
    chain = get_fallback_chain("all_modal")
    if chain:
        models = chain.get("models", [])
        if models:
            return models[:MAX_FALLBACK_RETRIES]
    return ["qwen3.5-omni-plus", "qwen-omni-turbo", "qwen3-omni-flash"]


MAX_AUDIO_SIZE_BYTES = 45 * 1024 * 1024
SEGMENT_DURATION_SECONDS = 600


def _get_ffmpeg_path() -> str | None:
    import shutil
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return None


def _convert_audio_to_wav(input_path: str, output_path: str) -> bool:
    import subprocess
    ffmpeg = _get_ffmpeg_path()
    if not ffmpeg:
        logger.warning("[omni] FFmpeg not found (neither system nor imageio-ffmpeg)")
        return False
    try:
        subprocess.run(
            [ffmpeg, "-i", input_path, "-ar", "16000", "-ac", "1", "-y", output_path],
            capture_output=True, timeout=300,
        )
        return True
    except Exception as e:
        logger.warning(f"[omni] FFmpeg conversion failed: {e}")
        return False


def _split_wav_with_wave(file_path: str, segment_duration: int = SEGMENT_DURATION_SECONDS) -> list[str]:
    import wave
    import tempfile
    from pathlib import Path

    try:
        with wave.open(file_path, "rb") as wf:
            params = wf.getparams()
            framerate = params.framerate
            nchannels = params.nchannels
            sampwidth = params.sampwidth
            nframes = params.nframes
            frames_per_segment = framerate * segment_duration

            if nframes <= frames_per_segment:
                return [file_path]

            tmp_dir = str(Path(FILE_DIR) / "tmp" / f"omni_split_{id(file_path)}")
            Path(tmp_dir).mkdir(parents=True, exist_ok=True)
            segments = []
            offset = 0
            seg_idx = 0

            while offset < nframes:
                remaining = nframes - offset
                current_frames = min(frames_per_segment, remaining)
                seg_path = str(Path(tmp_dir) / f"segment_{seg_idx:03d}.wav")

                with wave.open(seg_path, "wb") as seg_wf:
                    seg_wf.setnchannels(nchannels)
                    seg_wf.setsampwidth(sampwidth)
                    seg_wf.setframerate(framerate)
                    wf.setpos(offset)
                    data = wf.readframes(current_frames)
                    seg_wf.writeframes(data)

                segments.append(seg_path)
                offset += current_frames
                seg_idx += 1

        logger.info(f"[omni] Split WAV into {len(segments)} segments using wave module")
        return segments
    except Exception as e:
        logger.warning(f"[omni] Wave split failed: {e}")
        return [file_path]


def _split_audio_with_ffmpeg(file_path: str, segment_duration: int = SEGMENT_DURATION_SECONDS) -> list[str]:
    import subprocess
    import tempfile
    from pathlib import Path

    ffmpeg = _get_ffmpeg_path()
    if not ffmpeg:
        return _split_wav_with_wave(file_path, segment_duration)

    tmp_dir = str(Path(FILE_DIR) / "tmp" / f"omni_split_{id(file_path)}")
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    output_pattern = str(Path(tmp_dir) / "segment_%03d.wav")

    try:
        subprocess.run(
            [
                ffmpeg, "-i", file_path,
                "-ar", "16000", "-ac", "1",
                "-f", "segment", "-segment_time", str(segment_duration),
                "-y", output_pattern,
            ],
            capture_output=True, timeout=600,
        )
    except Exception as e:
        logger.warning(f"[omni] FFmpeg split failed: {e}")
        return _split_wav_with_wave(file_path, segment_duration)

    segments = sorted(Path(tmp_dir).glob("segment_*.wav"))
    if not segments:
        logger.warning("[omni] No segments produced, trying wave module")
        return _split_wav_with_wave(file_path, segment_duration)

    logger.info(f"[omni] Split audio into {len(segments)} segments")
    return [str(s) for s in segments]


async def _transcribe_single_audio(audio_data_b64: str, ext: str, language: str, models: list[str]) -> str:
    last_error = None
    for model_name in models:
        try:
            client, provider_id, actual_model = _get_client_for_model(model_name)
            messages = [{
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": f"data:audio/{ext};base64,{audio_data_b64}", "format": ext}},
                    {"type": "text", "text": "请将这段音频完整转写为文字。只输出转写文本，不要添加任何说明。"},
                ],
            }]

            stream = client.chat.completions.create(
                model=actual_model,
                messages=messages,
                modalities=["text"],
                temperature=0.1,
                max_tokens=8192,
                stream=True,
            )

            full_content = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    full_content += chunk.choices[0].delta.content
            return full_content
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[omni] Model {model_name} failed for segment: {last_error}")
            continue

    raise RuntimeError(last_error or "All omni models failed")


async def omni_transcribe_and_stream(file_path: str, language: str = "zh"):
    import base64
    import tempfile
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        yield {"type": "error", "error": f"File not found: {file_path}"}
        return

    ext = path.suffix.lower().lstrip(".")
    supported_formats = {"mp3", "wav", "flac", "ogg", "m4a", "aac", "3gp", "3gpp", "amr"}
    converted_path = None
    need_split = False

    file_size = path.stat().st_size
    file_size_mb = file_size / 1024 / 1024
    logger.info(f"[omni] Processing audio: {file_path}, size={file_size_mb:.1f}MB, format={ext}")

    if file_size > MAX_AUDIO_SIZE_BYTES:
        need_split = True
        logger.info(f"[omni] File size {file_size_mb:.1f}MB exceeds {MAX_AUDIO_SIZE_BYTES / 1024 / 1024:.0f}MB limit, will split into {SEGMENT_DURATION_SECONDS}s segments")

    if ext not in supported_formats or need_split:
        tmp_dir = Path(FILE_DIR) / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        converted_path = str(tmp_dir / f"omni_convert_{id(path)}.wav")
        if _convert_audio_to_wav(str(path), converted_path):
            path = Path(converted_path)
            ext = "wav"
            logger.info(f"[omni] Converted audio to WAV: {converted_path}")
        else:
            logger.warning("[omni] Conversion failed, trying original format")
            need_split = False
            try:
                Path(converted_path).unlink()
            except Exception:
                pass
            converted_path = None

    if need_split and path.exists():
        segment_paths = _split_audio_with_ffmpeg(str(path), SEGMENT_DURATION_SECONDS)
    else:
        segment_paths = [str(path)]

    api_key = get_api_key("qwen")
    if not api_key:
        yield {"type": "error", "error": "API Key 未配置"}
        return

    models = _get_omni_models()
    if not models:
        yield {"type": "error", "error": "No omni models configured"}
        return

    is_multi_segment = len(segment_paths) > 1
    if is_multi_segment:
        yield {"type": "step", "message": f"音频文件较大，已分割为 {len(segment_paths)} 段进行转写..."}

    last_error = None
    all_transcripts = []
    for seg_idx, seg_path in enumerate(segment_paths):
        seg_path_obj = Path(seg_path)
        if not seg_path_obj.exists():
            logger.warning(f"[omni] Segment file not found: {seg_path}")
            continue

        seg_data = base64.b64encode(seg_path_obj.read_bytes()).decode("utf-8")

        if is_multi_segment:
            yield {"type": "step", "message": f"正在转写第 {seg_idx + 1}/{len(segment_paths)} 段..."}

        for model_name in models:
            try:
                logger.info(f"[omni] Transcribing segment {seg_idx + 1}/{len(segment_paths)} with model: {model_name}")
                client, provider_id, actual_model = _get_client_for_model(model_name)

                messages = [{
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"data": f"data:audio/{ext};base64,{seg_data}", "format": ext}},
                        {"type": "text", "text": "请将这段音频完整转写为文字。只输出转写文本，不要添加任何说明。"},
                    ],
                }]

                stream = client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    modalities=["text"],
                    temperature=0.1,
                    max_tokens=8192,
                    stream=True,
                )

                if seg_idx == 0 and not is_multi_segment:
                    yield {"type": "model_info", "model": actual_model, "provider": provider_id, "chain": "all_modal"}

                full_content = ""
                loop = asyncio.get_event_loop()
                chunk_queue: asyncio.Queue = asyncio.Queue()

                def _drain():
                    try:
                        for chunk in stream:
                            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk.choices[0].delta.content)
                    finally:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

                import threading
                t = threading.Thread(target=_drain, daemon=True)
                t.start()

                while True:
                    content = await chunk_queue.get()
                    if content is None:
                        break
                    full_content += content
                    yield {"type": "transcript_chunk", "content": content}

                t.join(timeout=5)
                all_transcripts.append(full_content)
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[omni] Model {model_name} failed for segment {seg_idx}: {last_error}")
                yield {"type": "model_switch", "from_model": model_name, "to_chain": "all_modal", "error": last_error}
                continue
        else:
            all_transcripts.append(f"[第{seg_idx + 1}段转写失败]")

        if seg_path != str(path) and seg_path != file_path:
            try:
                Path(seg_path).unlink()
            except Exception:
                pass

    if converted_path:
        try:
            Path(converted_path).unlink()
        except Exception:
            pass
        tmp_dir = Path(converted_path).parent
        for leftover in tmp_dir.glob("segment_*.wav"):
            try:
                leftover.unlink()
            except Exception:
                pass

    final_transcript = "\n\n".join(all_transcripts)
    if not final_transcript.strip() or all(t.startswith("[第") and t.endswith("转写失败]") for t in all_transcripts):
        yield {"type": "all_modal_failed", "error": last_error or "All omni models failed", "message": "全模态模型转写失败，将降级使用 Whisper 转写"}
        return

    yield {"type": "transcript_done", "full_content": final_transcript, "model": models[0], "provider": "qwen"}