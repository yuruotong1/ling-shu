"""OpenAI兼容的聊天接口：POST /v1/chat/completions"""
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_api_key
from app.schemas.openai import ChatRequest, ChatResponse, ChatChoice, ChatMessage, ChatUsage
from app.models.agent import Agent
from app.models.model_config import ModelConfig
from app.services import agent_runner, model_client

router = APIRouter()


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    model_name = request.model

    agent_result = await db.execute(select(Agent).where(Agent.name == model_name, Agent.status == "active"))
    agent = agent_result.scalar_one_or_none()

    if agent is not None:
        mc_id = agent.model_config_id
        if mc_id:
            mc_result = await db.execute(select(ModelConfig).where(ModelConfig.id == mc_id))
        else:
            mc_result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
        mc = mc_result.scalar_one_or_none()
        if mc is None:
            raise HTTPException(status_code=500, detail="No active model config found")

        messages_dicts = [m.model_dump(exclude_none=True) for m in request.messages]
        output, trace_id, _ = await agent_runner.run_agent(
            agent=agent,
            mc=mc,
            messages=messages_dicts,
            db=db,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=model_name,
            choices=[ChatChoice(message=ChatMessage(role="assistant", content=output))],
            usage=ChatUsage(),
            trace_id=trace_id,
        )
    else:
        # 透传到配置的模型
        result = await db.execute(
            select(ModelConfig).where(ModelConfig.is_active == True).limit(1)
        )
        mc = result.scalar_one_or_none()
        if mc is None:
            raise HTTPException(status_code=500, detail="No active model config found")

        messages_dicts = [m.model_dump(exclude_none=True) for m in request.messages]
        raw = await model_client.chat_completion(
            mc=mc,
            messages=messages_dicts,
            model=model_name,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        choice = raw["choices"][0]
        usage = raw.get("usage", {})
        return ChatResponse(
            id=raw.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
            created=raw.get("created", int(time.time())),
            model=model_name,
            choices=[ChatChoice(
                message=ChatMessage(
                    role=choice["message"]["role"],
                    content=choice["message"].get("content"),
                ),
                finish_reason=choice.get("finish_reason", "stop"),
            )],
            usage=ChatUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
        )
