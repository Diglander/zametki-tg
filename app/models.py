from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func, String, Text, DateTime
from datetime import datetime
from .database import Base


class Zametka(Base):
    __tablename__ = 'zametki'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text)
    tag: Mapped[str] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
