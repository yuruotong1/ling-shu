"""工具执行器：HTTP多步骤工具 + 内置知识库操作 + Plugin 插件"""
import re
import json
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.tool import Tool
from app.plugin_engine import PluginEngine

# KB 内置操作定义
_KB_STEP_DEFS = [
    {
        "op": "search",
        "name": "查询",
        "description": "根据关键词检索知识库内容，返回最相关的条目",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询内容"},
                "top_k": {"type": "integer", "description": "返回结果数量，默认5"},
            },
            "required": ["query"],
        },
    },
    {
        "op": "add",
        "name": "新增",
        "description": "向知识库中写入新的知识条目（键值对形式）",
        "schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "知识条目的键名"},
                "value": {"type": "string", "description": "知识条目的内容"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "op": "delete",
        "name": "删除",
        "description": "从知识库中删除指定键名的知识条目",
        "schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "要删除的知识条目键名"},
            },
            "required": ["key"],
        },
    },
    {
        "op": "list",
        "name": "列举",
        "description": "列出知识库中所有知识条目",
        "schema": {"type": "object", "properties": {}},
    },
]


def _sanitize_fn_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized[:64] or "_tool"


def _kb_fn_name(tool_id, op: str) -> str:
    short_id = str(tool_id).replace("-", "")[:8]
    return f"kb_{op}_{short_id}"


def tool_to_function_defs(tool: Tool) -> list[dict]:
    """返回工具对应的所有 function definitions（可能多个步骤）"""
    if tool.tool_type == "builtin_kb":
        ns = tool.kb_namespace or ""
        return [
            {
                "type": "function",
                "function": {
                    "name": _kb_fn_name(tool.id, sd["op"]),
                    "description": f"{sd['description']}（知识库：{ns}）",
                    "parameters": sd["schema"],
                },
            }
            for sd in _KB_STEP_DEFS
        ]

    if tool.tool_type == "plugin":
        # plugin 类型：从 plugin_functions 或动态加载获取
        try:
            funcs = tool.plugin_functions or []
            if not funcs:
                funcs = PluginEngine.get_plugin_tools(tool)
            return [
                {
                    "type": "function",
                    "function": {
                        "name": _sanitize_fn_name(f["name"]),
                        "description": f.get("description", ""),
                        "parameters": f.get("schema") or {"type": "object", "properties": {}},
                    },
                }
                for f in funcs
            ]
        except Exception:
            # 插件未加载或损坏时返回占位，避免阻塞整体流程
            return [
                {
                    "type": "function",
                    "function": {
                        "name": _sanitize_fn_name(tool.name),
                        "description": f"{tool.description}（插件暂不可用）",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]

    steps = tool.steps or []
    if steps:
        return [
            {
                "type": "function",
                "function": {
                    "name": _sanitize_fn_name(s.get("name") or tool.name),
                    "description": s.get("description", ""),
                    "parameters": s.get("input_schema") or {"type": "object", "properties": {}},
                },
            }
            for s in steps
        ]

    # 向后兼容：无 steps 时使用 Tool 自身字段
    return [tool_to_function_def(tool)]


def tool_to_function_def(tool: Tool) -> dict:
    """单函数定义（向后兼容）"""
    return {
        "type": "function",
        "function": {
            "name": _sanitize_fn_name(tool.name),
            "description": tool.description,
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }


async def _run_builtin_kb_op(ns: str, op: str, params: dict, db: AsyncSession) -> str:
    from app.models.kb import KbChunk, KbData

    if op == "search":
        query = params.get("query", "")
        top_k = int(params.get("top_k", 5))
        keywords = [w for w in query.split() if w]
        if not keywords:
            return "未找到相关内容"
        result = await db.execute(select(KbChunk).where(KbChunk.namespace == ns))
        chunks = result.scalars().all()
        scored = [(c, sum(1 for kw in keywords if kw.lower() in c.content.lower())) for c in chunks]
        scored = [(c, s) for c, s in scored if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        if not scored:
            return f'知识库 [{ns}] 中未找到与 "{query}" 相关的内容'
        return "\n---\n".join(c.content for c, _ in scored[:top_k])

    elif op == "add":
        key = params.get("key", "").strip()
        value = params.get("value", "")
        if not key:
            return "错误：key 不能为空"
        existing = await db.execute(select(KbData).where(KbData.namespace == ns, KbData.key == key))
        item = existing.scalar_one_or_none()
        if item:
            item.value = value
        else:
            item = KbData(namespace=ns, key=key, value=value)
            db.add(item)
        await db.commit()
        return f"已写入：{key}"

    elif op == "delete":
        key = params.get("key", "").strip()
        if not key:
            return "错误：key 不能为空"
        result = await db.execute(select(KbData).where(KbData.namespace == ns, KbData.key == key))
        item = result.scalar_one_or_none()
        if not item:
            return f"未找到：{key}"
        await db.delete(item)
        await db.commit()
        return f"已删除：{key}"

    elif op == "list":
        result = await db.execute(select(KbData).where(KbData.namespace == ns))
        items = result.scalars().all()
        if not items:
            return f"知识库 [{ns}] 为空"
        return "\n".join(f"{item.key}：{item.value}" for item in items)

    return f"未知操作：{op}"


async def _run_http_step(step: dict, params: dict) -> str:
    headers: dict = {"Content-Type": "application/json"}
    auth = step.get("auth_config") or {}
    if auth.get("type") == "bearer":
        headers["Authorization"] = f"Bearer {auth.get('token', '')}"
    elif auth.get("type") == "apikey":
        headers[auth.get("key_name", "X-API-Key")] = auth.get("key_value", "")

    method = (step.get("method") or "POST").upper()
    url = step.get("api_url", "")
    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            resp = await client.get(url, params=params, headers=headers)
        elif method == "POST":
            resp = await client.post(url, json=params, headers=headers)
        elif method == "PUT":
            resp = await client.put(url, json=params, headers=headers)
        elif method == "DELETE":
            resp = await client.delete(url, params=params, headers=headers)
        else:
            resp = await client.post(url, json=params, headers=headers)
    try:
        return json.dumps(resp.json(), ensure_ascii=False)
    except Exception:
        return resp.text


async def run_tool(tool: Tool, fn_name: str, params: dict, db: AsyncSession | None = None) -> str:
    if tool.tool_type == "builtin_kb":
        if db is None:
            return "错误：内置知识库工具需要数据库连接"
        # 从函数名推断操作类型：kb_{op}_{short_id}
        parts = fn_name.split("_")
        op = parts[1] if len(parts) >= 2 else ""
        if op not in {"search", "add", "delete", "list"}:
            op = params.get("operation", "search")
        return await _run_builtin_kb_op(tool.kb_namespace or "", op, params, db)

    if tool.tool_type == "plugin":
        # plugin 类型：通过 PluginEngine 执行
        result = await PluginEngine.execute(tool, fn_name, params)
        # 统一序列化为字符串（兼容现有调用链）
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)

    steps = tool.steps or []
    if steps:
        step = next(
            (s for s in steps if _sanitize_fn_name(s.get("name", "")) == fn_name), steps[0]
        )
        return await _run_http_step(step, params)

    # 向后兼容：无 steps，直接用 Tool 字段
    return await _run_http_step({
        "api_url": tool.api_url,
        "method": tool.method,
        "auth_config": tool.auth_config,
    }, params)
