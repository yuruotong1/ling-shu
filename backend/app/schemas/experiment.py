import uuid
from datetime import datetime
from pydantic import BaseModel


class ExperimentCreate(BaseModel):
    name: str
    evaluator_id: uuid.UUID
    eval_set_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    target_type: str  # agent/skill
    target_name: str
    target_version: int | None = None


class ExperimentOut(BaseModel):
    id: uuid.UUID
    name: str
    evaluator_id: uuid.UUID
    eval_set_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    target_type: str
    target_name: str
    target_version: int | None
    status: str
    avg_score: float | None
    pass_rate: float | None
    total_items: int
    failed_items: int
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class ExperimentResultOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    item_id: uuid.UUID
    actual_output: str
    score: float | None
    issues: list
    suggestion: str
    error: str | None
    input: list = []
    reference_output: str | None = None

    class Config:
        from_attributes = True
