"""Agent管理API"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.agent import Agent, AgentVersion, agent_skills
from app.models.skill import Skill
from app.models.model_config import ModelConfig
from app.schemas.agent import AgentCreate, AgentUpdate, AgentOut, AgentVersionOut, AgentTestRequest
from app.services import agent_runner

router = APIRouter(prefix="/agents", tags=["agents"])


async def _set_skills(db: AsyncSession, agent: Agent, skill_ids: list[uuid.UUID]):
    await db.execute(delete(agent_skills).where(agent_skills.c.agent_id == agent.id))
    for sid in skill_ids:
        await db.execute(agent_skills.insert().values(agent_id=agent.id, skill_id=sid))


@router.get("", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).options(selectinload(Agent.skills), selectinload(Agent.model_config_rel)))
    return result.scalars().all()


@router.post("", response_model=AgentOut)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent = Agent(
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        max_loops=body.max_loops,
        model_config_id=body.model_config_id,
        model_override=body.model_override,
        risk_control=body.risk_control,
    )
    db.add(agent)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, f"Agent 名称 '{body.name}' 已存在")
    await _set_skills(db, agent, body.skill_ids)
    await db.commit()
    result = await db.execute(select(Agent).options(selectinload(Agent.skills), selectinload(Agent.model_config_rel)).where(Agent.id == agent.id))
    return result.scalar_one()


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: uuid.UUID, body: AgentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")

    # 保存历史版本
    av = AgentVersion(
        agent_id=agent.id,
        version=agent.version,
        system_prompt=agent.system_prompt,
        change_summary="用户更新",
    )
    db.add(av)

    for field, val in body.model_dump(exclude_none=True).items():
        if field == "skill_ids":
            continue
        setattr(agent, field, val)
    agent.version += 1

    if body.skill_ids is not None:
        await _set_skills(db, agent, body.skill_ids)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, f"Agent 名称 '{body.name}' 已存在")
    result = await db.execute(select(Agent).options(selectinload(Agent.skills), selectinload(Agent.model_config_rel)).where(Agent.id == agent.id))
    return result.scalar_one()


@router.delete("/{agent_id}")
async def delete_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)
    await db.commit()
    return {"ok": True}


@router.get("/{agent_id}/versions", response_model=list[AgentVersionOut])
async def get_agent_versions(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentVersion).where(AgentVersion.agent_id == agent_id).order_by(AgentVersion.version.desc())
    )
    return result.scalars().all()


@router.post("/{agent_id}/rollback/{version_id}", response_model=AgentOut)
async def rollback_agent(agent_id: uuid.UUID, version_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    a_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = a_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")

    v_result = await db.execute(select(AgentVersion).where(AgentVersion.id == version_id))
    ver = v_result.scalar_one_or_none()
    if ver is None:
        raise HTTPException(404, "Version not found")

    agent.system_prompt = ver.system_prompt
    agent.version += 1
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/test")
async def test_agent(agent_id: uuid.UUID, body: AgentTestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")

    mc_id = body.model_config_id or agent.model_config_id
    if mc_id:
        mc_result = await db.execute(select(ModelConfig).where(ModelConfig.id == mc_id))
    else:
        mc_result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    mc = mc_result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(500, "No model config available")

    output, trace_id, loop_steps = await agent_runner.run_agent(
        agent=agent, mc=mc, messages=body.messages, db=db
    )
    return {"output": output, "trace_id": trace_id, "loop_steps": loop_steps}
