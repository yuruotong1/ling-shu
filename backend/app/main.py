from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import (
    chat, openai_models, agents, skills, tools,
    model_configs, evaluators, experiments, traces, kb, users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import init_db
    await init_db()
    yield


app = FastAPI(
    title="灵枢引擎",
    description="评估驱动优化的AI Agent生产平台",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI兼容接口
app.include_router(chat.router, prefix="/v1")
app.include_router(openai_models.router, prefix="/v1")

# 认证 & 用户管理
app.include_router(users.router, prefix="/api/v1")

# 管理API
app.include_router(agents.router, prefix="/api/v1")
app.include_router(skills.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(model_configs.router, prefix="/api/v1")
app.include_router(evaluators.router, prefix="/api/v1")
app.include_router(experiments.router, prefix="/api/v1")
app.include_router(traces.router, prefix="/api/v1")
app.include_router(kb.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "灵枢引擎", "version": "1.1.0"}
