import json
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import add_message, get_files_by_conv, get_conversation, update_conversation_title, create_task, update_task
from ..services.actor_critic import run_actor_critic_stream
from ..services.file_service import save_upload_file, save_generated_file, read_text_file, extract_audio_from_video
from ..services.whisper_service import transcribe_audio_file, transcribe_audio_path
from ..services.mode_detector import detect_mode_suggestion
from ..services.auto_file_service import try_auto_generate_file
from ..services.tool_registry import get_tools_for_mode
from ..services.llm_service import omni_transcribe_and_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["meeting"])

MEETING_SYSTEM_PROMPT = """你是一个专业的会议纪要 AI。请根据提供的会议文本生成结构化的会议纪要。

输出格式：
1. **会议主题**
2. **参会人员**
3. **会议时间**
4. **关键讨论点**
5. **决议事项**
6. **待办事项**（含负责人和截止时间）
7. **下次会议安排**

请用 Markdown 格式输出专业、清晰的会议纪要。"""


class MinutesRequest(BaseModel):
    transcript: str
    language: str = "zh"
    model_override: str | None = None
    conv_id: str | None = None
    mode: str = "meeting"
    skip_thinking: bool = False
    output_format: str = "md"


class SaveMinutesRequest(BaseModel):
    content: str
    conv_id: str | None = None
    mode: str = "meeting"


