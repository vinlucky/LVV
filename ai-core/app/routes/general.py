import json
import os
from fastapi import APIRouter
from pydantic import BaseModel

from ..database import list_tasks, get_task, create_task, update_task, get_token_usage_stats
from ..services.llm_service import (
    get_available_providers, get_models_for_provider, get_all_models,
    get_task_model_map,
)


class SwitchRequest(BaseModel):
    provider: str
    model_name: str | None = None
    api_key: str | None = None


class DiscoverModelsRequest(BaseModel):
    base_url: str
    api_key: str
    provider_id: str | None = None
    save: bool = True


class TestModelRequest(BaseModel):
    base_url: str
    api_key: str
    model_name: str


class AddProviderRequest(BaseModel):
    base_url: str
    api_key: str
    provider_id: str | None = None
    provider_name: str | None = None
    auto_test: bool = True
    auto_fallback_chain: bool = True


router = APIRouter(tags=["general"])


@router.get("/health")
async def health_check():
    providers = get_available_providers()
    online = [p["id"] for p in providers if p["available"]]
    offline = [p["id"] for p in providers if not p["available"]]
    return {
        "status": "ok",
        "all_offline": len(online) == 0,
        "online_providers": online,
        "offline_providers": offline,
    }


@router.get("/providers")
async def list_providers():
    providers = get_available_providers()
    return {"providers": [p["id"] for p in providers]}


@router.get("/providers/detail")
async def list_providers_detail():
    providers = get_available_providers()
    result = {}
    for p in providers:
        result[p["id"]] = {
            "name": p["name"],
            "description": p.get("description", ""),
            "has_api_key": p.get("has_api_key", False),
            "masked_api_key": p.get("masked_api_key", ""),
            "model_counts": p.get("model_counts", {"llm": 0, "omni": 0, "embedding": 0}),
        }
    return result


@router.post("/switch")
async def switch_provider(req: SwitchRequest):
    if req.api_key and req.provider:
        try:
            from ..config import ROOT_DIR
            env_path = ROOT_DIR / ".env"
            env_map = {}
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_s = line.strip()
                        if line_s and not line_s.startswith("#") and "=" in line_s:
                            k, _, v = line_s.partition("=")
                            env_map[k.strip()] = v.strip().strip("\"'")
            provider_key_map = {"qwen": "QWEN_API_KEY", "tencent": "TENCENT_API_KEY"}
            key_name = provider_key_map.get(req.provider)
            if not key_name:
                key_name = f"{req.provider.upper()}_API_KEY"
            env_map[key_name] = req.api_key
            os.environ[key_name] = req.api_key
            with open(env_path, "w", encoding="utf-8") as f:
                for k, v in env_map.items():
                    f.write(f"{k}={v}\n")
        except Exception:
            pass

    return {"provider": req.provider, "model_name": req.model_name, "ok": True}


@router.get("/models")
async def list_models():
    models = get_all_models()
    return {"models": models}


@router.get("/task-model-map")
async def task_model_map():
    return get_task_model_map()


@router.post("/models/discover")
async def discover_models(req: DiscoverModelsRequest):
    return {"models": [], "message": "Discovery stub"}


@router.post("/models/discover-existing")
async def discover_existing_models():
    return {"models": [], "message": "Discovery stub"}


@router.post("/models/test")
async def test_model(req: TestModelRequest):
    return {"success": False, "message": "Test stub"}


@router.post("/models/reload")
async def reload_models():
    from ..config import load_models_config
    config = load_models_config()
    total = sum(len(p.get("models", [])) for p in config.get("providers", {}).values())
    return {"models_loaded": total}


@router.post("/providers/add")
async def add_provider(req: AddProviderRequest):
    return {"provider_id": req.provider_id or "custom", "ok": True}


@router.get("/tasks")
async def get_tasks(status: str | None = None):
    tasks = list_tasks(status)
    return tasks


@router.get("/tasks/{task_id}")
async def get_task_detail(task_id: str):
    task = get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    return task


@router.get("/token-usage")
async def token_usage():
    return get_token_usage_stats()


@router.get("/offline/demo/{task_type}")
async def offline_demo(task_type: str):
    import json as _json
    demos = {
        "chat": {
            "output": "你好！我是 LVV 办公助手。我可以帮助你：\n\n1. 📝 生成会议纪要\n2. 📚 生成文献摘要\n3. ✨ 多语言润色\n4. 📊 PPT 生成\n\n请随时告诉我你的需求！",
            "critic_feedbacks": ["通过"],
        },
        "meeting": {
            "output": "## 会议纪要\n\n**会议主题**: 项目进度讨论\n**参会人员**: 张三、李四、王五\n\n### 关键讨论点\n- 前端开发进度正常\n- 后端API已完成80%\n- 测试下周启动\n\n### 决议\n- 下周三进行集成测试",
            "critic_feedbacks": ["通过"],
        },
        "literature": {
            "output": "## 文献摘要\n\n**标题**: 人工智能在医疗领域的应用\n**作者**: 示例作者\n\n### 研究背景\n人工智能技术正在深刻改变医疗行业...",
            "critic_feedbacks": ["通过"],
        },
        "polish": {
            "output": "This research demonstrates significant potential for advancing our understanding. We recommend conducting additional experiments to further validate the proposed hypothesis.",
            "critic_feedbacks": ["通过"],
        },
        "ppt": {
            "output": _json.dumps({
                "title": "人工智能发展趋势",
                "slides": [
                    {"title": "概述", "bullets": ["AI技术发展历程", "当前应用场景", "未来展望"]},
                    {"title": "核心技术", "bullets": ["机器学习", "深度学习", "自然语言处理"]},
                ],
            }, ensure_ascii=False),
            "critic_feedbacks": ["通过"],
        },
    }

    demo = demos.get(task_type, demos["chat"])
    if isinstance(demo.get("output"), dict):
        demo["output"] = _json.dumps(demo["output"], ensure_ascii=False, indent=2)
    return demo