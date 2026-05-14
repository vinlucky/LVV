import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import FILE_DIR
from ..database import update_file_conv_id
from ..services.file_service import save_upload_file, get_download_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


class UpdateConvIdRequest(BaseModel):
    files: list[dict]
    conv_id: str
    mode: str = "general"


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    mode: str = Form("chat"),
    conv_id: str | None = Form(None),
    subdir: str | None = Form(None),
):
    file_info = await save_upload_file(file, conv_id, mode)
    return file_info


@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    normalized = file_path.replace("\\", "/")
    path = get_download_path(normalized)
    if path.exists():
        return FileResponse(str(path), filename=path.name)
    for candidate in [
        FILE_DIR / normalized,
        FILE_DIR / normalized.replace("file/", ""),
    ]:
        if candidate.exists():
            return FileResponse(str(candidate), filename=candidate.name)
    name_only = Path(normalized).name
    matches = list(FILE_DIR.rglob(name_only))
    if len(matches) == 1:
        return FileResponse(str(matches[0]), filename=matches[0].name)
    if len(matches) > 1:
        best = None
        for m in matches:
            if normalized in str(m).replace("\\", "/"):
                best = m
                break
        if best:
            return FileResponse(str(best), filename=best.name)
        return FileResponse(str(matches[0]), filename=matches[0].name)
    raise HTTPException(404, f"File not found: {file_path}")


@router.post("/update-conv-id")
async def update_files_conv_id(req: UpdateConvIdRequest):
    updated_files = []
    for f in req.files:
        filename = f.get("stored_filename") or f.get("filename", "")
        if filename:
            updated = update_file_conv_id(filename, req.conv_id)
            if updated:
                updated_files.append({
                    "filename": updated["filename"],
                    "stored_filename": updated["stored_filename"],
                    "file_path": updated["file_path"],
                    "relative_path": str(Path(updated["file_path"]).relative_to(FILE_DIR.parent)).replace("\\", "/") if updated["file_path"] else "",
                    "conv_id": updated["conv_id"],
                })
    return {"files": updated_files}