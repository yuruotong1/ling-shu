"""对话会话管理 API：支持多轮对话、满意后提交触发评估优化流水线"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate, MessageAdd, ConversationSubmit,
    ConversationOut, MessageOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _load_conv(conv_id: uuid.UUID, db: AsyncSession) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conv_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


# ── CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ConversationOut)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = Conversation(
        title=body.title or "新对话",
        agent_id=body.agent_id,
        skill_id=body.skill_id,
        created_by=current_user.username,
    )
    db.add(conv)
    await db.commit()
    return await _load_conv(conv.id, db)


@router.get("/{conv_id}", response_model=ConversationOut)
async def get_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await _load_conv(conv_id, db)


@router.post("/{conv_id}/messages", response_model=MessageOut)
async def add_message(
    conv_id: uuid.UUID,
    body: MessageAdd,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """向会话追加一条消息（user 或 assistant 轮）。"""
    conv = await _load_conv(conv_id, db)
    if conv.status != "draft":
        raise HTTPException(400, "只能向 draft 状态的会话追加消息")

    turn_index = len(conv.messages)
    msg = ConversationMessage(
        conversation_id=conv_id,
        turn_index=turn_index,
        role=body.role,
        content=body.content,
        rating=body.rating,
        reference_output=body.reference_output,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.delete("/{conv_id}")
async def delete_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    conv = await _load_conv(conv_id, db)
    await db.delete(conv)
    await db.commit()
    return {"ok": True}


# ── Submit Pipeline ───────────────────────────────────────────────────

@router.post("/{conv_id}/submit", response_model=ConversationOut)
async def submit_conversation(
    conv_id: uuid.UUID,
    body: ConversationSubmit,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交满意的对话，触发流水线：
    1. 将 assistant 轮保存为评估集 items
    2. AI 优化 Skill 提示词（生成新版本）
    3. 创建实验并异步运行（跑分）
    4. 达到 auto_deploy_threshold 则自动上线新版本
    """
    conv = await _load_conv(conv_id, db)
    if conv.status != "draft":
        raise HTTPException(400, f"会话已处于 {conv.status} 状态，无法重复提交")
    if not conv.skill_id:
        raise HTTPException(400, "该会话未绑定 Skill，无法触发 Skill 优化流水线")

    # 补充 reference_output
    for upd in body.message_updates:
        msg_id = upd.get("message_id")
        ref = upd.get("reference_output")
        if msg_id and ref:
            for m in conv.messages:
                if str(m.id) == str(msg_id):
                    m.reference_output = ref

    conv.status = "submitted"
    conv.submitted_at = datetime.utcnow()
    await db.commit()

    if body.run_pipeline:
        background_tasks.add_task(
            _run_pipeline,
            conv_id=conv_id,
            auto_deploy_threshold=body.auto_deploy_threshold,
        )

    return await _load_conv(conv_id, db)


async def _run_pipeline(conv_id: uuid.UUID, auto_deploy_threshold: float):
    """后台流水线：评估集 → AI优化版本 → 实验 → (可选)自动上线"""
    from app.core.database import AsyncSessionLocal
    from app.models.dataset import EvaluationSet, EvaluationItem
    from app.models.evaluator import Evaluator
    from app.models.experiment import Experiment
    from app.models.skill import Skill, SkillVersion
    from app.services.evaluator_svc import run_experiment
    from app.services.optimizer_svc import optimize_skill, apply_skill_version
    import asyncio

    async with AsyncSessionLocal() as db:
        try:
            conv_result = await db.execute(
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(Conversation.id == conv_id)
            )
            conv = conv_result.scalar_one_or_none()
            if conv is None:
                return

            conv.status = "pipeline_running"
            await db.commit()

            # ── Step 1：从对话中提取 user→assistant 配对，创建评估集 ──
            pairs = []
            msgs = sorted(conv.messages, key=lambda m: m.turn_index)
            i = 0
            while i < len(msgs) - 1:
                if msgs[i].role == "user" and msgs[i + 1].role == "assistant":
                    pairs.append((msgs[i], msgs[i + 1]))
                    i += 2
                else:
                    i += 1

            skill_result = await db.execute(
                select(Skill).where(Skill.id == conv.skill_id)
            )
            skill = skill_result.scalar_one_or_none()
            if skill is None or not pairs:
                conv.status = "failed"
                conv.pipeline_result = {"error": "无有效对话对或Skill不存在"}
                await db.commit()
                return

            eval_set_name = f"conv-{str(conv_id)[:8]}-{skill.name}-v{skill.version}"
            eval_set = EvaluationSet(
                name=eval_set_name,
                description=f"由对话 {conv.title} 自动生成",
                data_type="skill",
                target_name=skill.name,
            )
            db.add(eval_set)
            await db.flush()

            for user_msg, asst_msg in pairs:
                item = EvaluationItem(
                    set_id=eval_set.id,
                    input=[{"role": "user", "content": user_msg.content}],
                    reference_output=asst_msg.reference_output or asst_msg.content,
                    data_type="skill",
                    skill_name=skill.name,
                    skill_version=skill.version,
                )
                db.add(item)

            conv.eval_set_id = eval_set.id
            await db.commit()

            # ── Step 2：AI 优化 Skill 提示词 ─────────────────────────
            # 没有实验历史时用空实验 ID 触发；optimizer_svc 对 None experiment 有容错
            new_ver = await optimize_skill(
                skill_id=conv.skill_id,
                experiment_id=None,
                db=db,
                additional_instruction=(
                    f"参考对话 '{conv.title}' 中 {len(pairs)} 条用户满意的问答对进行优化，"
                    "提升对同类问题的回答质量。"
                ),
            )
            if new_ver:
                conv.new_skill_version_id = new_ver.id
                await db.commit()

            # ── Step 3：挑一个评估器创建实验并运行 ───────────────────
            eval_result = await db.execute(select(Evaluator).limit(1))
            evaluator = eval_result.scalar_one_or_none()
            if evaluator:
                exp = Experiment(
                    name=f"auto-{eval_set_name}",
                    evaluator_id=evaluator.id,
                    eval_set_id=eval_set.id,
                    target_type="skill",
                    target_name=skill.name,
                    target_version=skill.version,
                )
                db.add(exp)
                await db.commit()
                await db.refresh(exp)
                conv.experiment_id = exp.id
                await db.commit()

                # 同步等待实验完成（后台任务中可同步调用）
                await run_experiment(exp.id, db)

                # ── Step 4：达标则自动上线新版本 ─────────────────────
                await db.refresh(exp)
                pipeline_result: dict = {
                    "eval_set_id": str(eval_set.id),
                    "experiment_id": str(exp.id),
                    "avg_score": exp.avg_score,
                    "pass_rate": exp.pass_rate,
                    "auto_deployed": False,
                }

                if (
                    new_ver
                    and exp.avg_score is not None
                    and exp.avg_score >= auto_deploy_threshold
                ):
                    await apply_skill_version(conv.skill_id, new_ver.id, db)
                    pipeline_result["auto_deployed"] = True
                    pipeline_result["deployed_version"] = new_ver.version
            else:
                pipeline_result = {
                    "eval_set_id": str(eval_set.id),
                    "note": "无可用评估器，跳过实验步骤",
                    "auto_deployed": False,
                }

            conv.status = "completed"
            conv.pipeline_result = pipeline_result
            await db.commit()

        except Exception as exc:
            try:
                conv_result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
                conv = conv_result.scalar_one_or_none()
                if conv:
                    conv.status = "failed"
                    conv.pipeline_result = {"error": str(exc)}
                    await db.commit()
            except Exception:
                pass
