"""Agent ReAct循环引擎：思考→行动→观察"""
import json
import time
import uuid as uuid_mod
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.agent import Agent
from app.models.skill import Skill
from app.models.model_config import ModelConfig
from app.models.trace import Trace
from app.services import model_client, skill_runner


def _build_skill_function_defs(skills: list[Skill]) -> list[dict]:
    """将Agent绑定的Skills转换为function definitions供LLM选择"""
    defs = []
    for sk in skills:
        fn_name = sk.name.replace(" ", "_").replace("-", "_")
        defs.append({
            "type": "function",
            "function": {
                "name": fn_name,
                "description": sk.description or sk.name,
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
) -> tuple[str, str, list[dict]]:
    """
    执行Agent循环，返回 (output_content, trace_id, loop_steps)
    """
    start_time = time.time()
    skills: list[Skill] = agent.skills or []
    skill_map = {sk.name.replace(" ", "_").replace("-", "_"): sk for sk in skills}

    skill_func_defs = _build_skill_function_defs(skills) if skills else None

    system_prompt = agent.system_prompt
    if skills:
        skill_list_text = "\n".join(f"- {sk.name}: {sk.description or ''}" for sk in skills)
        system_prompt += f"\n\n## 可用Skill\n{skill_list_text}"

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

    latency_ms = int((time.time() - start_time) * 1000)
    trace_id = str(uuid_mod.uuid4())

    trace = Trace(
        id=uuid_mod.UUID(trace_id),
        agent_name=agent.name,
        agent_version=agent.version,
        input=[{"role": m["role"], "content": m.get("content", "")} for m in messages],
        output=final_output,
        loop_steps=loop_steps,
        total_loops=len(loop_steps),
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        latency_ms=latency_ms,
        status="success",
    )
    db.add(trace)
    await db.commit()

    return final_output, trace_id, loop_steps
