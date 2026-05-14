import json
import logging
import subprocess
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from ..config import SKILLS_DIR, FILE_DIR
from ..database import add_message, get_files_by_conv, update_conversation_title, create_task, update_task, save_file_record
from ..services.actor_critic import run_actor_critic_stream
from ..services.file_service import save_generated_file, _get_conv_dir
from ..services.mode_detector import detect_mode_suggestion
from ..services.auto_file_service import try_auto_generate_file
from ..services.rag_service import build_rag_context
from ..services.tool_registry import get_tools_for_mode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ppt", tags=["ppt"])

PPT_SYSTEM_PROMPT = """你是一个专业的 PPT 大纲生成 AI。请根据用户提供的主题和内容，生成结构化的 PPT 大纲。

输出格式（JSON）：
{
  "title": "PPT 总标题",
  "subtitle": "副标题（可选）",
  "author": "作者",
  "slides": [
    {
      "title": "幻灯片标题",
      "bullets": ["要点1", "要点2", "要点3"],
      "notes": "演讲备注",
      "image_keywords": "配图关键词"
    }
  ]
}

要求：
1. 生成 8-15 页幻灯片
2. 每页 3-5 个要点
3. 内容有逻辑层次
4. 适合演示使用
"""

PPT_TEMPLATES = [
    {"key": "default", "name": "默认模板", "description": "简洁专业的默认模板"},
    {"key": "academic", "name": "学术模板", "description": "适合学术报告和论文答辩"},
    {"key": "business", "name": "商务模板", "description": "适合商业汇报和项目展示"},
    {"key": "creative", "name": "创意模板", "description": "色彩丰富的创意风格"},
]


class PPTGenerateRequest(BaseModel):
    topic: str
    content: str = ""
    style: str = "academic"
    template: str = "default"
    model_override: str | None = None
    conv_id: str | None = None
    mode: str = "ppt"
    ref_files: list[dict] | None = None
    skip_thinking: bool = False


class PPTRenderRequest(BaseModel):
    outline: dict
    template: str = "default"
    mode: str = "ppt"
    conv_id: str | None = None


