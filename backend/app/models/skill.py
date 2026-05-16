import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Integer, Float, ForeignKey, Table, Column, JSON, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid
from app.core.database import Base

skill_tools = Table(
    "skill_tools",
    Base.metadata,
    Column("skill_id", Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE")),
    Column("tool_id", Uuid(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE")),
)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kb_namespaces: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")

    tools = relationship("Tool", secondary=skill_tools, lazy="selectin", uselist=True)
    versions: Mapped[list["SkillVersion"]] = relationship("SkillVersion", back_populates="skill", order_by="SkillVersion.version.desc()")


class SkillVersion(Base):
    __tablename__ = "skill_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(50), default="user")
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    skill: Mapped["Skill"] = relationship("Skill", back_populates="versions")
