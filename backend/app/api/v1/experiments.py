"""实验管理API：创建实验、运行评估、版本对比、自动迭代"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.experiment import Experiment, ExperimentResult
from app.models.skill import Skill, SkillVersion
from app.schemas.experiment import ExperimentCreate, ExperimentOut, ExperimentResultOut
from app.schemas.skill import SkillVersionOut
from app.services.evaluator_svc import run_experiment
from app.services.optimizer_svc import optimize_skill

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentOut])
async def list_experiments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Experiment).order_by(Experiment.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ExperimentOut)
async def create_experiment(body: ExperimentCreate, db: AsyncSession = Depends(get_db)):
    exp = Experiment(**body.model_dump())
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    return exp


@router.get("/{exp_id}", response_model=ExperimentOut)
async def get_experiment(exp_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Experiment).where(Experiment.id == exp_id))
    exp = result.scalar_one_or_none()
    if exp is None:
        raise HTTPException(404, "Experiment not found")
    return exp


@router.post("/{exp_id}/run")
async def run_experiment_api(
    exp_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Experiment).where(Experiment.id == exp_id))
    exp = result.scalar_one_or_none()
    if exp is None:
        raise HTTPException(404, "Experiment not found")
    if exp.status == "running":
        raise HTTPException(400, "Experiment already running")

    background_tasks.add_task(run_experiment, exp_id, db)
    return {"message": "Experiment started", "experiment_id": str(exp_id)}


@router.get("/{exp_id}/results", response_model=list[ExperimentResultOut])
async def get_experiment_results(exp_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ExperimentResult).where(ExperimentResult.experiment_id == exp_id)
    )
    results = result.scalars().all()
    out = []
    for r in results:
        d = ExperimentResultOut.model_validate(r)
        if r.item:
            d.input = r.item.input
            d.reference_output = r.item.reference_output
        out.append(d)
    return out


@router.post("/{exp_id}/optimize-skill")
async def trigger_skill_optimization(
    exp_id: uuid.UUID,
    skill_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    instruction: str = "",
    db: AsyncSession = Depends(get_db),
):
    """触发AI自动优化Skill，基于本实验的失败样本"""
    result = await db.execute(select(Experiment).where(Experiment.id == exp_id))
    exp = result.scalar_one_or_none()
    if exp is None:
        raise HTTPException(404, "Experiment not found")
    if exp.status != "completed":
        raise HTTPException(400, "Experiment must be completed first")

    new_ver = await optimize_skill(skill_id, exp_id, db, instruction)
    if new_ver is None:
        raise HTTPException(500, "Optimization failed or no improvement found")

    return SkillVersionOut.model_validate(new_ver)


@router.delete("/{exp_id}")
async def delete_experiment(exp_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Experiment).where(Experiment.id == exp_id))
    exp = result.scalar_one_or_none()
    if exp is None:
        raise HTTPException(404, "Experiment not found")
    await db.delete(exp)
    await db.commit()
    return {"ok": True}
