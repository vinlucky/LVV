import json
import logging
import asyncio
import threading
from openai import OpenAI

from .tool_executor import execute_tool
from .llm_service import _get_client_for_model, _get_fallback_models, get_api_key
from ..config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()
MAX_REACT_STEPS = 3
REQUEST_TIMEOUT = _settings.get("request_timeout", 120)
HEARTBEAT_INTERVAL = 3

REACT_SYSTEM_PROMPT = """你是一个智能助手，可以使用工具来获取信息。请按以下步骤工作：

1. 分析用户的问题，判断是否需要使用工具获取信息
2. 如果需要，调用合适的工具
3. 根据工具返回的结果，决定是否需要继续调用工具
4. 当信息充足时，停止调用工具

重要规则：
- 如果用户消息中已经包含了"===文件内容==="或"===参考资料==="，说明文件内容已经提供，不需要再调用 read_file 或 list_files 工具读取
- 只在确实缺少信息时才调用工具，已有足够信息则直接结束
- 优先使用 search_knowledge_base 搜索知识库获取补充信息"""


async def run_react_loop(user_message: str, tools: list[dict],
                          conv_id: str | None = None, mode: str = "chat"):
    api_key = get_api_key("qwen")
    if not api_key:
        logger.warning("[react] No API key, skipping ReAct loop")
        yield {"type": "react_done", "context": "", "steps": 0}
        return

    models = _get_fallback_models("actor")
    if not models:
        yield {"type": "react_done", "context": "", "steps": 0}
        return

    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    tool_context_parts = []
    steps = 0

    for step in range(MAX_REACT_STEPS):
        steps += 1
        tool_called = False

        for model_name in models:
            try:
                client, provider_id, actual_model = _get_client_for_model(model_name)
                logger.info(f"[react] Step {step + 1}, model: {model_name}")

                yield {
                    "type": "heartbeat",
                    "text": f"ReAct 第{step + 1}轮思考中...",
                    "step": step + 1,
                }

                stream = client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=2048,
                    timeout=REQUEST_TIMEOUT,
                    stream=True,
                )

                loop = asyncio.get_event_loop()
                chunk_queue: asyncio.Queue = asyncio.Queue()

                def _drain_stream():
                    try:
                        for chunk in stream:
                            if not chunk.choices:
                                continue
                            delta = chunk.choices[0].delta
                            finish_reason = chunk.choices[0].finish_reason
                            loop.call_soon_threadsafe(
                                chunk_queue.put_nowait,
                                {"delta": delta, "finish_reason": finish_reason},
                            )
                    except Exception as e:
                        loop.call_soon_threadsafe(
                            chunk_queue.put_nowait,
                            {"error": str(e)},
                        )
                    finally:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

                drain_thread = threading.Thread(target=_drain_stream, daemon=True)
                drain_thread.start()

                full_content = ""
                tool_calls_accum: dict[int, dict] = {}

                while True:
                    try:
                        item = await asyncio.wait_for(
                            chunk_queue.get(), timeout=HEARTBEAT_INTERVAL
                        )
                    except asyncio.TimeoutError:
                        yield {
                            "type": "heartbeat",
                            "text": f"ReAct 第{step + 1}轮思考中...",
                            "step": step + 1,
                        }
                        continue

                    if item is None:
                        break

                    if "error" in item:
                        raise RuntimeError(item["error"])

                    delta = item["delta"]
                    finish_reason = item["finish_reason"]

                    if delta and delta.content:
                        full_content += delta.content
                        yield {
                            "type": "react_thought",
                            "step": step + 1,
                            "thought": delta.content,
                            "streaming": True,
                            "model": actual_model,
                            "provider": provider_id,
                        }

                    if delta and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_accum:
                                tool_calls_accum[idx] = {
                                    "id": "",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc_delta.id:
                                tool_calls_accum[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_accum[idx]["function"]["name"] += (
                                        tc_delta.function.name
                                    )
                                if tc_delta.function.arguments:
                                    tool_calls_accum[idx]["function"]["arguments"] += (
                                        tc_delta.function.arguments
                                    )

                drain_thread.join(timeout=5)

                if full_content:
                    logger.info(f"[react] Step {step + 1} thought: {full_content[:200]}")
                    yield {
                        "type": "react_thought",
                        "step": step + 1,
                        "thought": full_content[:500],
                        "streaming": False,
                        "model": actual_model,
                        "provider": provider_id,
                    }

                tool_calls_list = [
                    tool_calls_accum[i] for i in sorted(tool_calls_accum.keys())
                ]

                if not tool_calls_list:
                    logger.info(f"[react] Step {step + 1}: No tool calls, ReAct loop ending")
                    break

                assistant_tool_calls = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in tool_calls_list
                ]

                messages.append({
                    "role": "assistant",
                    "content": full_content or "",
                    "tool_calls": assistant_tool_calls,
                })

                for tc in tool_calls_list:
                    tool_called = True
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    logger.info(f"[react] Step {step + 1} calling tool: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")

                    yield {
                        "type": "tool_call",
                        "step": step + 1,
                        "name": tool_name,
                        "arguments": tool_args,
                        "call_id": tc["id"],
                    }

                    result = execute_tool(tool_name, tool_args, mode, conv_id)

                    logger.info(f"[react] Step {step + 1} tool result: {result[:200]}")

                    yield {
                        "type": "tool_result",
                        "step": step + 1,
                        "name": tool_name,
                        "result": result[:1000],
                        "call_id": tc["id"],
                    }

                    tool_context_parts.append(f"工具 {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:100]}):\n{result}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                break

            except Exception as e:
                logger.warning(f"[react] Model {model_name} failed at step {step + 1}: {e}")
                continue

        if not tool_called:
            break

    context = "\n\n".join(tool_context_parts) if tool_context_parts else ""
    logger.info(f"[react] Loop completed: {steps} steps, {len(tool_context_parts)} tool calls")
    yield {"type": "react_done", "context": context, "steps": steps}
