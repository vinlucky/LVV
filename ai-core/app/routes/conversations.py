from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..database import (
    create_conversation, get_conversation, list_conversations,
    delete_conversation, add_message, update_conversation_title,
    search_conversations,
)
from ..services.llm_service import chat_completion_with_fallback

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    task_type: str = "chat"
    initial_message: str | None = None


class AddMessageRequest(BaseModel):
    conv_id: str
    role: str
    content: str


class GenerateTitleRequest(BaseModel):
    conv_id: str


@router.post("")
async def api_create_conversation(req: CreateConversationRequest):
    conv = create_conversation(req.task_type)
    if req.initial_message:
        add_message(conv["conv_id"], "user", req.initial_message)
    return conv


@router.get("")
async def api_list_conversations(limit: int = 50, offset: int = 0, task_type: str | None = None):
    convs = list_conversations(limit, offset, task_type)
    return {"conversations": convs, "total": len(convs)}


@router.get("/by-type")
async def api_list_conversations_by_type():
    convs = list_conversations(200, 0)
    grouped = {}
    for c in convs:
        t = c.get("task_type", "chat")
        if t not in grouped:
            grouped[t] = []
        grouped[t].append(c)
    return {"groups": grouped}


@router.get("/{conv_id}")
async def api_get_conversation(conv_id: str):
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.delete("/{conv_id}")
async def api_delete_conversation(conv_id: str):
    delete_conversation(conv_id)
    return {"ok": True}


@router.post("/message")
async def api_add_message(req: AddMessageRequest):
    return add_message(req.conv_id, req.role, req.content)


@router.post("/generate-title")
async def api_generate_title(req: GenerateTitleRequest):
    conv = get_conversation(req.conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = conv.get("messages", [])
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    if not user_msgs:
        return {"title": "新对话"}

    first_msg = user_msgs[0][:200]
    result = chat_completion_with_fallback(
        chain_name="critic",
        system_prompt="你是一个标题生成器。根据用户的第一条消息生成一个简短的对话标题（15字以内），只输出标题，不要输出其他内容。",
        user_message=first_msg,
    )
    title = result.get("content", "新对话").strip().strip("\"'")[:50]
    update_conversation_title(req.conv_id, title)
    return {"title": title}


@router.get("/search/{keyword}")
async def api_search_conversations(keyword: str, limit: int = 20):
    convs = search_conversations(keyword, limit)
    return {"conversations": convs}