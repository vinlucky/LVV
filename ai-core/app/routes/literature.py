import json
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import add_message, get_files_by_conv, get_conversation, update_conversation_title, create_task, update_task
from ..services.actor_critic import run_actor_critic_stream
from ..services.file_service import save_upload_file, save_generated_file, read_text_file
from ..services.mode_detector import detect_mode_suggestion
from ..services.auto_file_service import try_auto_generate_file
from ..services.rag_service import build_rag_context
from ..services.tool_registry import get_tools_for_mode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/literature", tags=["literature"])

LITERATURE_SYSTEM_PROMPT = """你是一个专业的文献分析 AI。请根据提供的文献内容生成详细摘要和分析。

输出格式：
1. **文献信息**（标题、作者、期刊/来源、年份）
2. **研究背景**
3. **研究方法**
4. **主要发现**
5. **创新点与贡献**
6. **局限性**
7. **综合评价**

请用 Markdown 格式输出，力求专业、准确。"""


class SummarizeRequest(BaseModel):
    file_path: str
    query: str = "请生成这篇文献的详细摘要"
    model_override: str | None = None
    conv_id: str | None = None
    mode: str = "literature"
    skip_thinking: bool = False


class AskDocumentRequest(BaseModel):
    doc_id: str
    question: str
    model_override: str | None = None
    conv_id: str | None = None
    skip_thinking: bool = False


@router.post("/summarize/stream")
async def literature_summarize_stream(req: SummarizeRequest):
    file_content = read_text_file(req.file_path)

    async def generate():
        try:
            if req.conv_id:
                task_info = create_task("literature", req.query[:200])
                conv = get_conversation(req.conv_id)
                user_msg_count = len([m for m in conv.get("messages", []) if m["role"] == "user"]) if conv else 0
            suggestion = detect_mode_suggestion(req.query, "literature")
            if suggestion:
                yield f"data: {json.dumps(suggestion, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            prompt = f"请分析以下文献内容：\n\n{file_content[:8000]}\n\n用户需求：{req.query}"

            rag_context = None
            try:
                rag_context = build_rag_context(query=req.query, mode="literature", conv_id=req.conv_id, top_k=5)
                if rag_context:
                    logger.info(f"[literature] RAG context built ({len(rag_context)} chars)")
            except Exception as e:
                logger.warning(f"[literature] RAG context failed: {e}")

            react_tools = get_tools_for_mode("literature")
            has_file = bool(req.file_path)
            enable_react = has_file
            logger.info(f"[literature] ReAct {'enabled' if enable_react else 'disabled'} (has_file={has_file}), tools: {[t['function']['name'] for t in react_tools]}")

            logger.info(f"[literature] skip_thinking={req.skip_thinking}")

            summary_file = None
            async for event in run_actor_critic_stream(
                user_message=prompt,
                system_prompt_override=LITERATURE_SYSTEM_PROMPT,
                conv_id=req.conv_id,
                mode="literature",
                skip_thinking=req.skip_thinking,
                rag_context=rag_context,
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "actor_done" and event.get("title") and req.conv_id:
                    try:
                        update_conversation_title(req.conv_id, event["title"], mode="literature")
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
                    auto_file = try_auto_generate_file(output, req.query, req.conv_id, "literature")
                    if auto_file:
                        event["file"] = auto_file
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': auto_file}, ensure_ascii=False)}\n\n"
                    if not auto_file:
                        summary_file = save_generated_file(
                            content=output,
                            filename="文献摘要",
                            file_format="md",
                            conv_id=req.conv_id,
                            mode="literature",
                        )
                        event["file"] = summary_file
                        if req.conv_id:
                            conv_files = get_files_by_conv(req.conv_id)
                            add_message(req.conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': summary_file}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Literature stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/upload")
async def upload_literature_file(
    file: UploadFile = File(...),
    mode: str = Form("literature"),
    conv_id: str | None = Form(None),
):
    file_info = await save_upload_file(file, conv_id, mode)
    try:
        file_content = read_text_file(file_info["file_path"])
        file_info["preview"] = file_content[:500]
    except Exception:
        file_info["preview"] = ""
    return file_info


@router.post("/ask")
async def ask_about_document(req: AskDocumentRequest):
    async def generate():
        try:
            react_tools = get_tools_for_mode("literature")
            enable_react = False
            logger.info(f"[literature/ask] ReAct disabled (no file upload), tools: {[t['function']['name'] for t in react_tools]}")

            async for event in run_actor_critic_stream(
                user_message=f"请根据之前分析的文献内容回答问题：{req.question}",
                system_prompt_override=LITERATURE_SYSTEM_PROMPT,
                conv_id=req.conv_id,
                mode="literature",
                skip_thinking=req.skip_thinking,
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "complete":
                    output = event.get("output", "")
                    if req.conv_id:
                        add_message(req.conv_id, "actor", output)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Ask document error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/summarize")
async def literature_summarize_sync(req: SummarizeRequest):
    from ..services.llm_service import chat_completion_with_fallback

    file_content = read_text_file(req.file_path)
    prompt = f"请分析以下文献内容：\n\n{file_content[:8000]}\n\n用户需求：{req.query}"

    result = chat_completion_with_fallback(
        chain_name="actor",
        system_prompt=LITERATURE_SYSTEM_PROMPT,
        user_message=prompt,
    )

    output = result.get("content", "")
    if req.conv_id:
        add_message(req.conv_id, "actor", output)

    summary_file = save_generated_file(
        content=output,
        filename="文献摘要",
        file_format="md",
        conv_id=req.conv_id,
        mode="literature",
    )

    return {
        "output": output,
        "model": result.get("model", ""),
        "file": summary_file,
    }