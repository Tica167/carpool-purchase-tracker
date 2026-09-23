from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
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


class MemberDayStatus(Base):
    """成員某天的請假/居家狀態，跟共乘打卡紀錄互不影響、可同時存在。
    團隊所有成員互相可見（跟共乘打卡紀錄「自己只能看自己的」不同）。
    """

    __tablename__ = "member_day_status"
    __table_args__ = (UniqueConstraint("member_id", "record_date", name="uq_member_day_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    record_date: Mapped[str] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # "leave" / "wfh"

    member: Mapped["Member"] = relationship()


class CarpoolRate(Base):
    """每趟共乘車資的費率設定，依生效日期區分。新登記的共乘紀錄依「登記日期」
    對應當時生效（`effective_date` <= 登記日期，取最接近的那筆）的費率計算金額；
    已經登記過的舊紀錄金額不會被追溯修改。僅車主可以新增/修改費率設定。
    """

    __tablename__ = "carpool_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    effective_date: Mapped[str] = mapped_column(Date, nullable=False, unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)


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

    @property
    def buyer_summary(self) -> list[tuple["Member", int, bool]]:
        """把這張代買卡片底下「每個品項各自的購買人分攤」彙總成「每位購買人」的
        小計金額與付款狀態（該購買人在這張卡片裡所有品項分攤都已付款才算已付款）。
        供畫面顯示卡片下方的購買人彙總表格使用。
        """
        totals: dict[int, dict] = {}
        for item in self.items:
            for s in item.shares:
                bucket = totals.setdefault(s.member_id, {"member": s.member, "amount": 0, "paid": []})
                bucket["amount"] += s.share_amount
                bucket["paid"].append(s.is_paid)
        return [(b["member"], b["amount"], all(b["paid"])) for b in totals.values()]


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_record_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_records.id"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    purchase_record: Mapped["PurchaseRecord"] = relationship(back_populates="items")
    shares: Mapped[list["PurchaseItemShare"]] = relationship(
        back_populates="purchase_item", cascade="all, delete-orphan"
    )


class PurchaseItemShare(Base):
    """代買品項的購買人分攤：每個品項各自的購買人可以不同，金額由該品項金額
    平均分攤給該品項指定的購買人（購買人可留空，代表這個品項僅代買人自己的花費）。
    """

    __tablename__ = "purchase_item_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_item_id: Mapped[int] = mapped_column(ForeignKey("purchase_items.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    share_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    purchase_item: Mapped["PurchaseItem"] = relationship(back_populates="shares")
    member: Mapped["Member"] = relationship()
