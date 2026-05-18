"""Skill管理API"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.skill import Skill, SkillVersion, skill_tools
from app.models.model_config import ModelConfig
from app.models.user import User
from app.schemas.skill import (
    SkillCreate, SkillUpdate, SkillOut, SkillVersionOut, SkillTestRequest,
)
from app.services import skill_runner
from app.services.optimizer_svc import apply_skill_version

router = APIRouter(prefix="/skills", tags=["skills"])


async def _set_tools(db: AsyncSession, skill: Skill, tool_ids: list[uuid.UUID]):
    await db.execute(delete(skill_tools).where(skill_tools.c.skill_id == skill.id))
    for tid in tool_ids:
        await db.execute(skill_tools.insert().values(skill_id=skill.id, tool_id=tid))


@router.get("", response_model=list[SkillOut])
async def list_skills(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).options(selectinload(Skill.tools)))
    return result.scalars().all()


@router.post("", response_model=SkillOut)
async def create_skill(
    body: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = Skill(name=body.name, description=body.description, prompt=body.prompt, kb_namespaces=body.kb_namespaces)
    db.add(skill)
    await db.flush()
    await _set_tools(db, skill, body.tool_ids)
    await db.commit()
    result = await db.execute(select(Skill).options(selectinload(Skill.tools)).where(Skill.id == skill.id))
    return result.scalar_one()


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "Skill not found")
    return skill


@router.put("/{skill_id}", response_model=SkillOut)
async def update_skill(
    skill_id: uuid.UUID,
    body: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "Skill not found")

    # 保存历史版本
    sv = SkillVersion(
        skill_id=skill.id,
        version=skill.version,
        prompt=skill.prompt,
        change_summary=body.change_summary or "用户更新",
        created_by=current_user.username,
    )
    db.add(sv)

    for field, val in body.model_dump(exclude_none=True, exclude={"tool_ids", "kb_namespaces", "change_summary"}).items():
        setattr(skill, field, val)
    if body.kb_namespaces is not None:
        skill.kb_namespaces = body.kb_namespaces
    skill.version += 1

    if body.tool_ids is not None:
        await _set_tools(db, skill, body.tool_ids)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, f"Skill 名称 '{body.name}' 已存在")
    result = await db.execute(select(Skill).options(selectinload(Skill.tools)).where(Skill.id == skill.id))
    return result.scalar_one()


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "Skill not found")
    # 先清理关联记录，避免外键冲突
    await db.execute(delete(skill_tools).where(skill_tools.c.skill_id == skill_id))
    await db.execute(delete(SkillVersion).where(SkillVersion.skill_id == skill_id))
    await db.delete(skill)
    await db.commit()
    return {"ok": True}


# ── Versions ─────────────────────────────────────────────────────────

@router.post("/{skill_id}/versions/{version_id}/set-active", response_model=SkillOut)
async def set_active_version(
    skill_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """将指定版本固定为线上版本。"""
    result = await db.execute(select(Skill).options(selectinload(Skill.tools)).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "Skill not found")
    ver_result = await db.execute(select(SkillVersion).where(SkillVersion.id == version_id, SkillVersion.skill_id == skill_id))
    if ver_result.scalar_one_or_none() is None:
        raise HTTPException(404, "Version not found")
    skill.active_version_id = version_id
    await db.commit()
    await db.refresh(skill)
    return skill


@router.post("/{skill_id}/versions/unpin", response_model=SkillOut)
async def unpin_version(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """取消版本固定，恢复使用最新版本。"""
    result = await db.execute(select(Skill).options(selectinload(Skill.tools)).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "Skill not found")
    skill.active_version_id = None
    await db.commit()
    await db.refresh(skill)
    return skill


@router.delete("/{skill_id}/versions/{version_id}")
async def delete_skill_version(
    skill_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除指定历史版本（不可删除当前线上版本）。"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "Skill not found")
    if skill.active_version_id == version_id:
        raise HTTPException(400, "无法删除当前线上版本，请先切换或取消固定")
    ver_result = await db.execute(select(SkillVersion).where(SkillVersion.id == version_id, SkillVersion.skill_id == skill_id))
    ver = ver_result.scalar_one_or_none()
    if ver is None:
        raise HTTPException(404, "Version not found")
    await db.delete(ver)
    await db.commit()
    return {"ok": True}


@router.get("/{skill_id}/versions", response_model=list[SkillVersionOut])
async def get_skill_versions(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SkillVersion).where(SkillVersion.skill_id == skill_id).order_by(SkillVersion.version.desc())
    )
    return result.scalars().all()


@router.post("/{skill_id}/rollback/{version_id}", response_model=SkillOut)
async def rollback_skill(
    skill_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await apply_skill_version(skill_id, version_id, db)


# ── Test ──────────────────────────────────────────────────────────────

@router.post("/{skill_id}/test")
async def test_skill(
    skill_id: uuid.UUID,
    body: SkillTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, "Skill not found")

    mc_result = await db.execute(
        select(ModelConfig).where(ModelConfig.is_active == True).limit(1)
    )
    mc = mc_result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(500, "No model config available")

    output = await skill_runner.run_skill(skill=skill, messages=body.messages, mc=mc, db=db)
    return {"output": output}
