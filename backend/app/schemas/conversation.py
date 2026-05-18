import uuid
from datetime import datetime
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = ""
    agent_id: uuid.UUID | None = None
    skill_id: uuid.UUID | None = None


class MessageAdd(BaseModel):
    role: str  # user | assistant
    content: str
    rating: str | None = None         # good | bad（仅 assistant 轮有意义）
    reference_output: str | None = None  # 标准答案（提交时可补填）


class ConversationSubmit(BaseModel):
    """提交会话，触发评估流水线。"""
    # 可在提交时补充每一轮的标准答案
    message_updates: list[dict] = []  # [{"message_id": "...", "reference_output": "..."}]
    # 提交后是否自动跑 AI 优化 + 实验
    run_pipeline: bool = True
    # 评估通过门限（avg_score >= threshold 则自动上线新版本）
    auto_deploy_threshold: float = 0.75


class MessageOut(BaseModel):
    id: uuid.UUID
    turn_index: int
    role: str
    content: str
    rating: str | None
    reference_output: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    agent_id: uuid.UUID | None
    skill_id: uuid.UUID | None
    status: str
    created_by: str
    created_at: datetime
    submitted_at: datetime | None
    eval_set_id: uuid.UUID | None
    experiment_id: uuid.UUID | None
    new_skill_version_id: uuid.UUID | None
    pipeline_result: dict | None
    messages: list[MessageOut] = []

    class Config:
        from_attributes = True
