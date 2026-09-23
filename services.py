from datetime import date, datetime

from sqlalchemy import extract

from database import get_session
from models import CarpoolRecord, Member, MemberDayStatus, PurchaseItem, PurchaseRecord, PurchaseShare

DAY_STATUS_CHOICES = ("leave", "wfh")

CARPOOL_AMOUNT = 30


def set_carpool_slot(
    member_id: int, record_date: date, period: str, active: bool, note: str | None = None
) -> None:
    """依點選日曆的操作，開/關某一天某時段的共乘紀錄，並同步備註。"""
    with get_session() as session:
        record = (
            session.query(CarpoolRecord)
            .filter_by(member_id=member_id, record_date=record_date, period=period)
            .first()
        )
        if active:
            if record is None:
                session.add(
                    CarpoolRecord(
                        member_id=member_id,
                        record_date=record_date,
                        period=period,
                        amount=CARPOOL_AMOUNT,
                        note=note,
                    )
                )
            else:
                record.note = note
        elif record is not None:
            session.delete(record)
        session.commit()


def set_day_status(member_id: int, record_date: date, status: str | None) -> None:
    """設定/清除成員某天的請假/居家狀態。status 為 None 代表清除（恢復正常）。
    跟共乘打卡紀錄互不影響，可以同時存在。
    """
    if status is not None and status not in DAY_STATUS_CHOICES:
        raise ValueError("未知的狀態")

    with get_session() as session:
        record = (
            session.query(MemberDayStatus)
            .filter_by(member_id=member_id, record_date=record_date)
            .first()
        )
        if status is None:
            if record is not None:
                session.delete(record)
        elif record is None:
            session.add(MemberDayStatus(member_id=member_id, record_date=record_date, status=status))
        else:
            record.status = status
        session.commit()


def get_month_day_status(member_id: int, year: int, month: int) -> dict[date, str]:
    """回傳該成員當月的請假/居家狀態，供日曆標色使用。團隊所有成員互相可見。"""
    with get_session() as session:
        records = (
            session.query(MemberDayStatus)
            .filter(
                MemberDayStatus.member_id == member_id,
                extract("year", MemberDayStatus.record_date) == year,
                extract("month", MemberDayStatus.record_date) == month,
            )
            .all()
        )
        return {r.record_date: r.status for r in records}


def get_month_all_day_status(year: int, month: int) -> dict[date, dict[int, str]]:
    """回傳當月「所有成員」的請假/居家狀態：{日期: {member_id: status}}。
    用於車主自己頁面一次彙總看所有人狀態，以及讓車主的請假/居家自動出現在其他成員自己的頁面上。
    """
    with get_session() as session:
        records = (
            session.query(MemberDayStatus)
            .filter(
                extract("year", MemberDayStatus.record_date) == year,
                extract("month", MemberDayStatus.record_date) == month,
            )
            .all()
        )
        result: dict[date, dict[int, str]] = {}
        for r in records:
            result.setdefault(r.record_date, {})[r.member_id] = r.status
        return result


def toggle_payment_status(record_type: str, record_id: int, member_id: int) -> bool:
    with get_session() as session:
        if record_type == "carpool":
            record = session.get(CarpoolRecord, record_id)
        elif record_type == "purchase_share":
            record = session.get(PurchaseShare, record_id)
        else:
            raise ValueError("未知的紀錄類型")

        if record is None:
            raise ValueError("紀錄不存在")
        if record.member_id != member_id:
            raise PermissionError("僅本人可標記自己的付款狀態")

        record.is_paid = not record.is_paid
        session.commit()
        return record.is_paid


def create_purchase_record(
    initiator_id: int,
    record_date: date,
    items: list[tuple[str, int]],
    share_member_ids: list[int],
    note: str | None = None,
) -> PurchaseRecord:
    """新增一筆代買紀錄。share_member_ids 可以是空清單──代表這筆只是自己的紀錄，不需要別人付款。"""
    if not items:
        raise ValueError("請至少輸入一個代買品項")

    with get_session() as session:
        purchase = PurchaseRecord(initiator_id=initiator_id, record_date=record_date, note=note)
        session.add(purchase)
        session.flush()

        total = 0
        for item_name, amount in items:
            session.add(
                PurchaseItem(purchase_record_id=purchase.id, item_name=item_name, amount=amount)
            )
            total += amount

        if share_member_ids:
            share_count = len(share_member_ids)
            base_share = round(total / share_count)
            for member_id in share_member_ids:
                session.add(
                    PurchaseShare(
                        purchase_record_id=purchase.id,
                        member_id=member_id,
                        share_amount=base_share,
                    )
                )

        session.commit()
        session.refresh(purchase)
        _ = purchase.items  # 觸發載入，避免 session 關閉後存取觸發 DetachedInstanceError
        _ = purchase.shares
        return purchase


def delete_purchase_record(record_id: int, member_id: int) -> None:
    """刪除一筆代買紀錄（含品項與分攤），僅發起人可刪除。"""
    with get_session() as session:
        record = session.get(PurchaseRecord, record_id)
        if record is None:
            raise ValueError("紀錄不存在")
        if record.initiator_id != member_id:
            raise PermissionError("僅發起人可刪除此紀錄")
        session.delete(record)
        session.commit()


