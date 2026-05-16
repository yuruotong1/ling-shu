"""知识库 API"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, distinct
from pydantic import BaseModel
from app.core.database import get_db
from app.models.kb import KbDocument, KbChunk, KbData

router = APIRouter(prefix="/kb", tags=["knowledge-base"])

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _split_chunks(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _score_chunk(chunk_content: str, keywords: list[str]) -> int:
    lower = chunk_content.lower()
    return sum(1 for kw in keywords if kw.lower() in lower)


# ---- Namespace ----

@router.get("/namespaces")
async def list_namespaces(db: AsyncSession = Depends(get_db)):
    doc_ns = await db.execute(select(distinct(KbDocument.namespace)))
    data_ns = await db.execute(select(distinct(KbData.namespace)))
    ns_set = set(doc_ns.scalars().all()) | set(data_ns.scalars().all())
    return sorted(ns_set)


@router.post("/{namespace}/register-tools")
async def register_kb_tools(namespace: str, db: AsyncSession = Depends(get_db)):
    from app.models.tool import Tool
    # 删除旧的分散工具（兼容旧数据）
    await db.execute(delete(Tool).where(Tool.kb_namespace == namespace, Tool.kb_operation != "all"))
    # 确保合并工具存在
    tool_name = f"{namespace}_知识库"
    existing = await db.execute(select(Tool).where(Tool.kb_namespace == namespace, Tool.kb_operation == "all"))
    if not existing.scalar_one_or_none():
        db.add(Tool(
            name=tool_name,
            description=f"操作知识库「{namespace}」：支持查询、新增、删除、列举知识条目",
            api_url="builtin",
            method="builtin",
            tool_type="builtin_kb",
            kb_namespace=namespace,
            kb_operation="all",
        ))
        await db.commit()
        return {"created": [tool_name]}
    await db.commit()
    return {"created": []}


class RenameNamespace(BaseModel):
    new_name: str


@router.delete("/{namespace}")
async def delete_namespace(namespace: str, db: AsyncSession = Depends(get_db)):
    from app.models.tool import Tool
    await db.execute(delete(KbChunk).where(KbChunk.namespace == namespace))
    await db.execute(delete(KbDocument).where(KbDocument.namespace == namespace))
    await db.execute(delete(KbData).where(KbData.namespace == namespace))
    await db.execute(delete(Tool).where(Tool.kb_namespace == namespace))
    await db.commit()
    return {"ok": True}


@router.post("/{namespace}/rename")
async def rename_namespace(namespace: str, body: RenameNamespace, db: AsyncSession = Depends(get_db)):
    new_name = body.new_name.strip()
    if not new_name or new_name == namespace:
        raise HTTPException(400, "新名称无效")
    # 迁移文档
    docs_result = await db.execute(select(KbDocument).where(KbDocument.namespace == namespace))
    for doc in docs_result.scalars().all():
        new_doc = KbDocument(namespace=new_name, filename=doc.filename, content=doc.content, chunk_count=doc.chunk_count)
        db.add(new_doc)
        await db.flush()
        chunks_result = await db.execute(select(KbChunk).where(KbChunk.document_id == doc.id))
        for c in chunks_result.scalars().all():
            db.add(KbChunk(document_id=new_doc.id, namespace=new_name, content=c.content, chunk_idx=c.chunk_idx))
    # 迁移键值
    kv_result = await db.execute(select(KbData).where(KbData.namespace == namespace))
    for kv in kv_result.scalars().all():
        existing = await db.execute(select(KbData).where(KbData.namespace == new_name, KbData.key == kv.key))
        if not existing.scalar_one_or_none():
            db.add(KbData(namespace=new_name, key=kv.key, value=kv.value))
    # 删除旧数据
    await db.execute(delete(KbChunk).where(KbChunk.namespace == namespace))
    await db.execute(delete(KbDocument).where(KbDocument.namespace == namespace))
    await db.execute(delete(KbData).where(KbData.namespace == namespace))
    # 同步更新工具：名称替换 + namespace 更新
    from app.models.tool import Tool
    tools_result = await db.execute(select(Tool).where(Tool.kb_namespace == namespace))
    for tool in tools_result.scalars().all():
        tool.kb_namespace = new_name
        tool.name = new_name + tool.name[len(namespace):]
        tool.description = tool.description.replace(f"知识库：{namespace}", f"知识库：{new_name}")
    await db.commit()
    return {"ok": True, "new_name": new_name}


# ---- Documents ----

@router.get("/{namespace}/documents")
async def list_documents(namespace: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KbDocument).where(KbDocument.namespace == namespace).order_by(KbDocument.created_at.desc())
    )
    docs = result.scalars().all()
    return [{"id": str(d.id), "filename": d.filename, "chunk_count": d.chunk_count,
             "created_at": d.created_at.isoformat()} for d in docs]


@router.post("/{namespace}/documents")
async def upload_document(
    namespace: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("gbk", errors="replace")

    chunks = _split_chunks(content)
    doc = KbDocument(
        namespace=namespace,
        filename=file.filename or "untitled",
        content=content,
        chunk_count=len(chunks),
    )
    db.add(doc)
    await db.flush()

    for idx, chunk_text in enumerate(chunks):
        db.add(KbChunk(document_id=doc.id, namespace=namespace, content=chunk_text, chunk_idx=idx))

    await db.commit()
    return {"id": str(doc.id), "filename": doc.filename, "chunk_count": doc.chunk_count}


@router.delete("/{namespace}/documents/{doc_id}")
async def delete_document(namespace: str, doc_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KbDocument).where(KbDocument.id == doc_id, KbDocument.namespace == namespace))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Document not found")
    await db.delete(doc)
    await db.commit()
    return {"ok": True}


# ---- Search ----

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/{namespace}/search")
async def search(namespace: str, body: SearchRequest, db: AsyncSession = Depends(get_db)):
    keywords = [w for w in body.query.split() if w]
    if not keywords:
        return {"results": []}

    result = await db.execute(select(KbChunk).where(KbChunk.namespace == namespace))
    chunks = result.scalars().all()

    scored = [(c, _score_chunk(c.content, keywords)) for c in chunks]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    doc_ids = {c.document_id for c, _ in scored[:body.top_k]}
    doc_result = await db.execute(select(KbDocument).where(KbDocument.id.in_(doc_ids)))
    doc_map = {d.id: d.filename for d in doc_result.scalars().all()}

    return {
        "results": [
            {
                "content": c.content,
                "source": doc_map.get(c.document_id, ""),
                "score": round(s / max(len(keywords), 1), 2),
                "chunk_idx": c.chunk_idx,
            }
            for c, s in scored[:body.top_k]
        ]
    }


# ---- Key-Value ----

class KvWrite(BaseModel):
    key: str
    value: str


@router.get("/{namespace}/data")
async def list_data(namespace: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KbData).where(KbData.namespace == namespace).order_by(KbData.created_at.desc())
    )
    return [{"id": str(d.id), "key": d.key, "value": d.value, "created_at": d.created_at.isoformat()}
            for d in result.scalars().all()]


@router.post("/{namespace}/data")
async def write_data(namespace: str, body: KvWrite, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(KbData).where(KbData.namespace == namespace, KbData.key == body.key))
    item = existing.scalar_one_or_none()
    if item:
        item.value = body.value
    else:
        item = KbData(namespace=namespace, key=body.key, value=body.value)
        db.add(item)
    await db.commit()
    return {"key": item.key, "value": item.value}


@router.get("/{namespace}/data/{key}")
async def get_data(namespace: str, key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KbData).where(KbData.namespace == namespace, KbData.key == key))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Key not found")
    return {"key": item.key, "value": item.value}


@router.delete("/{namespace}/data/{key}")
async def delete_data(namespace: str, key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KbData).where(KbData.namespace == namespace, KbData.key == key))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Key not found")
    await db.delete(item)
    await db.commit()
    return {"ok": True}
