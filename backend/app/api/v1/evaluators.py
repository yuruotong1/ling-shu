"""评估器 + 数据集管理API"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.evaluator import Evaluator
from app.models.dataset import EvaluationSet, EvaluationItem
from app.schemas.evaluator import (
    EvaluatorCreate, EvaluatorUpdate, EvaluatorOut,
    EvalSetCreate, EvalItemCreate, EvalSetOut, EvalItemOut,
)

router = APIRouter(tags=["evaluators"])

# ---- 评估器 ----

@router.get("/evaluators", response_model=list[EvaluatorOut])
async def list_evaluators(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Evaluator))
    return result.scalars().all()


@router.post("/evaluators", response_model=EvaluatorOut)
async def create_evaluator(body: EvaluatorCreate, db: AsyncSession = Depends(get_db)):
    ev = Evaluator(**body.model_dump())
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


@router.put("/evaluators/{ev_id}", response_model=EvaluatorOut)
async def update_evaluator(ev_id: uuid.UUID, body: EvaluatorUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Evaluator).where(Evaluator.id == ev_id))
    ev = result.scalar_one_or_none()
    if ev is None:
        raise HTTPException(404, "Evaluator not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(ev, field, val)
    await db.commit()
    await db.refresh(ev)
    return ev


@router.delete("/evaluators/{ev_id}")
async def delete_evaluator(ev_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Evaluator).where(Evaluator.id == ev_id))
    ev = result.scalar_one_or_none()
    if ev is None:
        raise HTTPException(404, "Evaluator not found")
    await db.delete(ev)
    await db.commit()
    return {"ok": True}


# ---- 评估集 ----

@router.get("/evaluation-sets", response_model=list[EvalSetOut])
async def list_eval_sets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationSet))
    sets = result.scalars().all()
    out = []
    for s in sets:
        count_result = await db.execute(
            select(func.count()).where(EvaluationItem.set_id == s.id)
        )
        count = count_result.scalar_one()
        d = EvalSetOut.model_validate(s)
        d.item_count = count
        out.append(d)
    return out


@router.post("/evaluation-sets", response_model=EvalSetOut)
async def create_eval_set(body: EvalSetCreate, db: AsyncSession = Depends(get_db)):
    s = EvaluationSet(**body.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    d = EvalSetOut.model_validate(s)
    d.item_count = 0
    return d


@router.delete("/evaluation-sets/{set_id}")
async def delete_eval_set(set_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationSet).where(EvaluationSet.id == set_id))
    s = result.scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "Evaluation set not found")
    await db.delete(s)
    await db.commit()
    return {"ok": True}


@router.get("/evaluation-sets/{set_id}/items", response_model=list[EvalItemOut])
async def list_eval_items(set_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationItem).where(EvaluationItem.set_id == set_id))
    return result.scalars().all()


@router.post("/evaluation-sets/{set_id}/items", response_model=EvalItemOut)
async def add_eval_item(set_id: uuid.UUID, body: EvalItemCreate, db: AsyncSession = Depends(get_db)):
    item = EvaluationItem(set_id=set_id, **body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/evaluation-sets/{set_id}/items/{item_id}")
async def delete_eval_item(set_id: uuid.UUID, item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationItem).where(EvaluationItem.id == item_id, EvaluationItem.set_id == set_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Item not found")
    await db.delete(item)
    await db.commit()
    return {"ok": True}