def get_month_purchase_subtotal_by_initiator(year: int, month: int) -> dict[int, int]:
    """本月各發起人的代買小計（品項金額加總），用於顯示每位發起人各自的小計。"""
    with get_session() as session:
        rows = (
            session.query(PurchaseRecord.initiator_id, PurchaseItem.amount)
            .join(PurchaseItem, PurchaseItem.purchase_record_id == PurchaseRecord.id)
            .filter(
                extract("year", PurchaseRecord.record_date) == year,
                extract("month", PurchaseRecord.record_date) == month,
            )
            .all()
        )
        totals: dict[int, int] = {}
        for initiator_id, amount in rows:
            totals[initiator_id] = totals.get(initiator_id, 0) + amount
        return totals


def get_month_payable_by_initiator(member_id: int, year: int, month: int) -> dict[int, dict[str, int]]:
    """該成員本月要付給各發起人的金額，依已付/未付分開加總：{initiator_id: {"paid": x, "unpaid": y}}。"""
    with get_session() as session:
        rows = (
            session.query(PurchaseRecord.initiator_id, PurchaseShare.share_amount, PurchaseShare.is_paid)
            .join(PurchaseShare, PurchaseShare.purchase_record_id == PurchaseRecord.id)
            .filter(
                PurchaseShare.member_id == member_id,
                extract("year", PurchaseRecord.record_date) == year,
                extract("month", PurchaseRecord.record_date) == month,
            )
            .all()
        )
        result: dict[int, dict[str, int]] = {}
        for initiator_id, amount, is_paid in rows:
            bucket = result.setdefault(initiator_id, {"paid": 0, "unpaid": 0})
            bucket["paid" if is_paid else "unpaid"] += amount
        return result


def get_month_carpool_records(member_id: int, year: int, month: int) -> list[CarpoolRecord]:
    with get_session() as session:
        records = (
            session.query(CarpoolRecord)
            .filter(
                CarpoolRecord.member_id == member_id,
                extract("year", CarpoolRecord.record_date) == year,
                extract("month", CarpoolRecord.record_date) == month,
            )
            .all()
        )
        for r in records:
            _ = r.member
        return records


def get_month_purchase_records(year: int, month: int) -> list[PurchaseRecord]:
    with get_session() as session:
        records = (
            session.query(PurchaseRecord)
            .filter(
                extract("year", PurchaseRecord.record_date) == year,
                extract("month", PurchaseRecord.record_date) == month,
            )
            .order_by(PurchaseRecord.record_date.desc(), PurchaseRecord.id.desc())
            .all()
        )
        for r in records:
            _ = r.items
            _ = r.shares
            _ = r.initiator
            for s in r.shares:
                _ = s.member
        return records


def get_member_monthly_summary(member_id: int, year: int, month: int) -> dict:
    carpool_records = get_month_carpool_records(member_id, year, month)
    ride_count = len(carpool_records)
    carpool_subtotal = sum(r.amount for r in carpool_records)

    with get_session() as session:
        purchase_subtotal = (
            session.query(PurchaseShare)
            .join(PurchaseRecord)
            .filter(
                PurchaseShare.member_id == member_id,
                extract("year", PurchaseRecord.record_date) == year,
                extract("month", PurchaseRecord.record_date) == month,
            )
            .with_entities(PurchaseShare.share_amount)
            .all()
        )
        purchase_subtotal = sum(s[0] for s in purchase_subtotal)

    return {
        "ride_count": ride_count,
        "carpool_subtotal": carpool_subtotal,
        "purchase_subtotal": purchase_subtotal,
        "total": carpool_subtotal + purchase_subtotal,
    }


def get_monthly_unpaid_count(member_id: int, year: int | None = None, month: int | None = None) -> int:
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    with get_session() as session:
        carpool_unpaid = (
            session.query(CarpoolRecord)
            .filter(
                CarpoolRecord.member_id == member_id,
                CarpoolRecord.is_paid.is_(False),
                extract("year", CarpoolRecord.record_date) == year,
                extract("month", CarpoolRecord.record_date) == month,
            )
            .count()
        )
        share_unpaid = (
            session.query(PurchaseShare)
            .join(PurchaseRecord)
            .filter(
                PurchaseShare.member_id == member_id,
                PurchaseShare.is_paid.is_(False),
                extract("year", PurchaseRecord.record_date) == year,
                extract("month", PurchaseRecord.record_date) == month,
            )
            .count()
        )
        return carpool_unpaid + share_unpaid


def add_member(name: str) -> Member:
    with get_session() as session:
        if session.query(Member).filter_by(name=name).first():
            raise ValueError("成員姓名已存在")
        member = Member(name=name, is_owner=False)
        session.add(member)
        session.commit()
        session.refresh(member)
        return member


def remove_member(member_id: int) -> None:
    with get_session() as session:
        member = session.get(Member, member_id)
        if member is None:
            raise ValueError("成員不存在")
        session.delete(member)
        session.commit()
