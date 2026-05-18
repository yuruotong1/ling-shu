import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Integer, Float, ForeignKey, Table, Column, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid
from app.core.database import Base

agent_skills = Table(
    "agent_skills",
    Base.metadata,
    Column("agent_id", Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")),
    Column("skill_id", Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE")),
    Column("sort_order", Integer, default=0),
)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    max_loops: Mapped[int] = mapped_column(Integer, default=10)
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("model_configs.id"), nullable=True)
    model_override: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_control: Mapped[dict] = mapped_column(JSON, default=dict)
    response_format: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    response_format_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    # 固定线上版本；None 表示始终使用最新（agent.system_prompt）
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    model_config_rel: Mapped["ModelConfig"] = relationship("ModelConfig", lazy="selectin")
    skills = relationship("Skill", secondary=agent_skills, lazy="selectin", uselist=True)
    versions: Mapped[list["AgentVersion"]] = relationship("AgentVersion", back_populates="agent", order_by="AgentVersion.version.desc()")


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    skills_snapshot: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="versions")
