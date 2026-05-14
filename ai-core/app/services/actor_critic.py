import json
import re
import time
import logging
import asyncio
from .llm_service import (
    chat_completion_stream_with_fallback,
    chat_completion_with_fallback,
    ACTOR_CRITIC_MAX_ITER,
)

logger = logging.getLogger(__name__)

ACTOR_SYSTEM_PROMPT = """你是一个专业的办公助手 AI（Actor 角色）。你需要根据用户的需求生成高质量的回复。

输出格式要求（严格按 JSON 格式返回）：
{
  "title": "对话标题（15字以内，概括核心内容）",
  "actor_content": "你的正式回复内容（Markdown格式）",
  "need_download": false,
  "download_filename": "",
  "download_format": "md"
}

注意：
1. title 是本轮对话的简短标题，用于历史记录显示
2. actor_content 是你生成的正式回复正文，使用 Markdown 格式
3. need_download 表示是否需要生成可下载文件（true/false）
4. 如果需要生成文件，填写 download_filename 和 download_format
5. 回复必须严格按以上 JSON 格式输出
6. actor_content 中只包含最终回复内容，不要包含任何审查建议、修改意见或 Critic 的反馈
7. actor_content 必须是完整的回复，不能截断或省略"""

CRITIC_SYSTEM_PROMPT = """你是一个专业的审阅 AI（Critic 角色）。你需要审查 Actor 生成的回复内容，判断质量是否达标。

审查标准：
1. 内容是否准确、完整、符合用户需求
2. 格式是否规范、易读
3. 逻辑是否清晰、无矛盾
4. 语言是否流畅、专业

输出格式要求（严格按 JSON 格式返回）：
{
  "suggestion": "你的修改建议（如果不通过则必填，通过可为空字符串）",
  "approved": true,
  "revised_content": ""
}

注意：
1. approved 为 true 表示通过审查，为 false 表示不通过
2. 如果不通过，suggestion 中给出具体修改建议
3. revised_content 仅在需要修改时填写修改后的版本
4. 回复必须严格按以上 JSON 格式输出"""


