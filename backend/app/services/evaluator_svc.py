"""评估服务：运行实验，对Agent/Skill输出打分"""
import json
import uuid as uuid_mod
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.evaluator import Evaluator
from app.models.dataset import EvaluationSet, EvaluationItem
from app.models.experiment import Experiment, ExperimentResult
from app.models.agent import Agent
from app.models.skill import Skill
from app.models.model_config import ModelConfig
from app.services import model_client, agent_runner, skill_runner


async def _get_model_config(db: AsyncSession, mc_id: uuid_mod.UUID | None) -> ModelConfig | None:
    if mc_id is None:
        result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
        return result.scalar_one_or_none()
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == mc_id))
    return result.scalar_one_or_none()


async def _run_target(
    target_type: str,
    target_name: str,
    target_version: int | None,
    messages: list[dict],
    db: AsyncSession,
    mc: ModelConfig,
) -> str:
    if target_type == "agent":
        result = await db.execute(select(Agent).where(Agent.name == target_name))
        agent = result.scalar_one_or_none()
        if agent is None:
            return f"Agent '{target_name}' not found"
        output, _, _ = await agent_runner.run_agent(agent, mc, messages, db)
        return output
    else:
        result = await db.execute(select(Skill).where(Skill.name == target_name))
        skill = result.scalar_one_or_none()
        if skill is None:
            return f"Skill '{target_name}' not found"
        return await skill_runner.run_skill(skill, messages, mc)


async def _score_output(
    evaluator: Evaluator,
    input_messages: list[dict],
    reference_output: str | None,
    actual_output: str,
    mc: ModelConfig,
) -> tuple[float, list[str], str]:
    input_summary = input_messages[-1].get("content", "") if input_messages else ""
    eval_prompt = evaluator.prompt
    score_min, score_max = evaluator.score_range[0], evaluator.score_range[1]

    user_content = f"""请评估以下AI输出的质量，给出{score_min}到{score_max}之间的分数。

## 输入
{input_summary}

## 参考输出（如有）
{reference_output or '无'}

## 实际输出
{actual_output}

请按以下JSON格式输出评估结果：
{{"score": <float>, "issues": [<string>], "suggestion": "<string>"}}

只输出JSON，不要其他内容。"""

    result = await model_client.chat_completion(
        mc=mc,
        messages=[
            {"role": "system", "content": eval_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    content = result["choices"][0]["message"].get("content", "{}")
    try:
        parsed = json.loads(content)
        score = float(parsed.get("score", 0))
        score = max(score_min, min(score_max, score))
        issues = parsed.get("issues", [])
        suggestion = parsed.get("suggestion", "")
    except Exception:
        score = 0.0
        issues = ["解析评分结果失败"]
        suggestion = content

    return score, issues, suggestion


async def run_experiment(experiment_id: uuid_mod.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    exp = result.scalar_one_or_none()
    if exp is None:
        return

    exp.status = "running"
    await db.commit()

    try:
        eval_result = await db.execute(select(Evaluator).where(Evaluator.id == exp.evaluator_id))
        evaluator = eval_result.scalar_one_or_none()

        set_result = await db.execute(
            select(EvaluationSet).where(EvaluationSet.id == exp.eval_set_id)
        )
        eval_set = set_result.scalar_one_or_none()

        items_result = await db.execute(
            select(EvaluationItem).where(EvaluationItem.set_id == exp.eval_set_id)
        )
        items = items_result.scalars().all()

        mc = await _get_model_config(db, evaluator.model_config_id if evaluator else None)
        if mc is None:
            exp.status = "failed"
            await db.commit()
            return

        scores = []
        failed_count = 0
        for item in items:
            try:
                actual_output = await _run_target(
                    exp.target_type, exp.target_name, exp.target_version,
                    item.input, db, mc
                )
                score, issues, suggestion = await _score_output(
                    evaluator, item.input, item.reference_output, actual_output, mc
                )
                er = ExperimentResult(
                    experiment_id=exp.id,
                    item_id=item.id,
                    actual_output=actual_output,
                    score=score,
                    issues=issues,
                    suggestion=suggestion,
                )
                db.add(er)
                scores.append(score)
            except Exception as e:
                failed_count += 1
                er = ExperimentResult(
                    experiment_id=exp.id,
                    item_id=item.id,
                    actual_output="",
                    score=None,
                    issues=[],
                    suggestion="",
                    error=str(e),
                )
                db.add(er)

        exp.total_items = len(items)
        exp.failed_items = failed_count
        exp.avg_score = sum(scores) / len(scores) if scores else None
        exp.pass_rate = len([s for s in scores if s >= 0.7]) / len(scores) if scores else None
        exp.status = "completed"
        exp.completed_at = datetime.utcnow()
        await db.commit()
    except Exception as e:
        exp.status = "failed"
        await db.commit()
        raise
