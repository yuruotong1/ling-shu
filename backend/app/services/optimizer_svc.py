"""自动迭代服务：基于评估结果AI自动生成新版Skill提示词"""
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.skill import Skill, SkillVersion
from app.models.experiment import Experiment, ExperimentResult
from app.models.model_config import ModelConfig
from app.services import model_client


async def _get_default_mc(db: AsyncSession) -> ModelConfig | None:
    result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True).limit(1))
    return result.scalar_one_or_none()


async def optimize_skill(
    skill_id,
    experiment_id,
    db: AsyncSession,
    additional_instruction: str = "",
) -> SkillVersion | None:
    """基于实验失败样本，让AI生成优化后的Skill提示词，创建新的draft版本"""
    skill_result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = skill_result.scalar_one_or_none()
    if skill is None:
        return None

    exp_result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    exp = exp_result.scalar_one_or_none()

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
