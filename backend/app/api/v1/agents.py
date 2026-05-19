"""Agent管理API"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.agent import Agent, AgentVersion, agent_skills
from app.models.skill import Skill
from app.models.model_config import ModelConfig
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentUpdate, AgentOut, AgentVersionOut, AgentTestRequest, ResponseFormatUpdate
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
    result = await db.execute(select(Agent).options(selectinload(Agent.skills), selectinload(Agent.model_config_rel)).where(Agent.id == agent_id))
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
        skills_snapshot=[{"id": str(s.id), "name": s.name, "description": s.description} for s in (agent.skills or [])],
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


# ── Response Format ────────────────────────────────────────────────────

@router.get("/{agent_id}/response-format")
async def get_response_format(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return {
        "agent_id": agent_id,
        "response_format": agent.response_format,
        "response_format_locked": agent.response_format_locked,
    }


@router.put("/{agent_id}/response-format")
async def update_response_format(
    agent_id: uuid.UUID,
    body: ResponseFormatUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")

    if body.response_format is not None:
        import jsonschema
        try:
            jsonschema.Draft7Validator.check_schema(body.response_format)
        except jsonschema.SchemaError as e:
            raise HTTPException(400, f"无效的 JSON Schema：{e.message}")
        agent.response_format = body.response_format
    elif body.response_format is None and body.response_format_locked is None:
        agent.response_format = None

    if body.response_format_locked is not None:
        agent.response_format_locked = body.response_format_locked

    await db.commit()
    return {
        "agent_id": agent_id,
        "response_format": agent.response_format,
        "response_format_locked": agent.response_format_locked,
    }


@router.post("/{agent_id}/response-format/test")
async def test_response_format(
    agent_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """用示例数据测试 JSON Schema 是否合法并能否通过验证。"""
    schema = body.get("schema")
    data = body.get("data")
    if schema is None:
        raise HTTPException(400, "Schema 不能为空")
    import jsonschema
    try:
        jsonschema.validate(data, schema)
        return {"valid": True}
    except jsonschema.ValidationError as e:
        return {"valid": False, "error": e.message}
    except jsonschema.SchemaError as e:
        return {"valid": False, "error": f"无效的 JSON Schema：{e.message}"}


@router.post("/{agent_id}/response-format/generate")
async def generate_response_format(
    agent_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """根据自然语言描述，调用大模型生成 JSON Schema。"""
    description = body.get("description", "")
    if not description:
        raise HTTPException(400, "描述不能为空")

    mc_result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    mc = mc_result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(500, "No model config available")

    system_prompt = (
        "你是一个 JSON Schema 生成专家。根据用户的自然语言描述，生成一个合法的 JSON Schema。\n"
        "要求：\n"
        "1. 只输出 JSON Schema 本身，不要输出任何解释性文字\n"
        "2. 必须包含 type='object' 和 properties\n"
        "3. 为每个字段添加 description\n"
        "4. 合理设置 required 字段\n"
        "5. 输出必须是合法的 JSON 格式"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请为以下需求生成 JSON Schema：\n{description}"},
    ]

    result = await model_client.chat_completion(mc=mc, messages=messages, temperature=0.2)
    content = result["choices"][0]["message"].get("content", "")

    # 尝试从响应中提取 JSON
    import json
    import re
    schema = None
    # 先尝试直接解析
    try:
        schema = json.loads(content)
    except Exception:
        pass
    # 再尝试提取 ```json 代码块
    if schema is None:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            try:
                schema = json.loads(m.group(1))
            except Exception:
                pass
    # 最后尝试提取 {...}
    if schema is None:
        m = re.search(r"(\{[\s\S]*\})", content)
        if m:
            try:
                schema = json.loads(m.group(1))
            except Exception:
                pass

    if schema is None:
        raise HTTPException(500, "模型未返回合法的 JSON Schema，请重试或手动编写")

    return {"schema": schema}


@router.post("/{agent_id}/versions/{version_id}/set-active", response_model=AgentOut)
async def set_active_version(
    agent_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """将指定版本固定为线上版本。"""
    result = await db.execute(select(Agent).options(selectinload(Agent.skills), selectinload(Agent.model_config_rel)).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")
    # 验证版本存在
    ver_result = await db.execute(select(AgentVersion).where(AgentVersion.id == version_id, AgentVersion.agent_id == agent_id))
    if ver_result.scalar_one_or_none() is None:
        raise HTTPException(404, "Version not found")
    agent.active_version_id = version_id
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/versions/unpin", response_model=AgentOut)
async def unpin_version(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """取消版本固定，恢复使用最新版本。"""
    result = await db.execute(select(Agent).options(selectinload(Agent.skills), selectinload(Agent.model_config_rel)).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")
    agent.active_version_id = None
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}/versions/{version_id}")
async def delete_agent_version(
    agent_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除指定历史版本（不可删除当前线上版本）。"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found")
    if agent.active_version_id == version_id:
        raise HTTPException(400, "无法删除当前线上版本，请先切换或取消固定")
    ver_result = await db.execute(select(AgentVersion).where(AgentVersion.id == version_id, AgentVersion.agent_id == agent_id))
    ver = ver_result.scalar_one_or_none()
    if ver is None:
        raise HTTPException(404, "Version not found")
    await db.delete(ver)
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
    result = await db.execute(select(Agent).options(selectinload(Agent.skills)).where(Agent.id == agent_id))
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

    session_id = body.session_id
    turn_index = 0

    if session_id:
        # 基于已有会话继续
        turns_result = await db.execute(
            select(Trace).where(Trace.session_id == session_id).order_by(Trace.turn_index)
        )
        turns = turns_result.scalars().all()
        if turns:
            turn_index = max(t.turn_index for t in turns) + 1
        # 客户端自行维护对话历史，后端不再重建，直接使用传入的 messages
        output, trace_id, loop_steps, session_id = await agent_runner.run_agent(
            agent=agent, mc=mc, messages=body.messages, db=db,
            session_id=session_id, turn_index=turn_index,
        )
        return {"output": output, "trace_id": trace_id, "loop_steps": loop_steps, "session_id": str(session_id)}

    # 新建会话
    if session_id is None:
        session_id = uuid.uuid4()

    output, trace_id, loop_steps, session_id = await agent_runner.run_agent(
        agent=agent, mc=mc, messages=body.messages, db=db,
        session_id=session_id, turn_index=turn_index,
    )
    return {"output": output, "trace_id": trace_id, "loop_steps": loop_steps, "session_id": str(session_id)}
