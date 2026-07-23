import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class DecisionStatus(str, enum.Enum):
    open = "open"
    decided = "decided"


class Decision(Base):
    """A running list of things the household needs to decide, resolved by
    both people voting for the same option — not a single free-text call.
    `decision` and `decided_at` are set automatically once both votes agree."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item: Mapped[str] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus, name="decision_status"), default=DecisionStatus.open
    )
    decision: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    decided_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    options: Mapped[list["DecisionOption"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan", order_by="DecisionOption.id"
    )
    votes: Mapped[list["DecisionVote"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )


class DecisionOption(Base):
    __tablename__ = "decision_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(300))

    decision: Mapped["Decision"] = relationship(back_populates="options")


class DecisionVote(Base):
    """One vote per person per decision — voting again replaces the
    previous vote rather than adding a second one."""

    __tablename__ = "decision_votes"
    __table_args__ = (UniqueConstraint("decision_id", "voter", name="uq_decision_voter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"))
    option_id: Mapped[int] = mapped_column(ForeignKey("decision_options.id", ondelete="CASCADE"))
    voter: Mapped[str] = mapped_column(String(20))

    decision: Mapped["Decision"] = relationship(back_populates="votes")
