import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    prompt: str
    tool_ids: list[uuid.UUID] = []
    kb_namespaces: list[str] = []


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    tool_ids: list[uuid.UUID] | None = None
    kb_namespaces: list[str] | None = None
    status: str | None = None
    change_summary: str = ""


class ToolBrief(BaseModel):
    id: uuid.UUID
    name: str
    description: str

    class Config:
        from_attributes = True


class SkillOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    prompt: str
    version: int
    status: str
    eval_score: float | None
    tools: list[ToolBrief] = []
    kb_namespaces: list[str] = []
    active_version_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator('tools', mode='before')
    @classmethod
    def coerce_tools(cls, v):
        return v if v is not None else []

    @field_validator('kb_namespaces', mode='before')
    @classmethod
    def coerce_kb_namespaces(cls, v):
        return v if v is not None else []


class SkillVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    prompt: str
    change_summary: str
    created_by: str
    eval_score: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class SkillTestRequest(BaseModel):
    messages: list[dict]
    model_config_id: uuid.UUID | None = None
