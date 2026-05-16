"""Skill执行器：加载Skill提示词，执行LLM调用，处理Tool调用"""
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.skill import Skill
from app.models.model_config import ModelConfig
from app.services import model_client, tool_runner


def _kb_search_func_def(namespaces: list[str]) -> dict:
    ns_desc = "、".join(namespaces)
    props: dict = {
        "query": {"type": "string", "description": "搜索查询内容"},
    }
    if len(namespaces) > 1:
        props["namespace"] = {
            "type": "string",
            "description": f"知识库命名空间，可选：{ns_desc}",
            "enum": namespaces,
        }
    else:
        props["namespace"] = {
            "type": "string",
            "description": f"知识库命名空间（固定为 {namespaces[0]}）",
            "enum": namespaces,
        }
    return {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": f"从知识库（{ns_desc}）中检索相关内容",
            "parameters": {
                "type": "object",
                "properties": props,
                "required": ["namespace", "query"],
            },
        },
    }


async def _run_kb_search(db: AsyncSession, namespace: str, query: str, top_k: int = 5) -> str:
    from app.models.kb import KbChunk
    keywords = [w for w in query.split() if w]
    if not keywords:
        return "未找到相关内容"
    result = await db.execute(select(KbChunk).where(KbChunk.namespace == namespace))
    chunks = result.scalars().all()
    scored = [(c, sum(1 for kw in keywords if kw.lower() in c.content.lower())) for c in chunks]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored:
        return f'知识库 [{namespace}] 中未找到与"{query}"相关的内容'
    return "\n---\n".join(c.content for c, _ in scored[:top_k])


async def run_skill(
    skill: Skill,
    messages: list[dict],
    mc: ModelConfig,
    temperature: float | None = None,
    max_tokens: int | None = None,
    db: AsyncSession | None = None,
) -> str:
    system_msg = {"role": "system", "content": skill.prompt}
    full_messages = [system_msg] + messages

    tools_list = skill.tools or []
    func_defs = []
    fn_to_tool: dict = {}
    for t in tools_list:
        defs = tool_runner.tool_to_function_defs(t)
        func_defs.extend(defs)
        for d in defs:
            fn_to_tool[d["function"]["name"]] = t

    kb_namespaces = skill.kb_namespaces or []
    if kb_namespaces and db is not None:
        func_defs.append(_kb_search_func_def(kb_namespaces))

    func_defs = func_defs or None

    max_tool_loops = 5
    for _ in range(max_tool_loops):
        result = await model_client.chat_completion(
            mc=mc,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=func_defs,
        )
        choice = result["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        if finish_reason == "tool_calls" or (msg.get("tool_calls")):
            full_messages.append(msg)
            for tc in msg.get("tool_calls", []):
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"].get("arguments", "{}"))

                if fn_name == "kb_search" and db is not None:
                    ns = fn_args.get("namespace", kb_namespaces[0] if kb_namespaces else "")
                    query = fn_args.get("query", "")
                    tool_result = await _run_kb_search(db, ns, query)
                else:
                    matched_tool = fn_to_tool.get(fn_name)
                    if matched_tool:
                        tool_result = await tool_runner.run_tool(matched_tool, fn_name, fn_args, db=db)
                    else:
                        tool_result = f"Tool '{fn_name}' not found"

                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })
        else:
            return msg.get("content", "")

    return full_messages[-1].get("content", "") if full_messages else ""
