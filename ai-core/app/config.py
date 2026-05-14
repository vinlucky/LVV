import os
import json5
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"
FILE_DIR = ROOT_DIR / "file"
SKILLS_DIR = ROOT_DIR / "skills"
DB_DIR = ROOT_DIR / "data"

FILE_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

MODELS_CONFIG_PATH = CONFIG_DIR / "models.json5"
DB_PATH = DB_DIR / "lvv.db"
VEC_PATH = DB_DIR / "lvv_vec.db"

_env_file = ROOT_DIR / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_env_file), override=True)
    except ImportError:
        _dotenv_lines = []
        with open(_env_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    _dotenv_lines.append(line)
        for line in _dotenv_lines:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ[key] = value

_qwen_api_key = os.getenv("QWEN_API_KEY", "")
_tencent_api_key = os.getenv("TENCENT_API_KEY", "")
_qwen_api_base = os.getenv("QWEN_API_BASE", "")
_tencent_api_base = os.getenv("TENCENT_API_BASE", "")
_default_provider = os.getenv("DEFAULT_PROVIDER", "qwen")
AI_CORE_HOST = os.getenv("AI_CORE_HOST", "127.0.0.1")
AI_CORE_PORT = int(os.getenv("AI_CORE_PORT", "8000"))
AI_CORE_URL = os.getenv("AI_CORE_URL", f"http://{AI_CORE_HOST}:{AI_CORE_PORT}")


def load_models_config() -> dict:
    with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json5.load(f)


def get_provider_config(provider: str) -> dict:
    config = load_models_config()
    return config.get("providers", {}).get(provider, {})


def get_fallback_chain(chain_name: str) -> dict:
    config = load_models_config()
    return config.get("fallback_chains", {}).get(chain_name, {})


def get_api_key(provider: str) -> str:
    if provider == "qwen":
        return os.getenv("QWEN_API_KEY", _qwen_api_key)
    elif provider == "tencent":
        return os.getenv("TENCENT_API_KEY", _tencent_api_key)
    env_key = f"{provider.upper()}_API_KEY"
    return os.getenv(env_key, "")


def get_base_url(provider: str) -> str:
    if provider == "qwen" and _qwen_api_base:
        return _qwen_api_base
    if provider == "tencent" and _tencent_api_base:
        return _tencent_api_base
    provider_cfg = get_provider_config(provider)
    base_url_env = provider_cfg.get("base_url_env", "")
    if base_url_env:
        env_val = os.getenv(base_url_env, "")
        if env_val:
            return env_val
    return provider_cfg.get("base_url", "")


def get_settings() -> dict:
    config = load_models_config()
    return config.get("settings", {})