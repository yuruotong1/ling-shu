import uuid
from datetime import datetime
from pydantic import BaseModel


class EvaluatorCreate(BaseModel):
    name: str
    description: str = ""
    prompt: str
    score_range: list[float] = [0, 1]
    output_format: dict = {"score": "float", "issues": ["string"], "suggestion": "string"}
    model_config_id: uuid.UUID | None = None


class EvaluatorUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    score_range: list[float] | None = None
    output_format: dict | None = None
    model_config_id: uuid.UUID | None = None
    is_active: bool | None = None


class EvaluatorOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    prompt: str
    score_range: list
    output_format: dict
    model_config_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvalSetCreate(BaseModel):
    name: str
    description: str = ""
    data_type: str = "agent"
    target_name: str | None = None
    agent_id: uuid.UUID | None = None


class EvalItemCreate(BaseModel):
    input: list[dict]
    reference_output: str | None = None
    data_type: str = "agent"
    agent_name: str | None = None
    agent_version: int | None = None
    skill_name: str | None = None
    skill_version: int | None = None


class EvalSetOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    data_type: str
    target_name: str | None
    agent_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    item_count: int = 0

    class Config:
        from_attributes = True


class EvalItemOut(BaseModel):
    id: uuid.UUID
    set_id: uuid.UUID
    input: list
    reference_output: str | None
    data_type: str
    agent_name: str | None
    skill_name: str | None
    eval_score: float | None
    created_at: datetime

    class Config:
        from_attributes = True
