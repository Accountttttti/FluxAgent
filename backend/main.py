from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import cron
import mcp_loader
from chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时把 mcp.json 里的外部工具加载进全局工具表
    await mcp_loader.load_all()
    # 启动定时任务后台线程
    cron.cron_service.start()
    yield


app = FastAPI(title="FluxAgent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
