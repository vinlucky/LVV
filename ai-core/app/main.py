import logging
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from .routes import conversations, chat, meeting, literature, polish, ppt, xlsx, docx, files, skills, general
from .database import get_conn
from .config import AI_CORE_HOST, AI_CORE_PORT

ASCII_LOGO = """
   \033[36m\033[1m██╗     ██╗   ██╗██╗   ██╗██╗  ██╗
   ██║     ██║   ██║██║   ██║╚██╗██╔╝
   ██║     ██║   ██║██║   ██║ ╚███╔╝
   ███████╗╚██████╔╝╚██████╔╝ ██╔██╗
   ╚══════╝ ╚═════╝  ╚═════╝  ╚═╝ ╚╝\033[0m
   \033[35m\033[1m        L o v e   W o r k i n g\033[0m
   \033[33m\033[1m          [ AI Core ]\033[0m
   \033[90m  ─────────────────────────────────────\033[0m
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(ASCII_LOGO, flush=True)
    logger.info("Starting LVV AI Core on %s:%s", AI_CORE_HOST, AI_CORE_PORT)
    get_conn()
    logger.info("Database initialized")

    from .config import _qwen_api_key, _tencent_api_key
    if not _qwen_api_key:
        logger.warning("QWEN_API_KEY is not set! AI features will not work.")
        logger.warning("Please edit .env and fill in QWEN_API_KEY")
        logger.warning("Get API Key: https://dashscope.console.aliyun.com/apiKey")
    else:
        logger.info("QWEN_API_KEY: %s...%s", _qwen_api_key[:4], _qwen_api_key[-4:])
    if not _tencent_api_key:
        logger.info("TENCENT_API_KEY not set (optional)")
    else:
        logger.info("TENCENT_API_KEY: %s...%s", _tencent_api_key[:4], _tencent_api_key[-4:])

    yield
    logger.info("Shutting down LVV AI Core...")


app = FastAPI(
    title="LVV AI Core",
    description="LVV 办公助手 - AI 核心服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(general.router)
app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(meeting.router)
app.include_router(literature.router)
app.include_router(polish.router)
app.include_router(ppt.router)
app.include_router(xlsx.router)
app.include_router(docx.router)
app.include_router(files.router)
app.include_router(skills.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=AI_CORE_HOST,
        port=AI_CORE_PORT,
        reload=True,
        log_level="info",
    )