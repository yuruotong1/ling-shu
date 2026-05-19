"""调用链路 & 多轮对话 API"""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.trace import Trace
from app.models.agent import Agent
from app.models.model_config import ModelConfig
from app.models.user import User
from app.services import agent_runner

router = APIRouter(prefix="/traces", tags=["traces"])


class TraceOut(BaseModel):
    id: uuid.UUID
    agent_name: str
    agent_version: int | None
    agent_id: uuid.UUID | None = None
    input: list
    output: str
    loop_steps: list
    total_loops: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    status: str
    error_message: str | None
    session_id: uuid.UUID | None = None
    turn_index: int = 0
    user_rating: str | None = None
    reference_output: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class RatingUpdate(BaseModel):
    user_rating: Literal["good", "bad"] | None = None
    reference_output: str | None = None


class ContinueRequest(BaseModel):
    user_message: str


class OptimizeRequest(BaseModel):
    target_type: Literal["agent", "skill"]
    target_id: uuid.UUID
    instruction: str = ""


@router.get("", response_model=list[TraceOut])
async def list_traces(
    agent_name: str | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    q = select(Trace).order_by(Trace.created_at.desc()).limit(limit)
    if agent_name:
        q = q.where(Trace.agent_name == agent_name)
    if agent_id:
        q = q.where(Trace.agent_id == agent_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{trace_id}", response_model=TraceOut)
async def get_trace(trace_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(404, "Trace not found")
    return trace


@router.delete("/{trace_id}")
async def delete_trace(
    trace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(404, "Trace not found")
    await db.delete(trace)
    await db.commit()
    return {"ok": True}


class BatchDeleteRequest(BaseModel):
    trace_ids: list[uuid.UUID]


@router.post("/batch-delete")
async def batch_delete_traces(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    from sqlalchemy import delete as sqla_delete
    await db.execute(sqla_delete(Trace).where(Trace.id.in_(body.trace_ids)))
    await db.commit()
    return {"deleted": len(body.trace_ids)}


@router.patch("/{trace_id}/rating", response_model=TraceOut)
async def update_rating(
    trace_id: uuid.UUID,
    body: RatingUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """为某一轮输出打分（good/bad）+ 填写期望输出。"""
    result = await db.execute(select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(404, "Trace not found")
    if body.user_rating is not None:
        trace.user_rating = body.user_rating
    if body.reference_output is not None:
        trace.reference_output = body.reference_output
    await db.commit()
    await db.refresh(trace)
    return trace


# ── 多轮会话 ──────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}", response_model=list[TraceOut])
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取某个多轮会话的所有 Trace，按 turn_index 排序。"""
    result = await db.execute(
        select(Trace).where(Trace.session_id == session_id).order_by(Trace.turn_index)
    )
    turns = result.scalars().all()
    if not turns:
        raise HTTPException(404, "Session not found")
    return turns


@router.post("/{trace_id}/continue", response_model=TraceOut)
async def continue_trace(
    trace_id: uuid.UUID,
    body: ContinueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    从单次 Trace 或已有会话继续对话：
    - 若 trace 无 session_id，先为其分配一个新的 session_id（turn_index=0）
    - 然后基于完整历史运行 Agent，新 Trace 追加到会话末尾
    """
    result = await db.execute(select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(404, "Trace not found")

    # 优先用 agent_id，兜底用 agent_name（兼容旧 Trace 记录）
    agent = None
    if trace.agent_id:
        r = await db.execute(select(Agent).where(Agent.id == trace.agent_id))
        agent = r.scalar_one_or_none()
    if agent is None and trace.agent_name:
        r = await db.execute(select(Agent).where(Agent.name == trace.agent_name))
        agent = r.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, f"找不到名称为 '{trace.agent_name}' 的 Agent，请先确认该 Agent 存在")

    # 确保有 session_id
    if trace.session_id is None:
        session_id = uuid.uuid4()
        trace.session_id = session_id
        trace.turn_index = 0
        await db.commit()
    else:
        session_id = trace.session_id

    # 获取该会话所有已有轮次，构建历史消息
    turns_result = await db.execute(
        select(Trace).where(Trace.session_id == session_id).order_by(Trace.turn_index)
    )
    turns = turns_result.scalars().all()
    next_turn_index = max(t.turn_index for t in turns) + 1

    # 重建多轮消息历史（取每轮最后一条 user 消息）
    history: list[dict] = []
    for t in turns:
        user_msg = next((m for m in reversed(t.input or []) if m.get("role") == "user"), None)
        history.append({"role": "user", "content": user_msg.get("content", "") if user_msg else ""})
        history.append({"role": "assistant", "content": t.output})
    history.append({"role": "user", "content": body.user_message})

    mc_result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    mc = mc_result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(500, "No model config available")

    output, new_trace_id, loop_steps, _ = await agent_runner.run_agent(
        agent=agent,
        mc=mc,
        messages=history,
        db=db,
        session_id=session_id,
        turn_index=next_turn_index,
    )

    # 返回新建的 Trace
    new_trace_result = await db.execute(
        select(Trace).where(Trace.id == uuid.UUID(new_trace_id))
    )
    return new_trace_result.scalar_one()


# ── 从对话链路优化 Agent / Skill ──────────────────────────────────────

@router.post("/sessions/{session_id}/optimize")
async def optimize_from_session(
    session_id: uuid.UUID,
    body: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """基于多轮会话（含评分和期望输出）一键优化 Agent 或 Skill，生成新版本。"""
    turns_result = await db.execute(
        select(Trace).where(Trace.session_id == session_id).order_by(Trace.turn_index)
    )
    turns = turns_result.scalars().all()
    if not turns:
        raise HTTPException(404, "Session not found")

    turn_data = [
        {
            "input": (t.input[-1].get("content", "") if t.input else ""),
            "output": t.output,
            "rating": t.user_rating,
            "reference": t.reference_output,
        }
        for t in turns
    ]

    from app.services.optimizer_svc import optimize_skill_from_conversation, optimize_agent_from_conversation

    if body.target_type == "skill":
        new_ver = await optimize_skill_from_conversation(
            body.target_id, turn_data, db, body.instruction
        )
        if new_ver is None:
            raise HTTPException(400, "优化未产生新版本（提示词无变化或无可用模型）")
        return {
            "type": "skill_version",
            "version": new_ver.version,
            "id": str(new_ver.id),
            "prompt": new_ver.prompt,
            "change_summary": new_ver.change_summary,
        }
    else:
        new_ver = await optimize_agent_from_conversation(
            body.target_id, turn_data, db, body.instruction
        )
        if new_ver is None:
            raise HTTPException(400, "优化未产生新版本（提示词无变化或无可用模型）")
        return {
            "type": "agent_version",
            "version": new_ver.version,
            "id": str(new_ver.id),
            "system_prompt": new_ver.system_prompt,
            "change_summary": new_ver.change_summary,
        }


@router.post("/{trace_id}/optimize")
async def optimize_from_single_trace(
    trace_id: uuid.UUID,
    body: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """单次 Trace 直接优化（无需多轮会话）。"""
    result = await db.execute(select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if trace is None:
        raise HTTPException(404, "Trace not found")

    turn_data = [{
        "input": (trace.input[-1].get("content", "") if trace.input else ""),
        "output": trace.output,
        "rating": trace.user_rating,
        "reference": trace.reference_output,
    }]

    from app.services.optimizer_svc import optimize_skill_from_conversation, optimize_agent_from_conversation

    if body.target_type == "skill":
        new_ver = await optimize_skill_from_conversation(body.target_id, turn_data, db, body.instruction)
    else:
        new_ver = await optimize_agent_from_conversation(body.target_id, turn_data, db, body.instruction)

    if new_ver is None:
        raise HTTPException(400, "优化未产生新版本")
    return {"type": body.target_type + "_version", "version": new_ver.version, "id": str(new_ver.id)}
