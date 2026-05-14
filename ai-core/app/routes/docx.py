import json
import logging
import subprocess
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import FILE_DIR
from ..database import add_message, get_files_by_conv, update_conversation_title, create_task, update_task
from ..services.actor_critic import run_actor_critic_stream
from ..services.file_service import save_generated_file, _get_conv_dir
from ..services.mode_detector import detect_mode_suggestion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/docx", tags=["docx"])

DOCX_RENDERER_DIR = Path(__file__).resolve().parent.parent.parent / "docx-renderer"
DOCX_RENDERER_SCRIPT = DOCX_RENDERER_DIR / "render.js"

DOCX_SYSTEM_PROMPT = """你是一个专业的 Word 文档生成 AI。请根据用户提供的主题和内容，生成结构化的 Word 文档数据。

输出格式（JSON）：
{
  "title": "文档标题",
  "subtitle": "副标题（可选）",
  "author": "作者",
  "date": "日期",
  "sections": [
    {
      "heading": "章节标题",
      "level": 1,
      "paragraphs": ["段落1", "段落2"],
      "bullets": ["要点1", "要点2", "要点3"],
      "table": {
        "headers": ["列1", "列2", "列3"],
        "rows": [["数据1", "数据2", "数据3"]]
      }
    }
  ]
}

要求：
1. 生成 3-8 个章节
2. 每个章节包含段落、列表或表格
3. 内容有逻辑层次
4. 适合作为正式文档使用
"""


class DOCXGenerateRequest(BaseModel):
    topic: str
    content: str = ""
    style: str = "default"
    model_override: str | None = None
    conv_id: str | None = None
    mode: str = "docx"
    ref_files: list[dict] | None = None
    skip_thinking: bool = False


class DOCXRenderRequest(BaseModel):
    outline: dict
    style: str = "default"
    mode: str = "docx"
    conv_id: str | None = None


@router.post("/generate/stream")
async def docx_generate_stream(req: DOCXGenerateRequest):
    async def generate():
        try:
            if req.conv_id:
                task_info = create_task("docx", req.topic[:200])

            suggestion = detect_mode_suggestion(req.topic, "docx")
            if suggestion:
                yield f"data: {json.dumps(suggestion, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            prompt = f"Word 文档主题：{req.topic}\n参考内容：{req.content or '无'}"

            file_content = None
            if req.ref_files:
                from ..services.file_service import read_text_file
                parts = []
                for f in req.ref_files:
                    fp = f.get("file_path", "")
                    fn = f.get("filename", "")
                    if fp:
                        try:
                            content = read_text_file(fp)
                            parts.append(f"=== 文件: {fn} ===\n{content}")
                        except Exception as e:
                            logger.warning(f"Failed to read ref file {fn}: {e}")
                if parts:
                    file_content = "\n\n".join(parts)

            async for event in run_actor_critic_stream(
                user_message=prompt,
                system_prompt_override=DOCX_SYSTEM_PROMPT,
                conv_id=req.conv_id,
                mode="docx",
                file_content=file_content,
                skip_thinking=req.skip_thinking,
            ):
                if event.get("type") == "actor_done" and event.get("title") and req.conv_id:
                    try:
                        update_conversation_title(req.conv_id, event["title"], mode="docx")
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

                    outline = None
                    try:
                        import re
                        json_match = re.search(r'\{[\s\S]*"title"[\s\S]*\}', output)
                        if json_match:
                            outline = json.loads(json_match.group())
                    except Exception:
                        pass

                    if outline:
                        event["outline"] = outline
                        yield f"data: {json.dumps({'type': 'preview_ready', 'outline': outline}, ensure_ascii=False)}\n\n"

                        docx_path = _generate_docx_from_outline(outline, req.conv_id, req.style)
                        if docx_path:
                            docx_file = {
                                "filename": docx_path.name,
                                "file_name": docx_path.stem,
                                "file_path": str(docx_path),
                                "relative_path": str(docx_path.relative_to(FILE_DIR.parent)),
                                "file_format": "docx",
                                "file_size": docx_path.stat().st_size if docx_path.exists() else 0,
                                "conv_id": req.conv_id,
                                "download_url": f"/files/download/{str(docx_path.relative_to(FILE_DIR.parent)).replace(chr(92), '/')}",
                            }
                            from ..database import save_file_record
                            save_file_record(
                                filename=docx_path.name,
                                stored_filename=docx_path.name,
                                file_path=str(docx_path),
                                file_format="docx",
                                file_size=docx_path.stat().st_size if docx_path.exists() else 0,
                                conv_id=req.conv_id,
                                mode="docx",
                                is_generated=True,
                            )
                            event["file"] = docx_file
                            yield f"data: {json.dumps({'type': 'file_generated', 'file': docx_file}, ensure_ascii=False)}\n\n"

                            if req.conv_id:
                                conv_files = get_files_by_conv(req.conv_id)
                                add_message(req.conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))

                    outline_text = json.dumps(outline, ensure_ascii=False) if outline else output
                    outline_md = save_generated_file(
                        content=outline_text,
                        filename=f"文档大纲_{req.topic[:20]}",
                        file_format="md",
                        conv_id=req.conv_id,
                        mode="docx",
                    )
                    event["outline_file"] = outline_md

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"DOCX stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _generate_docx_from_outline(outline: dict, conv_id: str | None = None, style: str = "default") -> Path | None:
    try:
        conv_dir = _get_conv_dir(conv_id, "docx") if conv_id else FILE_DIR / "docx"
        conv_dir.mkdir(parents=True, exist_ok=True)

        title = outline.get("title", "document")[:50]
        safe_title = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)
        output_path = conv_dir / f"{safe_title}.docx"

        tmp_dir = Path(FILE_DIR) / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        outline_tmp_path = str(tmp_dir / f"docx_outline_{id(outline)}.json")
        with open(outline_tmp_path, "w", encoding="utf-8") as tmp:
            json.dump(outline, tmp, ensure_ascii=False)

        try:
            logger.info(f"[docx-js] Starting subprocess: node {DOCX_RENDERER_SCRIPT} {outline_tmp_path} {output_path} {style}")
            result = subprocess.run(
                ["node", str(DOCX_RENDERER_SCRIPT), outline_tmp_path, str(output_path), style],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(DOCX_RENDERER_DIR),
            )
            if result.returncode != 0:
                logger.error(f"[docx-js] Render failed (exit={result.returncode}): {result.stderr}")
                return None

            if not output_path.exists():
                logger.error(f"[docx-js] Output file not found: {output_path}")
                return None

            logger.info(f"[docx-js] Successfully generated: {output_path} ({output_path.stat().st_size} bytes)")
            return output_path
        finally:
            Path(outline_tmp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Failed to generate DOCX: {e}")
        return None


@router.post("/render")
async def docx_render(req: DOCXRenderRequest):
    docx_path = _generate_docx_from_outline(req.outline, req.conv_id, req.style)
    if not docx_path:
        raise HTTPException(500, "Failed to generate DOCX file")

    return {
        "filename": docx_path.name,
        "file_name": docx_path.stem,
        "file_path": str(docx_path),
        "relative_path": str(docx_path.relative_to(FILE_DIR.parent)),
        "file_format": "docx",
        "file_size": docx_path.stat().st_size,
        "download_url": f"/files/download/{str(docx_path.relative_to(FILE_DIR.parent)).replace(chr(92), '/')}",
    }
