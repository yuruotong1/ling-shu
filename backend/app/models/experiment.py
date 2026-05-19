import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Uuid
from app.core.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluator_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evaluators.id"))
    eval_set_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evaluation_sets.id"))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    evaluator: Mapped["Evaluator"] = relationship("Evaluator", lazy="selectin")
    eval_set: Mapped["EvaluationSet"] = relationship("EvaluationSet", lazy="selectin")
    results: Mapped[list["ExperimentResult"]] = relationship("ExperimentResult", back_populates="experiment", cascade="all, delete-orphan")


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("experiments.id", ondelete="CASCADE"))
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evaluation_items.id"))
    actual_output: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    suggestion: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="results")
    item: Mapped["EvaluationItem"] = relationship("EvaluationItem", lazy="selectin")
