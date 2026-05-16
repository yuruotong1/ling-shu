import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str
    max_loops: int = 10
    model_config_id: uuid.UUID | None = None
    model_override: str | None = None
    skill_ids: list[uuid.UUID] = []
    risk_control: dict = {}


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    max_loops: int | None = None
    model_config_id: uuid.UUID | None = None
    model_override: str | None = None
    skill_ids: list[uuid.UUID] | None = None
    risk_control: dict | None = None
    status: str | None = None


class SkillBrief(BaseModel):
    id: uuid.UUID
    name: str
    description: str

    class Config:
        from_attributes = True


class AgentOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    system_prompt: str
    max_loops: int
    model_config_id: uuid.UUID | None
    model_override: str | None
    risk_control: dict
    version: int
    status: str
    skills: list[SkillBrief] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator('skills', mode='before')
    @classmethod
    def coerce_skills(cls, v):
        return v if v is not None else []


class AgentVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    system_prompt: str
    change_summary: str
    created_at: datetime

    class Config:
        from_attributes = True


class AgentTestRequest(BaseModel):
    messages: list[dict]
    model_config_id: uuid.UUID | None = None
