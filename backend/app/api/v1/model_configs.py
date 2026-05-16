"""模型配置管理API"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.model_config import ModelConfig
from app.schemas.model_config import ModelConfigCreate, ModelConfigUpdate, ModelConfigOut
from app.services.model_client import chat_completion

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


@router.get("", response_model=list[ModelConfigOut])
async def list_model_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig))
    return result.scalars().all()


@router.post("", response_model=ModelConfigOut)
async def create_model_config(body: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    mc = ModelConfig(
        name=body.name,
        provider=body.provider,
        endpoint=body.endpoint,
        api_key_encrypted=body.api_key,
        default_model=body.default_model,
        default_params=body.default_params,
    )
    db.add(mc)
    await db.commit()
    await db.refresh(mc)
    return mc


@router.get("/{mc_id}", response_model=ModelConfigOut)
async def get_model_config(mc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == mc_id))
    mc = result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(404, "Model config not found")
    return mc


@router.put("/{mc_id}", response_model=ModelConfigOut)
async def update_model_config(mc_id: uuid.UUID, body: ModelConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == mc_id))
    mc = result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(404, "Model config not found")
    data = body.model_dump(exclude_none=True)
    if "api_key" in data:
        mc.api_key_encrypted = data.pop("api_key")
    for field, val in data.items():
        setattr(mc, field, val)
    await db.commit()
    await db.refresh(mc)
    return mc


@router.delete("/{mc_id}")
async def delete_model_config(mc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == mc_id))
    mc = result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(404, "Model config not found")
    await db.delete(mc)
    await db.commit()
    return {"ok": True}


@router.post("/{mc_id}/test")
async def test_model_config(mc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    import httpx

    result = await db.execute(select(ModelConfig).where(ModelConfig.id == mc_id))
    mc = result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(404, "Model config not found")

    test_url = mc.endpoint.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {mc.api_key_encrypted or ''}",
    }
    payload = {
        "model": mc.default_model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(test_url, json=payload, headers=headers)
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {"success": True, "model": mc.default_model, "response": content}
    except httpx.ConnectError:
        return {"success": False, "error": f"无法连接到 {mc.endpoint}，请检查地址"}
    except httpx.TimeoutException:
        return {"success": False, "error": "连接超时，请检查地址或网络"}
    except (KeyError, IndexError):
        try:
            err_msg = data.get("error", {}).get("message") or str(data)
        except Exception:
            err_msg = resp.text[:300]
        return {"success": False, "error": err_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}
