"""GET /v1/models - 列出所有可用的Agent"""
import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_api_key
from app.schemas.openai import ModelListResponse, ModelObject
from app.models.agent import Agent

router = APIRouter()


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    result = await db.execute(select(Agent).where(Agent.status == "active"))
    agents = result.scalars().all()
    return ModelListResponse(
        data=[
            ModelObject(id=f"agent-{a.name}", owned_by="platform", created=int(time.time()))
            for a in agents
        ]
    )
