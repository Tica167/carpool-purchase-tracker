import calendar as calendar_lib
from datetime import date, datetime

from flask import Flask, abort, redirect, render_template, request, session, url_for

from database import get_session, init_db
from holidays import get_holidays, has_holiday_data
from models import CarpoolRecord, Member
from services import (
    CARPOOL_AMOUNT,
    add_member,
    create_purchase_record,
    get_member_monthly_summary,
    get_month_carpool_records,
    get_month_purchase_records,
    get_monthly_unpaid_count,
    remove_member,
    set_carpool_slot,
    toggle_payment_status,
)

app = Flask(__name__)
app.secret_key = "carpool-purchase-tracker-dev-secret"

PERIOD_LABELS = {"morning": "上班", "evening": "下班"}


def current_member():
    member_id = session.get("member_id")
    if member_id is None:
        return None
    with get_session() as db:
        return db.get(Member, member_id)


@app.before_request
def require_login():
    if request.endpoint in ("login_page", "login", "static"):
        return None
    if current_member() is None:
        return redirect(url_for("login_page"))


@app.context_processor
def inject_common():
    member = current_member()
    unpaid = get_monthly_unpaid_count(member.id) if member else 0
    return {"current_member": member, "monthly_unpaid": unpaid}


def _month_weeks(year: int, month: int) -> list[list[date]]:
    cal = calendar_lib.Calendar(firstweekday=0)  # 星期一為一週開始
    weeks: list[list[date]] = []
    week: list[date] = []
    for day in cal.itermonthdates(year, month):
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []
    return weeks


@app.route("/")
def login_page():
    with get_session() as db:
        members = db.query(Member).order_by(Member.id).all()
    return render_template("login.html", members=members)


@app.route("/login/<int:member_id>", methods=["POST"])
def login(member_id):
    with get_session() as db:
        member = db.get(Member, member_id)
    if member is None:
        abort(404)
    session["member_id"] = member.id
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    member = current_member()
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    selected_date_str = request.args.get("date")

    with get_session() as db:
        members = db.query(Member).order_by(Member.id).all()

    view_member_id = member.id
    if member.is_owner:
        view_member_id = request.args.get("view_member_id", type=int) or member.id
    view_member = next((m for m in members if m.id == view_member_id), member)
    can_edit = view_member.id == member.id

    carpool_records = get_month_carpool_records(view_member.id, year, month)
    records_by_day: dict[date, dict[str, CarpoolRecord]] = {}
    for r in carpool_records:
        records_by_day.setdefault(r.record_date, {})[r.period] = r

    summary = get_member_monthly_summary(view_member.id, year, month)
    purchase_records = get_month_purchase_records(year, month)
    purchase_subtotal_all = sum(
        item.amount for r in purchase_records for item in r.items if r.initiator_id == member.id
    )

    selected_date = date.fromisoformat(selected_date_str) if selected_date_str else None
    selected_day_records = records_by_day.get(selected_date, {}) if selected_date else {}

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    weeks = _month_weeks(year, month)
    holidays = get_holidays(year)
    holiday_data_available = has_holiday_data(year)

    return render_template(
        "dashboard.html",
        members=members,
        view_member=view_member,
        can_edit=can_edit,
        year=year,
        month=month,
        weeks=weeks,
        records_by_day=records_by_day,
        holidays=holidays,
        holiday_data_available=holiday_data_available,
        period_labels=PERIOD_LABELS,
        carpool_amount=CARPOOL_AMOUNT,
        summary=summary,
        purchase_records=purchase_records,
        purchase_subtotal_all=purchase_subtotal_all,
        selected_date=selected_date,
        selected_day_records=selected_day_records,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
    )


@app.route("/dashboard/carpool/save", methods=["POST"])
def carpool_save():
    member = current_member()
    record_date = date.fromisoformat(request.form["record_date"])
    year = int(request.form["year"])
    month = int(request.form["month"])
    note = request.form.get("note", "").strip() or None

    for period in ("morning", "evening"):
        active = request.form.get(period) == "on"
        set_carpool_slot(member.id, record_date, period, active, note)

    return redirect(
        url_for("dashboard", year=year, month=month, date=record_date.isoformat())
    )


@app.route("/dashboard/carpool/<int:record_id>/pay", methods=["POST"])
def carpool_pay(record_id):
    member = current_member()
    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    record_date = request.form.get("record_date")
    try:
        toggle_payment_status("carpool", record_id, member.id)
    except (ValueError, PermissionError):
        abort(403)
    return redirect(url_for("dashboard", year=year, month=month, date=record_date))


@app.route("/dashboard/purchase/add", methods=["POST"])
def purchase_add():
    member = current_member()
    year = int(request.form["year"])
    month = int(request.form["month"])
    record_date = date.fromisoformat(request.form["record_date"])
    item_name = request.form.get("item_name", "").strip()
    item_amount = request.form.get("item_amount", "").strip()
    note = request.form.get("note", "").strip() or None
    share_member_ids = [int(mid) for mid in request.form.getlist("share_member_id")]

    if item_name and item_amount:
        create_purchase_record(
            member.id, record_date, [(item_name, int(item_amount))], share_member_ids, note
        )

    return redirect(url_for("dashboard", year=year, month=month))


@app.route("/dashboard/purchase/share/<int:share_id>/pay", methods=["POST"])
def purchase_share_pay(share_id):
    member = current_member()
    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    try:
        toggle_payment_status("purchase_share", share_id, member.id)
    except (ValueError, PermissionError):
        abort(403)
    return redirect(url_for("dashboard", year=year, month=month))


@app.route("/members", methods=["GET", "POST"])
def members_page():
    member = current_member()
    if not member.is_owner:
        abort(403)

    error = None
    if request.method == "POST":
        name = request.form["name"].strip()
        try:
            add_member(name)
        except ValueError as e:
            error = str(e)

    with get_session() as db:
        all_members = db.query(Member).order_by(Member.id).all()
    return render_template("members.html", members=all_members, error=error)


@app.route("/members/<int:member_id>/delete", methods=["POST"])
def members_delete(member_id):
    member = current_member()
    if not member.is_owner:
        abort(403)
    try:
        remove_member(member_id)
    except ValueError:
        abort(404)
    return redirect(url_for("members_page"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
