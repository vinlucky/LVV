import os
import logging
import tempfile
import asyncio
from pathlib import Path
from fastapi import UploadFile

from ..config import FILE_DIR

logger = logging.getLogger(__name__)

_whisper_model = None
_whisper_model_name = "base"


def _get_whisper_model(model_name: str = "base"):
    global _whisper_model, _whisper_model_name
    if _whisper_model is None or _whisper_model_name != model_name:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(model_name, device="cpu", compute_type="int8")
            _whisper_model_name = model_name
            logger.info(f"Whisper model '{model_name}' loaded")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            _whisper_model = None
    return _whisper_model


async def transcribe_audio_file(file: UploadFile, language: str = "zh") -> dict:
    model = _get_whisper_model()
    if model is None:
        return {"success": False, "text": "", "error": "Whisper model not available. Install faster-whisper: pip install faster-whisper"}

    suffix = Path(file.filename).suffix if file.filename else ".wav"
    tmp_dir = Path(FILE_DIR) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = str(tmp_dir / f"whisper_{id(file)}{suffix}")
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        def _do_transcribe():
            segments, info = model.transcribe(tmp_path, language=language if language != "auto" else None)
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text)
            full_text = " ".join(text_parts).strip()
            return {
                "success": True,
                "text": full_text,
                "language": info.language,
                "duration": info.duration,
            }

        result = await asyncio.to_thread(_do_transcribe)
        return result
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return {"success": False, "text": "", "error": str(e)}
    finally:
        try:
            os.close(tmp_fd)
            os.unlink(tmp_path)
        except Exception:
            pass


async def transcribe_audio_path(file_path: str, language: str = "zh") -> dict:
    model = _get_whisper_model()
    if model is None:
        return {"success": False, "text": "", "error": "Whisper model not available. Install faster-whisper: pip install faster-whisper"}

    path = Path(file_path)
    if not path.is_absolute():
        path = FILE_DIR.parent / file_path

    if not path.exists():
        return {"success": False, "text": "", "error": f"File not found: {file_path}"}

    def _do_transcribe():
        segments, info = model.transcribe(str(path), language=language if language != "auto" else None)
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)
        full_text = " ".join(text_parts).strip()
        return {
            "success": True,
            "text": full_text,
            "language": info.language,
            "duration": info.duration,
        }

    try:
        return await asyncio.to_thread(_do_transcribe)
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return {"success": False, "text": "", "error": str(e)}