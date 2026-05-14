from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func, String, Text, DateTime, Boolean, BigInteger, Integer
from datetime import datetime
from .database import Base
from pgvector.sqlalchemy import Vector


class Zametka(Base):
    __tablename__ = 'zametki'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text)
    structured_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_with_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    tag: Mapped[str] = mapped_column(String(20), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    is_reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurrence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    repetitions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tg_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
