"""调用链路查询API"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.models.trace import Trace

router = APIRouter(prefix="/traces", tags=["traces"])


class TraceOut(BaseModel):
    id: uuid.UUID
    agent_name: str
    agent_version: int | None
    input: list
    output: str
    loop_steps: list
    total_loops: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    status: str
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[TraceOut])
async def list_traces(
    agent_name: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Trace).order_by(Trace.created_at.desc()).limit(limit)
    if agent_name:
        q = q.where(Trace.agent_name == agent_name)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{trace_id}", response_model=TraceOut)
async def get_trace(trace_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    from fastapi import HTTPException
    if trace is None:
        raise HTTPException(404, "Trace not found")
    return trace
