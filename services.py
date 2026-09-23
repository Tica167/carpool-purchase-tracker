from datetime import date, datetime

from sqlalchemy import extract

from database import get_session
from models import (
    CarpoolRate,
    CarpoolRecord,
    Member,
    MemberDayStatus,
    PurchaseItem,
    PurchaseItemShare,
    PurchaseRecord,
)

DAY_STATUS_CHOICES = ("leave", "wfh")

CARPOOL_AMOUNT = 30  # 從未設定過任何費率時的預設值


def get_effective_carpool_amount(for_date: date) -> int:
    """回傳「某一天」登記共乘時應套用的每趟車資：取生效日期 <= for_date 中最新的一筆；
    若車主從未設定過費率，回傳預設值 CARPOOL_AMOUNT。
    """
    with get_session() as session:
        rate = (
            session.query(CarpoolRate)
            .filter(CarpoolRate.effective_date <= for_date)
            .order_by(CarpoolRate.effective_date.desc())
            .first()
        )
        return rate.amount if rate else CARPOOL_AMOUNT


def set_carpool_rate(effective_date: date, amount: int) -> None:
    """新增/更新一筆車資費率設定（僅車主可呼叫，權限檢查在 app.py 做）。
    只影響「生效日期之後新登記」的共乘紀錄，已登記過的舊紀錄金額不會被追溯修改。
    """
    if amount <= 0:
        raise ValueError("車資金額必須大於 0")

    with get_session() as session:
        existing = session.query(CarpoolRate).filter_by(effective_date=effective_date).first()
        if existing:
            existing.amount = amount
        else:
            session.add(CarpoolRate(effective_date=effective_date, amount=amount))
        session.commit()


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
                        amount=get_effective_carpool_amount(record_date),
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
    """僅適用於共乘紀錄（每筆一個時段）。代買的付款狀態改用
    `toggle_purchase_record_share_payment()`（依卡片＋購買人整批切換）。
    """
    with get_session() as session:
        if record_type != "carpool":
            raise ValueError("未知的紀錄類型")
        record = session.get(CarpoolRecord, record_id)

        if record is None:
            raise ValueError("紀錄不存在")
        if record.member_id != member_id:
            raise PermissionError("僅本人可標記自己的付款狀態")

        record.is_paid = not record.is_paid
        session.commit()
        return record.is_paid


def add_purchase_item(
    initiator_id: int,
    record_date: date,
    item_name: str,
    amount: int,
    buyer_member_ids: list[int],
    note: str | None = None,
) -> PurchaseRecord:
    """新增一筆代買品項。若當天、同一位代買人已經有一張代買卡片（PurchaseRecord），
    新品項會併入該張現有卡片；否則新建一張卡片（此時才會採用傳入的 note）。
    buyer_member_ids 可以是空清單──代表這個品項僅代買人自己的花費，不需要別人付款；
    有指定購買人時，這個品項的金額平均分攤給「這個品項自己的」購買人（不同品項的購買人可以不同）。
    """
    if not item_name or amount <= 0:
        raise ValueError("請輸入品項名稱與金額")

    with get_session() as session:
        record = (
            session.query(PurchaseRecord)
            .filter_by(initiator_id=initiator_id, record_date=record_date)
            .first()
        )
        if record is None:
            record = PurchaseRecord(initiator_id=initiator_id, record_date=record_date, note=note)
            session.add(record)
            session.flush()

        item = PurchaseItem(purchase_record_id=record.id, item_name=item_name, amount=amount)
        session.add(item)
        session.flush()

        if buyer_member_ids:
            share_count = len(buyer_member_ids)
            base_share = round(amount / share_count)
            for member_id in buyer_member_ids:
                session.add(
                    PurchaseItemShare(
                        purchase_item_id=item.id,
                        member_id=member_id,
                        share_amount=base_share,
                    )
                )

        session.commit()
        session.refresh(record)
        for it in record.items:
            _ = it.shares  # 觸發載入，避免 session 關閉後存取觸發 DetachedInstanceError
        return record


def toggle_purchase_record_share_payment(record_id: int, member_id: int) -> bool:
    """把某成員在某張代買卡片裡「所有品項」的分攤付款狀態一次切換成同一值：
    目前有任何未付款就整張卡片對這個人設成已付款；已全部付款則改回未付款（供復原）。
    僅本人可操作。回傳切換後的狀態。
    """
    with get_session() as session:
        shares = (
            session.query(PurchaseItemShare)
            .join(PurchaseItem, PurchaseItem.id == PurchaseItemShare.purchase_item_id)
            .filter(
                PurchaseItem.purchase_record_id == record_id,
                PurchaseItemShare.member_id == member_id,
            )
            .all()
        )
        if not shares:
            raise ValueError("查無分攤紀錄")

        new_status = not all(s.is_paid for s in shares)
        for s in shares:
            s.is_paid = new_status
        session.commit()
        return new_status


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


def get_month_carpool_payment_status(member_id: int, year: int, month: int) -> bool:
    """該成員本月共乘紀錄是否已全部付清。只要有任何一筆未付款就回傳 False；
    全部已付款、或本月沒有任何共乘紀錄，都回傳 True。
    """
    records = get_month_carpool_records(member_id, year, month)
    return all(r.is_paid for r in records)


def toggle_month_carpool_payment_status(member_id: int, year: int, month: int) -> bool:
    """一鍵把該成員「當月所有」共乘紀錄的付款狀態都設成同一個值，不用逐筆點：
    目前只要有任何一筆未付款，就整月一次設成已付款（結算）；
    若整月已經全部付款，再點一次則整月改回未付款（取消結算，供標記錯誤時復原）。
    回傳設定後的狀態（True=已付款）。本月沒有任何紀錄時不做任何事，直接回傳 True。
    """
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
        if not records:
            return True

        new_status = not all(r.is_paid for r in records)
        for r in records:
            r.is_paid = new_status
        session.commit()
        return new_status


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
            session.query(
                PurchaseRecord.initiator_id, PurchaseItemShare.share_amount, PurchaseItemShare.is_paid
            )
            .join(PurchaseItem, PurchaseItem.purchase_record_id == PurchaseRecord.id)
            .join(PurchaseItemShare, PurchaseItemShare.purchase_item_id == PurchaseItem.id)
            .filter(
                PurchaseItemShare.member_id == member_id,
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
            _ = r.initiator
            for item in r.items:
                for s in item.shares:
                    _ = s.member
        return records


def get_member_monthly_summary(member_id: int, year: int, month: int) -> dict:
    carpool_records = get_month_carpool_records(member_id, year, month)
    ride_count = len(carpool_records)
    carpool_subtotal = sum(r.amount for r in carpool_records)

    with get_session() as session:
        purchase_subtotal = (
            session.query(PurchaseItemShare)
            .join(PurchaseItem, PurchaseItem.id == PurchaseItemShare.purchase_item_id)
            .join(PurchaseRecord, PurchaseRecord.id == PurchaseItem.purchase_record_id)
            .filter(
                PurchaseItemShare.member_id == member_id,
                extract("year", PurchaseRecord.record_date) == year,
                extract("month", PurchaseRecord.record_date) == month,
            )
            .with_entities(PurchaseItemShare.share_amount)
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
            session.query(PurchaseItemShare)
            .join(PurchaseItem, PurchaseItem.id == PurchaseItemShare.purchase_item_id)
            .join(PurchaseRecord, PurchaseRecord.id == PurchaseItem.purchase_record_id)
            .filter(
                PurchaseItemShare.member_id == member_id,
                PurchaseItemShare.is_paid.is_(False),
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