@router.post("/minutes/stream")
async def meeting_minutes_stream(req: MinutesRequest):
    async def generate():
        try:
            if req.conv_id:
                task_info = create_task("meeting", req.transcript[:200])
                conv = get_conversation(req.conv_id)
                user_msg_count = len([m for m in conv.get("messages", []) if m["role"] == "user"]) if conv else 0
            suggestion = detect_mode_suggestion(req.transcript, "meeting")
            if suggestion:
                yield f"data: {json.dumps(suggestion, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            prompt = req.transcript
            if req.language == "bilingual":
                prompt = f"[要求: 中英双语对照]\n\n{req.transcript}"

            react_tools = get_tools_for_mode("meeting")
            enable_react = False
            logger.info(f"[meeting] ReAct disabled (no file upload), tools: {[t['function']['name'] for t in react_tools]}")

            minutes_file = None
            async for event in run_actor_critic_stream(
                user_message=prompt,
                system_prompt_override=MEETING_SYSTEM_PROMPT,
                conv_id=req.conv_id,
                mode="meeting",
                skip_thinking=req.skip_thinking,
                actor_chain="actor",
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "actor_done" and event.get("title") and req.conv_id:
                    try:
                        update_conversation_title(req.conv_id, event["title"], mode="meeting")
                        event["title_generated"] = True
                    except Exception:
                        pass
                if event.get("type") == "complete":
                    output = event.get("output", "")
                    if req.conv_id:
                        add_message(req.conv_id, "actor", output)
                    try:
                        update_task(task_info["task_id"], "completed", output[:500])
                    except Exception:
                        pass
                    auto_file = try_auto_generate_file(output, req.transcript, req.conv_id, "meeting")
                    if auto_file:
                        event["file"] = auto_file
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': auto_file}, ensure_ascii=False)}\n\n"
                    if not auto_file:
                        minutes_file = save_generated_file(
                            content=output,
                            filename="会议纪要",
                            file_format=req.output_format if req.output_format in ("docx", "xlsx") else "md",
                            conv_id=req.conv_id,
                            mode="meeting",
                        )
                        event["file"] = minutes_file
                        if req.conv_id:
                            conv_files = get_files_by_conv(req.conv_id)
                            add_message(req.conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': minutes_file}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Meeting stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    language: str = Form("zh"),
    mode: str = Form("meeting"),
    conv_id: str | None = Form(None),
):
    file_info = await save_upload_file(file, conv_id, mode)
    result = await transcribe_audio_path(file_info["file_path"], language)
    if result["success"]:
        file_info["transcript"] = result["text"]
        file_info["language"] = result["language"]
    else:
        file_info["transcript"] = ""
        file_info["error"] = result.get("error", "")
    return file_info


@router.post("/audio/stream")
async def meeting_audio_stream(
    file: UploadFile = File(None),
    language: str = Form("zh"),
    conv_id: str | None = Form(None),
    skip_thinking: bool = Form(False),
    file_path: str = Form(""),
    output_format: str = Form("md"),
):
    if file:
        file_info = await save_upload_file(file, conv_id, "meeting")
        audio_path = file_info["file_path"]
    elif file_path:
        audio_path = file_path
    else:
        return {"type": "error", "message": "No file or file_path provided"}

    from pathlib import Path as _Path
    audio_path_obj = _Path(audio_path)
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".3gp"}
    if audio_path_obj.suffix.lower() in video_exts:
        logger.info(f"[meeting] Detected video file: {audio_path_obj.name}, extracting audio...")
        extracted_audio = extract_audio_from_video(audio_path)
        if extracted_audio:
            audio_path = extracted_audio
            audio_path_obj = _Path(audio_path)
            logger.info(f"[meeting] Using extracted audio: {audio_path}")
        else:
            logger.warning(f"[meeting] Video audio extraction failed, will try direct processing")

    audio_file_size = audio_path_obj.stat().st_size if audio_path_obj.exists() else 0
    audio_file_size_mb = audio_file_size / 1024 / 1024
    logger.info(f"[meeting] Audio stream request: file_size={audio_file_size_mb:.1f}MB, path={audio_path}")

    async def generate():
        try:
            if audio_file_size_mb > 45:
                yield f"data: {json.dumps({'type': 'step', 'message': f'音频文件较大（{audio_file_size_mb:.1f}MB），将进行分割转写...'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'step', 'message': f'正在使用全模态模型转写音频（{audio_file_size_mb:.1f}MB）...'}, ensure_ascii=False)}\n\n"

            transcript_text = ""
            omni_failed = False
            async for event in omni_transcribe_and_stream(audio_path, language):
                if event["type"] == "transcript_chunk":
                    yield f"data: {json.dumps({'type': 'stream', 'role': 'transcript', 'content': event['content']}, ensure_ascii=False)}\n\n"
                    transcript_text += event["content"]
                elif event["type"] == "transcript_done":
                    transcript_text = event["full_content"]
                    yield f"data: {json.dumps({'type': 'transcript_done', 'transcript': transcript_text}, ensure_ascii=False)}\n\n"
                elif event["type"] == "model_switch":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif event["type"] == "all_modal_failed":
                    omni_failed = True
                    logger.warning(f"[meeting] All modal models failed: {event.get('error')}, falling back to Whisper")
                    yield f"data: {json.dumps({'type': 'step', 'message': '全模态模型转写失败，降级使用 Whisper 转写...'}, ensure_ascii=False)}\n\n"
                    break
                elif event["type"] == "error":
                    omni_failed = True
                    logger.warning(f"[meeting] Omni transcription error: {event.get('error')}, falling back to Whisper")
                    yield f"data: {json.dumps({'type': 'step', 'message': '全模态转写出错，降级使用 Whisper 转写...'}, ensure_ascii=False)}\n\n"
                    break

            if omni_failed or not transcript_text:
                try:
                    logger.info("[meeting] Using Whisper for transcription fallback")
                    yield f"data: {json.dumps({'type': 'step', 'message': '正在使用 Whisper 转写音频...'}, ensure_ascii=False)}\n\n"
                    whisper_result = await transcribe_audio_path(audio_path, language)
                    if whisper_result.get("success") and whisper_result.get("text"):
                        transcript_text = whisper_result["text"]
                        logger.info(f"[meeting] Whisper transcription successful, length={len(transcript_text)}")
                        yield f"data: {json.dumps({'type': 'stream', 'role': 'transcript', 'content': transcript_text}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'transcript_done', 'transcript': transcript_text, 'method': 'whisper'}, ensure_ascii=False)}\n\n"
                    else:
                        error_msg = whisper_result.get("error", "Whisper 转写失败")
                        logger.error(f"[meeting] Whisper fallback also failed: {error_msg}")
                        yield f"data: {json.dumps({'type': 'error', 'message': f'音频转写失败：全模态模型和 Whisper 均无法转写。{error_msg}'}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                except Exception as whisper_err:
                    logger.error(f"[meeting] Whisper fallback exception: {whisper_err}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Whisper 降级转写异常：{str(whisper_err)}'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            if not transcript_text:
                yield f"data: {json.dumps({'type': 'error', 'message': '音频转写失败，未获取到文本'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            yield f"data: {json.dumps({'type': 'step', 'message': '转写完成，正在生成会议纪要...'}, ensure_ascii=False)}\n\n"

            if conv_id:
                task_info = create_task("meeting", transcript_text[:200])
            prompt = transcript_text
            if language == "bilingual":
                prompt = f"[要求: 中英双语对照]\n\n{transcript_text}"

            actor_chain = "actor" if omni_failed else "all_modal"
            if omni_failed:
                logger.info("[meeting] Using LLM actor chain (Whisper fallback path)")
                yield f"data: {json.dumps({'type': 'step', 'message': '使用大语言模型生成会议纪要...'}, ensure_ascii=False)}\n\n"

            react_tools = get_tools_for_mode("meeting")
            enable_react = False
            logger.info(f"[meeting] ReAct disabled (no file upload), tools: {[t['function']['name'] for t in react_tools]}")

            minutes_file = None
            async for event in run_actor_critic_stream(
                user_message=prompt,
                system_prompt_override=MEETING_SYSTEM_PROMPT,
                conv_id=conv_id,
                mode="meeting",
                skip_thinking=skip_thinking,
                actor_chain=actor_chain,
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "actor_done" and event.get("title") and conv_id:
                    try:
                        update_conversation_title(conv_id, event["title"], mode="meeting")
                        event["title_generated"] = True
                    except Exception:
                        pass
                if event.get("type") == "complete":
                    output = event.get("output", "")
                    if conv_id:
                        add_message(conv_id, "actor", output)
                    try:
                        update_task(task_info["task_id"], "completed", output[:500])
                    except Exception:
                        pass
                    auto_file = try_auto_generate_file(output, transcript_text, conv_id, "meeting")
                    if auto_file:
                        event["file"] = auto_file
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': auto_file}, ensure_ascii=False)}\n\n"
                    if not auto_file:
                        minutes_file = save_generated_file(
                            content=output,
                            filename="会议纪要",
                            file_format=output_format if output_format in ("docx", "xlsx") else "md",
                            conv_id=conv_id,
                            mode="meeting",
                        )
                        event["file"] = minutes_file
                        if conv_id:
                            conv_files = get_files_by_conv(conv_id)
                            add_message(conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': minutes_file}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Meeting audio stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/transcribe-sync")
async def transcribe_sync(
    file: UploadFile = File(...),
    language: str = Form("zh"),
    mode: str = Form("meeting"),
    conv_id: str | None = Form(None),
):
    file_info = await save_upload_file(file, conv_id, mode)
    result = await transcribe_audio_path(file_info["file_path"], language)
    if result["success"]:
        file_info["transcript"] = result["text"]
        file_info["language"] = result["language"]
    else:
        raise HTTPException(500, f"Transcription failed: {result.get('error', 'unknown')}")
    return file_info


@router.post("/save-minutes")
async def save_minutes(req: SaveMinutesRequest):
    return save_generated_file(
        content=req.content,
        filename="会议纪要",
        file_format="md",
        conv_id=req.conv_id,
        mode=req.mode,
    )


@router.post("/minutes")
async def meeting_minutes_sync(req: MinutesRequest):
    from ..services.llm_service import chat_completion_with_fallback

    prompt = req.transcript
    if req.language == "bilingual":
        prompt = f"[要求: 中英双语对照]\n\n{req.transcript}"

    result = chat_completion_with_fallback(
        chain_name="actor",
        system_prompt=MEETING_SYSTEM_PROMPT,
        user_message=prompt,
    )

    output = result.get("content", "")
    if req.conv_id:
        add_message(req.conv_id, "actor", output)

    minutes_file = save_generated_file(
        content=output,
        filename="会议纪要",
        file_format="md",
        conv_id=req.conv_id,
        mode="meeting",
    )

    return {
        "output": output,
        "model": result.get("model", ""),
        "file": minutes_file,
    }