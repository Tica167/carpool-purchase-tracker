from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CarpoolRecord(Base):
    __tablename__ = "carpool_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    record_date: Mapped[str] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # "morning" / "evening"
    amount: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    member: Mapped["Member"] = relationship()


class PurchaseRecord(Base):
    __tablename__ = "purchase_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    record_date: Mapped[str] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    initiator: Mapped["Member"] = relationship()
    items: Mapped[list["PurchaseItem"]] = relationship(
        back_populates="purchase_record", cascade="all, delete-orphan"
    )
    shares: Mapped[list["PurchaseShare"]] = relationship(
        back_populates="purchase_record", cascade="all, delete-orphan"
    )


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_record_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_records.id"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    purchase_record: Mapped["PurchaseRecord"] = relationship(back_populates="items")


class PurchaseShare(Base):
    __tablename__ = "purchase_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_record_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_records.id"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    share_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    purchase_record: Mapped["PurchaseRecord"] = relationship(back_populates="shares")
    member: Mapped["Member"] = relationship()