def _clean_actor_content(content: str) -> str:
    content = re.sub(r'===?\s*(Critic|Actor)\s*(建议|审查|反馈|回复|输出)\s*===?\s*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'(Critic|Actor)\s*(建议|审查意见|反馈|修改意见)\s*[:：]\s*.*?(?=\n\n|\n#|\Z)', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'审查(未通过|不通过)[：:]\s*.*?(?=\n\n|\n#|\Z)', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'修改建议[：:]\s*.*?(?=\n\n|\n#|\Z)', '', content, flags=re.IGNORECASE | re.DOTALL)
    return content.strip()


def parse_actor_response(response_text: str) -> dict:
    try:
        json_match = re.search(r'\{[\s\S]*"actor_content"[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group())
            actor_content = data.get("actor_content", response_text)
            return {
                "title": data.get("title", ""),
                "actor_content": _clean_actor_content(actor_content),
                "need_download": data.get("need_download", False),
                "download_filename": data.get("download_filename", ""),
                "download_format": data.get("download_format", "md"),
            }
    except (json.JSONDecodeError, KeyError):
        pass

    clean = response_text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    try:
        data = json.loads(clean.strip())
        if "actor_content" in data:
            actor_content = data.get("actor_content", response_text)
            return {
                "title": data.get("title", ""),
                "actor_content": _clean_actor_content(actor_content),
                "need_download": data.get("need_download", False),
                "download_filename": data.get("download_filename", ""),
                "download_format": data.get("download_format", "md"),
            }
        if "slides" in data or "sheets" in data or "sections" in data:
            title = data.get("title", "")
            return {
                "title": title,
                "actor_content": _clean_actor_content(response_text),
                "need_download": True,
                "download_filename": title or "output",
                "download_format": "json",
            }
    except (json.JSONDecodeError, KeyError):
        pass

    return {
        "title": "",
        "actor_content": _clean_actor_content(response_text),
        "need_download": False,
        "download_filename": "",
        "download_format": "md",
    }


def parse_critic_response(response_text: str) -> dict:
    try:
        json_match = re.search(r'\{[\s\S]*"approved"[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "suggestion": data.get("suggestion", ""),
                "approved": data.get("approved", False),
                "revised_content": data.get("revised_content", ""),
            }
    except (json.JSONDecodeError, KeyError):
        pass

    clean = response_text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    try:
        data = json.loads(clean.strip())
        return {
            "suggestion": data.get("suggestion", ""),
            "approved": data.get("approved", False),
            "revised_content": data.get("revised_content", ""),
        }
    except (json.JSONDecodeError, KeyError):
        pass

    approved = "通过" in response_text or "approved" in response_text.lower()
    return {
        "suggestion": response_text,
        "approved": approved,
        "revised_content": "",
    }


TITLE_FORMAT_SUFFIX = """

输出格式要求（严格按 JSON 格式返回）：
{
  "title": "对话标题（15字以内，概括核心内容）",
  "actor_content": "你的正式回复内容（Markdown格式）",
  "need_download": false,
  "download_filename": "",
  "download_format": "md"
}

注意：
1. title 是本轮对话的简短标题，用于历史记录显示
2. actor_content 是你生成的正式回复正文，使用 Markdown 格式
3. need_download 表示是否需要生成可下载文件（true/false）
4. 如果需要生成文件，填写 download_filename 和 download_format
5. 回复必须严格按以上 JSON 格式输出
6. actor_content 中只包含最终回复内容，不要包含任何审查建议、修改意见或 Critic 的反馈
7. actor_content 必须是完整的回复，不能截断或省略"""


async def run_actor_critic_stream(user_message: str, system_prompt_override: str | None = None,
                                    conv_id: str | None = None, mode: str = "chat",
                                    file_content: str | None = None,
                                    skip_thinking: bool = False,
                                    actor_chain: str = "actor",
                                    download_format_override: str | None = None,
                                    rag_context: str | None = None,
                                    enable_react: bool = False,
                                    react_tools: list[dict] | None = None):
    max_iterations = ACTOR_CRITIC_MAX_ITER
    remaining_iterations = max_iterations
    logger.info(f"[ActorCritic] Starting: skip_thinking={skip_thinking}, rag_context={'yes' if rag_context else 'no'}, enable_react={enable_react}")
    if skip_thinking:
        logger.info("[ActorCritic] skip_thinking=True, will skip Critic entirely")
    if system_prompt_override:
        has_custom_json_format = any(kw in system_prompt_override for kw in ['"slides"', '"sheets"', '"sections"'])
        if has_custom_json_format:
            actor_system = system_prompt_override
        else:
            fmt = download_format_override or "md"
            actor_system = system_prompt_override + TITLE_FORMAT_SUFFIX.replace('"download_format": "md"', f'"download_format": "{fmt}"')
    else:
        actor_system = ACTOR_SYSTEM_PROMPT
    critic_system = CRITIC_SYSTEM_PROMPT

    if rag_context:
        base_prompt = f"{user_message}\n\n===参考资料===\n{rag_context}"
    elif file_content:
        base_prompt = f"{user_message}\n\n===文件内容===\n{file_content}"
    else:
        base_prompt = user_message

    current_prompt = base_prompt

    iteration = 0
    while remaining_iterations > 0:
        iteration += 1
        logger.info(f"[ActorCritic] Iteration {iteration}/{max_iterations}, remaining={remaining_iterations}")

        actor_prompt = current_prompt

        if enable_react and react_tools:
            from .react_loop import run_react_loop
            react_result = ""
            logger.info(f"[ActorCritic] Running ReAct loop for iteration {iteration}")
            yield {"type": "react_start", "iteration": iteration}
            async for react_event in run_react_loop(current_prompt, react_tools, conv_id, mode):
                if react_event.get("type") == "react_thought":
                    yield react_event
                elif react_event.get("type") == "tool_call":
                    yield react_event
                elif react_event.get("type") == "tool_result":
                    yield react_event
                elif react_event.get("type") == "react_done":
                    react_result = react_event.get("context", "")
            if react_result:
                actor_prompt += f"\n\n===工具调用结果===\n{react_result}"
                logger.info(f"[ActorCritic] ReAct iteration {iteration} produced context ({len(react_result)} chars)")
            else:
                logger.info(f"[ActorCritic] ReAct iteration {iteration} produced no tool results")

        actor_full = ""
        yield {
            "type": "thinking",
            "phase": "actor",
            "iteration": iteration,
            "remaining_iterations": remaining_iterations,
            "conv_id": conv_id,
        }

        last_ts = time.time()
        async for event in _stream_llm(actor_system, actor_prompt, actor_chain):
            if event["type"] == "model_info":
                yield {
                    "type": "thinking",
                    "phase": "actor",
                    "model": event["model"],
                    "provider": event["provider"],
                }
            elif event["type"] == "chunk":
                now = time.time()
                if now - last_ts > 5:
                    last_ts = now
                    yield {"type": "heartbeat", "text": ""}
                actor_full += event["content"]
                yield {
                    "type": "stream",
                    "role": "actor",
                    "content": event["content"],
                    "iteration": iteration,
                }

        if not actor_full:
            yield {"type": "error", "message": "Actor failed to generate content", "conv_id": conv_id}
            return

        actor_parsed = parse_actor_response(actor_full)
        actor_content = actor_parsed["actor_content"]

        title = actor_parsed.get("title", "")
        if not title:
            first_line = actor_content.strip().split("\n")[0].strip()
            title = re.sub(r'^#+\s*', '', first_line)[:30].strip()
            if not title:
                title = actor_content.strip()[:20].strip()
            if not title:
                title = "新对话"

        yield {
            "type": "actor_done",
            "iteration": iteration,
            "remaining_iterations": remaining_iterations,
            "conv_id": conv_id,
            "title": title,
            "need_download": actor_parsed["need_download"],
            "download_filename": actor_parsed["download_filename"],
            "download_format": actor_parsed["download_format"],
            "output_complete": True,
        }

        if skip_thinking:
            yield {
                "type": "complete",
                "output": actor_content,
                "conv_id": conv_id,
                "iteration": iteration,
                "approved": True,
                "actor_content": actor_content,
                "need_download": actor_parsed["need_download"],
                "download_filename": actor_parsed["download_filename"],
                "download_format": actor_parsed["download_format"],
            }
            return

        critic_prompt = f"""请审查以下 Actor 生成的回复内容：

=== Actor 回复 ===
{actor_content}

用户原始需求：
{user_message}

请根据审查标准判断是否通过。"""

        critic_full = ""
        yield {
            "type": "thinking",
            "phase": "critic",
            "iteration": iteration,
            "conv_id": conv_id,
        }

        async for event in _stream_llm(critic_system, critic_prompt, "critic"):
            if event["type"] == "model_info":
                yield {
                    "type": "thinking",
                    "phase": "critic",
                    "model": event["model"],
                    "provider": event["provider"],
                }
            elif event["type"] == "chunk":
                critic_full += event["content"]
                if not skip_thinking:
                    yield {
                        "type": "stream",
                        "role": "critic",
                        "content": event["content"],
                        "iteration": iteration,
                    }

        if not critic_full:
            logger.warning("Critic did not produce output, accepting actor content")
            yield {
                "type": "complete",
                "output": actor_content,
                "conv_id": conv_id,
                "iteration": iteration,
                "approved": True,
                "actor_content": actor_content,
                "need_download": actor_parsed["need_download"],
                "download_filename": actor_parsed["download_filename"],
                "download_format": actor_parsed["download_format"],
            }
            return

        critic_parsed = parse_critic_response(critic_full)

        yield {
            "type": "critic_done",
            "approved": critic_parsed["approved"],
            "suggestion": critic_parsed["suggestion"],
            "iteration": iteration,
            "conv_id": conv_id,
            "critic_output_complete": True,
        }

        if critic_parsed["approved"]:
            yield {
                "type": "complete",
                "output": actor_content,
                "conv_id": conv_id,
                "iteration": iteration,
                "approved": True,
                "actor_content": actor_content,
                "need_download": actor_parsed["need_download"],
                "download_filename": actor_parsed["download_filename"],
                "download_format": actor_parsed["download_format"],
            }
            return
        else:
            remaining_iterations -= 1
            if remaining_iterations <= 0:
                logger.info("Max iterations reached, outputting last actor content")
                yield {
                    "type": "complete",
                    "output": actor_content,
                    "conv_id": conv_id,
                    "iteration": iteration,
                    "approved": False,
                    "exhausted": True,
                    "actor_content": actor_content,
                    "need_download": actor_parsed["need_download"],
                    "download_filename": actor_parsed["download_filename"],
                    "download_format": actor_parsed["download_format"],
                }
                return
            else:
                current_prompt = f"""Critic 审查未通过，请根据以下建议重新生成回复。

=== Critic 建议 ===
{critic_parsed["suggestion"]}

=== 上次 Actor 回复 ===
{actor_content}

=== 用户原始需求 ===
{base_prompt}

请重新生成更高质量的回复。"""
                yield {
                    "type": "thinking",
                    "phase": "retry",
                    "iteration": iteration,
                    "remaining_iterations": remaining_iterations,
                    "suggestion": critic_parsed["suggestion"],
                    "conv_id": conv_id,
                }


async def _stream_llm(system_prompt: str, user_prompt: str, chain_name: str):
    async for event in chat_completion_stream_with_fallback(
        chain_name=chain_name,
        system_prompt=system_prompt,
        user_message=user_prompt,
    ):
        yield event
