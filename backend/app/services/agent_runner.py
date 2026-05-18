"""Agent ReAct循环引擎：思考→行动→观察，支持结构化JSON输出"""
import json
import jsonschema
import time
import uuid
import uuid as uuid_mod
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.agent import Agent, AgentVersion
from app.models.skill import Skill, SkillVersion
from app.models.model_config import ModelConfig
from app.models.trace import Trace
from app.services import model_client, skill_runner


def _build_format_instruction(schema: dict) -> str:
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    return (
        "\n\n---\n【输出格式要求】\n"
        "你必须严格以 JSON 格式输出，不要输出任何 JSON 以外的内容（无需代码块包裹）。\n"
        f"返回的 JSON 必须符合以下 JSON Schema：\n{schema_str}"
    )


def _validate_and_extract_json(text: str, schema: dict) -> tuple[bool, str]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        stripped = inner.strip()
    try:
        parsed = json.loads(stripped)
        jsonschema.validate(parsed, schema)
        return True, json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return False, f"JSON解析失败：{e}"
    except jsonschema.ValidationError as e:
        return False, f"Schema校验失败：{e.message}"


def _build_skill_function_defs(skills: list[Skill]) -> list[dict]:
    """将Agent绑定的Skills转换为function definitions供LLM选择"""
    defs = []
    for i, sk in enumerate(skills):
        # OpenAI 限制 tool name 只能包含 a-zA-Z0-9_-，中文名需用 skill_i 替代
        fn_name = f"skill_{i}"
        defs.append({
            "type": "function",
            "function": {
                "name": fn_name,
                "description": f"{sk.name}: {sk.description or ''}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "传给Skill的输入内容"}
                    },
                    "required": ["input"],
                },
            },
        })
    return defs


async def run_agent(
    agent: Agent,
    mc: ModelConfig,
    messages: list[dict],
    db: AsyncSession,
    temperature: float | None = None,
    max_tokens: int | None = None,
    session_id: uuid.UUID | None = None,
    turn_index: int = 0,
) -> tuple[str, str, list[dict]]:
    """
    执行Agent循环，返回 (output_content, trace_id, loop_steps)
    """
    start_time = time.time()
    skills: list[Skill] = agent.skills or []
    skill_map = {f"skill_{i}": sk for i, sk in enumerate(skills)}

    skill_func_defs = _build_skill_function_defs(skills) if skills else None

    response_format: dict | None = agent.response_format
    # 使用固定线上版本的 system_prompt（若已设置）
    system_prompt = agent.system_prompt
    if agent.active_version_id:
        ver_r = await db.execute(select(AgentVersion).where(AgentVersion.id == agent.active_version_id))
        ver = ver_r.scalar_one_or_none()
        if ver:
            system_prompt = ver.system_prompt

    if skills:
        # 如果 skill 也有 active_version，更新其 prompt
        for sk in skills:
            if sk.active_version_id:
                sv_r = await db.execute(select(SkillVersion).where(SkillVersion.id == sk.active_version_id))
                sv = sv_r.scalar_one_or_none()
                if sv:
                    sk.prompt = sv.prompt  # 临时覆盖，不写库
        skill_list_text = "\n".join(f"- {sk.name}: {sk.description or ''}" for sk in skills)
        system_prompt += f"\n\n## 可用Skill\n{skill_list_text}"
    if response_format:
        system_prompt += _build_format_instruction(response_format)

    loop_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m.get("content", "")} for m in messages
    ]

    loop_steps = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    final_output = ""
    max_loops = agent.max_loops or 10

    for loop_idx in range(max_loops):
        result = await model_client.chat_completion(
            mc=mc,
            messages=loop_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=skill_func_defs,
        )
        choice = result["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")
        usage = result.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)

        step: dict = {"round": loop_idx + 1}

        if finish_reason == "tool_calls" or msg.get("tool_calls"):
            loop_messages.append(msg)
            for tc in msg.get("tool_calls", []):
                fn_name = tc["function"]["name"]
                fn_args_str = tc["function"].get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_str)
                except Exception:
                    fn_args = {}

                step["thought"] = msg.get("content") or f"调用Skill: {fn_name}"
                step["action"] = f"call_skill:{fn_name}"
                step["action_input"] = fn_args

                matched_skill = skill_map.get(fn_name)
                if matched_skill:
                    skill_input_text = fn_args.get("input", json.dumps(fn_args, ensure_ascii=False))
                    skill_messages = [{"role": "user", "content": skill_input_text}]
                    observation = await skill_runner.run_skill(
                        skill=matched_skill,
                        messages=skill_messages,
                        mc=mc,
                        temperature=temperature,
                        db=db,
                    )
                else:
                    observation = f"Skill '{fn_name}' not found"

                step["observation"] = observation
                loop_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": observation,
                })
        else:
            final_output = msg.get("content", "")
            step["thought"] = "任务完成"
            step["action"] = "final_response"
            step["observation"] = final_output
            loop_steps.append(step)
            break

        loop_steps.append(step)

    # ── JSON 格式强制校验 + 最多 2 次容错重试 ───────────────────────
    if response_format and final_output:
        for attempt in range(3):
            is_valid, extracted = _validate_and_extract_json(final_output, response_format)
            if is_valid:
                final_output = extracted
                break
            if attempt < 2:
                retry_messages = loop_messages + [
                    {"role": "assistant", "content": final_output},
                    {
                        "role": "user",
                        "content": (
                            f"你的输出不符合要求的 JSON Schema，原因：{extracted}\n"
                            "请重新输出，仅输出合法 JSON，不要有其他内容。"
                        ),
                    },
                ]
                retry_result = await model_client.chat_completion(
                    mc=mc, messages=retry_messages, temperature=0.1, max_tokens=max_tokens
                )
                final_output = retry_result["choices"][0]["message"].get("content", "")

    latency_ms = int((time.time() - start_time) * 1000)
    trace_id = str(uuid_mod.uuid4())

    trace = Trace(
        id=uuid_mod.UUID(trace_id),
        agent_name=agent.name,
        agent_version=agent.version,
        agent_id=agent.id,
        input=[{"role": m["role"], "content": m.get("content", "")} for m in messages],
        output=final_output,
        loop_steps=loop_steps,
        total_loops=len(loop_steps),
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        latency_ms=latency_ms,
        status="success",
        session_id=session_id,
        turn_index=turn_index,
    )
    db.add(trace)
    await db.commit()

    return final_output, trace_id, loop_steps