@router.post("/generate/stream")
async def ppt_generate_stream(req: PPTGenerateRequest):
    async def generate():
        try:
            if req.conv_id:
                task_info = create_task("ppt", req.topic[:200])

            suggestion = detect_mode_suggestion(req.topic, "ppt")
            if suggestion:
                yield f"data: {json.dumps(suggestion, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            prompt = f"PPT 主题：{req.topic}\n风格：{req.style}\n参考内容：{req.content or '无'}"

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

            rag_context = None
            try:
                rag_context = build_rag_context(query=req.topic, mode="ppt", conv_id=req.conv_id, top_k=5)
                if rag_context:
                    logger.info(f"[ppt] RAG context built ({len(rag_context)} chars)")
            except Exception as e:
                logger.warning(f"[ppt] RAG context failed: {e}")

            react_tools = get_tools_for_mode("ppt")
            has_files = bool(req.ref_files and len(req.ref_files) > 0)
            enable_react = has_files
            logger.info(f"[ppt] ReAct {'enabled' if enable_react else 'disabled'} (has_files={has_files}), tools: {[t['function']['name'] for t in react_tools]}")

            async for event in run_actor_critic_stream(
                user_message=prompt,
                system_prompt_override=PPT_SYSTEM_PROMPT,
                conv_id=req.conv_id,
                mode="ppt",
                file_content=file_content,
                skip_thinking=req.skip_thinking,
                rag_context=rag_context,
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "actor_done" and event.get("title") and req.conv_id:
                    try:
                        update_conversation_title(req.conv_id, event["title"], mode="ppt")
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

                    auto_file = try_auto_generate_file(output, req.topic, req.conv_id, "ppt")
                    if auto_file:
                        event["file"] = auto_file
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': auto_file}, ensure_ascii=False)}\n\n"

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

                        pptx_path = _generate_pptx_from_outline(outline, req.conv_id, req.style)
                        if pptx_path:
                            pptx_file = {
                                "filename": pptx_path.name,
                                "file_name": pptx_path.stem,
                                "file_path": str(pptx_path),
                                "relative_path": str(pptx_path.relative_to(FILE_DIR.parent)),
                                "file_format": "pptx",
                                "file_size": pptx_path.stat().st_size if pptx_path.exists() else 0,
                                "conv_id": req.conv_id,
                                "download_url": f"/files/download/{str(pptx_path.relative_to(FILE_DIR.parent)).replace(chr(92), '/')}",
                            }
                            from ..database import save_file_record
                            save_file_record(
                                filename=pptx_path.name,
                                stored_filename=pptx_path.name,
                                file_path=str(pptx_path),
                                file_format="pptx",
                                file_size=pptx_path.stat().st_size if pptx_path.exists() else 0,
                                conv_id=req.conv_id,
                                mode="ppt",
                                is_generated=True,
                            )
                            event["file"] = pptx_file
                            yield f"data: {json.dumps({'type': 'file_generated', 'file': pptx_file}, ensure_ascii=False)}\n\n"

                    outline_text = json.dumps(outline, ensure_ascii=False) if outline else output
                    outline_md = save_generated_file(
                        content=outline_text,
                        filename=f"PPT大纲_{req.topic[:20]}",
                        file_format="md",
                        conv_id=req.conv_id,
                        mode="ppt",
                    )
                    event["outline_file"] = outline_md
                    yield f"data: {json.dumps({'type': 'file_generated', 'file': outline_md}, ensure_ascii=False)}\n\n"

                    if req.conv_id:
                        conv_files = get_files_by_conv(req.conv_id)
                        add_message(req.conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"PPT stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


PPTX_RENDERER_DIR = Path(__file__).resolve().parent.parent.parent / "pptx-renderer"
PPTX_RENDERER_SCRIPT = PPTX_RENDERER_DIR / "render.js"


def _generate_pptx_from_outline(outline: dict, conv_id: str | None = None, style: str = "academic") -> Path | None:
    try:
        conv_dir = _get_conv_dir(conv_id, "ppt") if conv_id else FILE_DIR / "ppt"
        conv_dir.mkdir(parents=True, exist_ok=True)

        ppt_title = outline.get("title", "presentation")[:50]
        safe_title = "".join(c if c.isalnum() or c in "._- " else "_" for c in ppt_title)
        output_path = conv_dir / f"{safe_title}.pptx"

        tmp_dir = Path(FILE_DIR) / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        outline_tmp_path = str(tmp_dir / f"ppt_outline_{id(outline)}.json")
        with open(outline_tmp_path, "w", encoding="utf-8") as tmp:
            json.dump(outline, tmp, ensure_ascii=False)

        try:
            logger.info(f"[PptxGenJS] Starting subprocess: node {PPTX_RENDERER_SCRIPT} {outline_tmp_path} {output_path} {style}")
            result = subprocess.run(
                ["node", str(PPTX_RENDERER_SCRIPT), outline_tmp_path, str(output_path), style],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(PPTX_RENDERER_DIR),
            )
            if result.returncode != 0:
                logger.error(f"[PptxGenJS] Render failed (exit={result.returncode}): {result.stderr}")
                return None

            if not output_path.exists():
                logger.error(f"[PptxGenJS] Output file not found: {output_path}")
                return None

            logger.info(f"[PptxGenJS] Successfully generated: {output_path} ({output_path.stat().st_size} bytes)")
            return output_path
        finally:
            Path(outline_tmp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Failed to generate PPTX: {e}")
        return None


@router.post("/render")
async def ppt_render(req: PPTRenderRequest):
    pptx_path = _generate_pptx_from_outline(req.outline, req.conv_id, req.template)
    if not pptx_path:
        raise HTTPException(500, "Failed to generate PPTX file")

    return {
        "filename": pptx_path.name,
        "file_name": pptx_path.stem,
        "file_path": str(pptx_path),
        "relative_path": str(pptx_path.relative_to(FILE_DIR.parent)),
        "file_format": "pptx",
        "file_size": pptx_path.stat().st_size,
        "download_url": f"/files/download/{str(pptx_path.relative_to(FILE_DIR.parent)).replace(chr(92), '/')}",
    }


@router.get("/templates")
async def get_ppt_templates():
    return {"templates": PPT_TEMPLATES}