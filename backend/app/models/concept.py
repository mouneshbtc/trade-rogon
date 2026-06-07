from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class ConceptDefinition(Base, UUIDPrimaryKey, TimestampMixin):
    """A versioned, trader-authored definition of an ICT concept.

    No detection module hardcodes what an "Order Block" or "FVG" is — they all
    resolve their rules from here, pinned to the version that was active at a
    given point in time (`activated_at` / `deactivated_at`), so a backtest run
    today reproduces the reasoning the engine would have produced historically.
    """

    __tablename__ = "concept_definitions"
    __table_args__ = (UniqueConstraint("concept_name", "version", name="uq_concept_name_version"),)

    concept_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Structured, concept-specific rule payload — shape is concept-dependent
    # (e.g. an Order Block definition's `rules` differ from an FVG's).
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
