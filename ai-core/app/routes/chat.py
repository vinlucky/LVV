import json
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from ..config import FILE_DIR
from ..database import add_message, save_file_record, get_files_by_conv, get_conversation, update_conversation_title, create_task, update_task
from ..services.actor_critic import run_actor_critic_stream
from ..services.file_service import save_generated_file
from ..services.mode_detector import detect_mode_suggestion, detect_auto_file_type
from ..services.auto_file_service import read_ref_files, try_auto_generate_file, get_auto_file_system_prompt
from ..services.rag_service import build_rag_context
from ..services.tool_registry import get_tools_for_mode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

MATERIAL_TEMPLATES = [
    {"key": "meeting_minutes", "name": "会议纪要", "prompt": "请根据以下内容生成专业的会议纪要", "file_format": "md", "file_name": "会议纪要", "icon": "📝"},
    {"key": "weekly_report", "name": "实习周报", "prompt": "请根据以下内容生成专业的实习周报", "file_format": "md", "file_name": "实习周报", "icon": "📋"},
    {"key": "research_summary", "name": "研究摘要", "prompt": "请根据以下内容生成学术研究摘要", "file_format": "md", "file_name": "研究摘要", "icon": "📚"},
    {"key": "email_draft", "name": "邮件草稿", "prompt": "请根据以下内容生成专业的邮件草稿", "file_format": "md", "file_name": "邮件草稿", "icon": "✉️"},
    {"key": "presentation_script", "name": "演讲文稿", "prompt": "请根据以下内容生成演讲文稿", "file_format": "md", "file_name": "演讲文稿", "icon": "🎤"},
    {"key": "report", "name": "报告", "prompt": "请根据以下内容生成正式报告", "file_format": "md", "file_name": "报告", "icon": "📄"},
]


class ChatRequest(BaseModel):
    message: str
    system_prompt: str | None = None
    model_override: str | None = None
    auto_generate_file: bool = False
    file_format: str = "md"
    conv_id: str | None = None
    mode: str = "chat"
    ref_files: list[dict] | None = None
    skip_thinking: bool = False


class GenerateFileRequest(BaseModel):
    content: str
    file_format: str = "md"
    file_name: str = "内容"
    conv_id: str | None = None
    mode: str = "chat"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    async def generate():
        try:
            if req.conv_id:
                conv = get_conversation(req.conv_id)
                user_msg_count = len([m for m in conv.get("messages", []) if m["role"] == "user"]) if conv else 0
                task_info = create_task("chat", req.message[:200])

            suggestion = detect_mode_suggestion(req.message, "chat")
            if suggestion:
                yield f"data: {json.dumps(suggestion, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            system_prompt_override = req.system_prompt or get_auto_file_system_prompt(req.message)
            auto_file_type = detect_auto_file_type(req.message)
            download_format_override = auto_file_type if auto_file_type else None

            file_content = read_ref_files(req.ref_files)

            rag_context = None
            try:
                rag_context = build_rag_context(
                    query=req.message, mode=req.mode,
                    conv_id=req.conv_id, top_k=5,
                )
                if rag_context:
                    logger.info(f"[chat] RAG context built ({len(rag_context)} chars)")
            except Exception as e:
                logger.warning(f"[chat] RAG context failed: {e}")

            react_tools = get_tools_for_mode(req.mode)
            has_files = bool(req.ref_files and len(req.ref_files) > 0)
            enable_react = has_files
            logger.info(f"[chat] ReAct {'enabled' if enable_react else 'disabled'} (has_files={has_files}), tools: {[t['function']['name'] for t in react_tools]}")
            logger.info(f"[chat] skip_thinking={req.skip_thinking}")

            async for event in run_actor_critic_stream(
                user_message=req.message,
                system_prompt_override=system_prompt_override,
                conv_id=req.conv_id,
                mode=req.mode,
                file_content=file_content,
                skip_thinking=req.skip_thinking,
                download_format_override=download_format_override,
                rag_context=rag_context,
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "actor_done" and event.get("title") and req.conv_id:
                    try:
                        update_conversation_title(req.conv_id, event["title"], mode=req.mode)
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

                    auto_file = try_auto_generate_file(output, req.message, req.conv_id, req.mode)
                    if auto_file:
                        event["file"] = auto_file
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': auto_file}, ensure_ascii=False)}\n\n"

                    need_download = event.get("need_download", False)
                    auto_file_type = detect_auto_file_type(req.message)
                    if (need_download or req.auto_generate_file or auto_file_type) and not auto_file:
                        dl_filename = event.get("download_filename", "回复内容")
                        if auto_file_type == "docx":
                            dl_format = "docx"
                        elif auto_file_type == "xlsx":
                            dl_format = "xlsx"
                        else:
                            dl_format = event.get("download_format", "md")
                        file_info = save_generated_file(
                            content=output,
                            filename=dl_filename,
                            file_format=dl_format,
                            conv_id=req.conv_id,
                            mode=req.mode,
                        )
                        event["file"] = file_info
                        if req.conv_id:
                            conv_files = get_files_by_conv(req.conv_id)
                            add_message(req.conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': file_info}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/files")
async def get_chat_files():
    from ..database import get_all_files
    files = get_all_files("chat")
    return {"files": files}


@router.get("/material-templates")
async def get_material_templates():
    return {"templates": MATERIAL_TEMPLATES}


@router.post("/generate-file")
async def generate_file(req: GenerateFileRequest):
    file_info = save_generated_file(
        content=req.content,
        filename=req.file_name,
        file_format=req.file_format,
        conv_id=req.conv_id,
        mode=req.mode,
    )
    if req.conv_id:
        conv_files = get_files_by_conv(req.conv_id)
        add_message(req.conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))
    return file_info


@router.get("/download/{filename:path}")
async def download_chat_file(
    filename: str,
    mode: str = Query("chat"),
    conv_id: str = Query(""),
):
    from ..services.file_service import get_download_path
    normalized = filename.replace("\\", "/")
    for search in [
        FILE_DIR / normalized,
        get_download_path(normalized),
    ]:
        if search.exists():
            return FileResponse(str(search), filename=search.name)
    if conv_id:
        conv_dirs = list(FILE_DIR.glob(f"**/*_{conv_id[:8]}"))
        for conv_dir in conv_dirs:
            if conv_dir.is_dir():
                target = conv_dir / filename
                if target.exists():
                    return FileResponse(str(target), filename=target.name)
        for p in FILE_DIR.rglob(filename):
            return FileResponse(str(p), filename=p.name)
    raise HTTPException(404, f"File not found: {filename}")


@router.post("")
async def chat_sync(req: ChatRequest):
    from ..services.llm_service import chat_completion_with_fallback

    if req.conv_id:
        add_message(req.conv_id, "user", req.message)

    prompt = req.message
    if req.system_prompt:
        prompt = f"[系统指令: {req.system_prompt}]\n\n{req.message}"

    result = chat_completion_with_fallback(
        chain_name="actor",
        system_prompt=req.system_prompt or "",
        user_message=prompt,
    )

    output = result.get("content", "")
    if req.conv_id:
        add_message(req.conv_id, "actor", output)

    file_info = None
    if req.auto_generate_file:
        file_info = save_generated_file(
            content=output,
            filename="回复内容",
            file_format=req.file_format or "md",
            conv_id=req.conv_id,
            mode=req.mode,
        )

    return {
        "output": output,
        "model": result.get("model", ""),
        "file": file_info,
    }