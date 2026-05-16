"""Tool管理API"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.tool import Tool
from app.schemas.tool import ToolCreate, ToolUpdate, ToolOut, ToolTestRequest
from app.services.tool_runner import run_tool

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolOut])
async def list_tools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool))
    return result.scalars().all()


@router.post("", response_model=ToolOut)
async def create_tool(body: ToolCreate, db: AsyncSession = Depends(get_db)):
    tool = Tool(**body.model_dump())
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get("/{tool_id}", response_model=ToolOut)
async def get_tool(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    return tool


@router.put("/{tool_id}", response_model=ToolOut)
async def update_tool(tool_id: uuid.UUID, body: ToolUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(tool, field, val)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.delete("/{tool_id}")
async def delete_tool(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    await db.delete(tool)
    await db.commit()
    return {"ok": True}


@router.post("/{tool_id}/test")
async def test_tool(tool_id: uuid.UUID, body: ToolTestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(404, "Tool not found")
    try:
        output = await run_tool(tool, body.params)
        tool.call_count += 1
        await db.commit()
        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "error": str(e)}
