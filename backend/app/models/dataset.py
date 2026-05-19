import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid
from app.core.database import Base


class EvaluationSet(Base):
    __tablename__ = "evaluation_sets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    data_type: Mapped[str] = mapped_column(String(20), default="agent")
    target_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["EvaluationItem"]] = relationship("EvaluationItem", back_populates="eval_set", cascade="all, delete-orphan")


class EvaluationItem(Base):
    __tablename__ = "evaluation_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    set_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evaluation_sets.id", ondelete="CASCADE"))
    input: Mapped[list] = mapped_column(JSON, nullable=False)
    reference_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(20), default="agent")
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skill_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skill_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    eval_set: Mapped["EvaluationSet"] = relationship("EvaluationSet", back_populates="items")
