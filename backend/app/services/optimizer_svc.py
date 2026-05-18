"""自动迭代服务：基于评估结果/对话AI自动生成新版Skill/Agent提示词"""
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.skill import Skill, SkillVersion
from app.models.agent import Agent, AgentVersion
from app.models.experiment import Experiment, ExperimentResult
from app.models.model_config import ModelConfig
from app.services import model_client


async def _get_default_mc(db: AsyncSession) -> ModelConfig | None:
    result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    return result.scalar_one_or_none()


async def optimize_skill(
    skill_id,
    experiment_id,  # 可为 None（对话提交时无先验实验）
    db: AsyncSession,
    additional_instruction: str = "",
) -> SkillVersion | None:
    """基于实验失败样本（或额外指令），让AI生成优化后的Skill提示词，创建新版本"""
    skill_result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = skill_result.scalar_one_or_none()
    if skill is None:
        return None

    failed_samples = []
    if experiment_id is not None:
        # 获取失败/低分样本
        results_query = await db.execute(
            select(ExperimentResult).where(ExperimentResult.experiment_id == experiment_id)
        )
        all_results = results_query.scalars().all()
        failed_samples = [r for r in all_results if r.score is not None and r.score < 0.7][:5]

    samples_text = ""
    for i, r in enumerate(failed_samples, 1):
        input_text = r.item.input[-1].get("content", "") if r.item.input else ""
        samples_text += f"\n### 样本{i}\n输入：{input_text}\n实际输出：{r.actual_output[:300]}\n问题：{', '.join(r.issues)}\n建议：{r.suggestion}\n"

    mc = await _get_default_mc(db)
    if mc is None:
        return None

    prompt_content = f"""你是一个提示词优化专家。请根据以下信息，优化Skill的提示词。

## 当前Skill名称
{skill.name}

## 当前提示词
{skill.prompt}

## 评估问题（失败样本）
{samples_text or '无具体失败样本'}

## 额外优化要求
{additional_instruction or '无'}

## 要求
1. 保持Skill的核心功能不变
2. 针对失败样本中暴露的问题进行修复
3. 直接输出优化后的完整提示词，不要任何解释

优化后的提示词："""

    result = await model_client.chat_completion(
        mc=mc,
        messages=[{"role": "user", "content": prompt_content}],
        temperature=0.3,
    )
    new_prompt = result["choices"][0]["message"].get("content", "").strip()

    if not new_prompt or new_prompt == skill.prompt:
        return None

    new_version_num = skill.version + 1
    new_version = SkillVersion(
        skill_id=skill.id,
        version=new_version_num,
        prompt=new_prompt,
        change_summary=f"AI自动优化：基于实验{experiment_id}的评估结果{f'，{additional_instruction}' if additional_instruction else ''}",
        created_by="ai",
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return new_version


async def optimize_skill_from_conversation(
    skill_id,
    turns: list[dict],   # [{"input": str, "output": str, "rating": str|None, "reference": str|None}]
    db: AsyncSession,
    instruction: str = "",
) -> SkillVersion | None:
    """基于对话轮次（调用链路）优化 Skill 提示词。"""
    skill_result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = skill_result.scalar_one_or_none()
    if skill is None:
        return None

    bad_samples = [t for t in turns if t.get("rating") == "bad" or t.get("reference")]
    sample_text = ""
    for i, t in enumerate(bad_samples[:5], 1):
        sample_text += f"\n### 样本{i}\n输入：{t['input'][:300]}\n实际输出：{t['output'][:300]}"
        if t.get("reference"):
            sample_text += f"\n期望输出：{t['reference'][:300]}"
        sample_text += "\n"

    mc = await _get_default_mc(db)
    if mc is None:
        return None

    prompt_content = f"""你是一个提示词优化专家。请根据以下信息，优化Skill的提示词。

## 当前Skill名称
{skill.name}

## 当前提示词
{skill.prompt}

## 不满意的对话样本（rating=bad 或有期望输出）
{sample_text or '无具体样本，请根据优化要求进行通用优化'}

## 额外优化要求
{instruction or '无'}

## 要求
1. 保持Skill的核心功能不变
2. 针对样本中暴露的问题进行修复
3. 直接输出优化后的完整提示词，不要任何解释

优化后的提示词："""

    result = await model_client.chat_completion(
        mc=mc, messages=[{"role": "user", "content": prompt_content}], temperature=0.3,
    )
    new_prompt = result["choices"][0]["message"].get("content", "").strip()
    if not new_prompt or new_prompt == skill.prompt:
        return None

    new_version = SkillVersion(
        skill_id=skill.id,
        version=skill.version + 1,
        prompt=new_prompt,
        change_summary=f"AI优化（来自对话链路）{f'：{instruction}' if instruction else ''}",
        created_by="ai",
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return new_version


async def optimize_agent_from_conversation(
    agent_id,
    turns: list[dict],
    db: AsyncSession,
    instruction: str = "",
) -> AgentVersion | None:
    """基于对话轮次（调用链路）优化 Agent system_prompt。"""
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        return None

    bad_samples = [t for t in turns if t.get("rating") == "bad" or t.get("reference")]
    sample_text = ""
    for i, t in enumerate(bad_samples[:5], 1):
        sample_text += f"\n### 样本{i}\n输入：{t['input'][:300]}\n实际输出：{t['output'][:300]}"
        if t.get("reference"):
            sample_text += f"\n期望输出：{t['reference'][:300]}"
        sample_text += "\n"

    mc = await _get_default_mc(db)
    if mc is None:
        return None

    prompt_content = f"""你是一个提示词优化专家。请根据以下信息，优化Agent的系统提示词。

## 当前Agent名称
{agent.name}

## 当前系统提示词
{agent.system_prompt}

## 不满意的对话样本
{sample_text or '无具体样本，请根据优化要求进行通用优化'}

## 额外优化要求
{instruction or '无'}

## 要求
1. 保持Agent的核心角色定位不变
2. 针对样本中暴露的问题进行修复
3. 直接输出优化后的完整系统提示词，不要任何解释

优化后的系统提示词："""

    result = await model_client.chat_completion(
        mc=mc, messages=[{"role": "user", "content": prompt_content}], temperature=0.3,
    )
    new_prompt = result["choices"][0]["message"].get("content", "").strip()
    if not new_prompt or new_prompt == agent.system_prompt:
        return None

    new_version = AgentVersion(
        agent_id=agent.id,
        version=agent.version + 1,
        system_prompt=new_prompt,
        change_summary=f"AI优化（来自对话链路）{f'：{instruction}' if instruction else ''}",
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return new_version


async def apply_skill_version(skill_id, version_id, db: AsyncSession) -> Skill | None:
    """将某个版本设为当前版本并发布"""
    skill_result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = skill_result.scalar_one_or_none()
    if skill is None:
        return None

    ver_result = await db.execute(select(SkillVersion).where(SkillVersion.id == version_id))
    ver = ver_result.scalar_one_or_none()
    if ver is None:
        return None

    # 保存当前版本到历史
    current_ver = SkillVersion(
        skill_id=skill.id,
        version=skill.version,
        prompt=skill.prompt,
        change_summary="归档当前版本",
        created_by="system",
    )
    db.add(current_ver)

    skill.prompt = ver.prompt
    skill.version = ver.version
    skill.status = "active"
    await db.commit()
    await db.refresh(skill)
    return skill
