import json
import logging
import re
from pathlib import Path

from ..config import FILE_DIR
from ..database import save_file_record, get_files_by_conv, add_message
from ..services.mode_detector import detect_auto_file_type

logger = logging.getLogger(__name__)


def read_ref_files(ref_files: list[dict] | None) -> str | None:
    if not ref_files:
        return None
    from .file_service import read_text_file
    parts = []
    for f in ref_files:
        fp = f.get("file_path", "")
        fn = f.get("filename", "")
        if fp:
            try:
                content = read_text_file(fp)
                parts.append(f"=== 文件: {fn} ===\n{content}")
            except Exception as e:
                logger.warning(f"Failed to read ref file {fn}: {e}")
    return "\n\n".join(parts) if parts else None


def try_auto_generate_file(output: str, user_message: str, conv_id: str | None, mode: str) -> dict | None:
    auto_file_type = detect_auto_file_type(user_message)
    if not auto_file_type:
        return None

    outline = None
    try:
        json_match = re.search(r'\{[\s\S]*"title"[\s\S]*\}', output)
        if json_match:
            outline = json.loads(json_match.group())
    except Exception:
        pass

    if not outline:
        return None

    file_path = None
    if auto_file_type == "xlsx":
        from ..routes.xlsx import _generate_xlsx_from_outline
        file_path = _generate_xlsx_from_outline(outline, conv_id)
    elif auto_file_type == "docx":
        from ..routes.docx import _generate_docx_from_outline
        file_path = _generate_docx_from_outline(outline, conv_id)

    if not file_path:
        return None

    file_info = {
        "filename": file_path.name,
        "file_name": file_path.stem,
        "file_path": str(file_path),
        "relative_path": str(file_path.relative_to(FILE_DIR.parent)),
        "file_format": auto_file_type,
        "file_size": file_path.stat().st_size if file_path.exists() else 0,
        "conv_id": conv_id,
        "download_url": f"/files/download/{str(file_path.relative_to(FILE_DIR.parent)).replace(chr(92), '/')}",
    }
    save_file_record(
        filename=file_path.name,
        stored_filename=file_path.name,
        file_path=str(file_path),
        file_format=auto_file_type,
        file_size=file_path.stat().st_size if file_path.exists() else 0,
        conv_id=conv_id,
        mode=mode,
        is_generated=True,
    )
    if conv_id:
        conv_files = get_files_by_conv(conv_id)
        add_message(conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))
    return file_info


def get_auto_file_system_prompt(user_message: str) -> str | None:
    auto_file_type = detect_auto_file_type(user_message)
    if auto_file_type == "xlsx":
        from ..routes.xlsx import XLSX_SYSTEM_PROMPT
        return XLSX_SYSTEM_PROMPT
    elif auto_file_type == "docx":
        from ..routes.docx import DOCX_SYSTEM_PROMPT
        return DOCX_SYSTEM_PROMPT
    return None
