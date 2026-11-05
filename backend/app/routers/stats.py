from calendar import monthrange
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query

from ..db import get_conn
from ..nbrb import convert, get_rate
from ..periods import RU_MONTHS, add_months as _add_months
from ..security import get_current_user

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _savings_analytics(conn, start: str, end: str, report_cur: str, rate: float | None):
    """Аналитика по копилкам: накоплено, цели/прогресс, изменение за период и помесячная динамика."""

    def conv(amount, cur, rate_at=None):
        # По курсу на дату операции (снимок), чтобы динамика не «плавала» с курсом.
        try:
            return convert(amount or 0, cur, report_cur, rate_at or rate)
        except ValueError:
            return 0.0

    accounts = conn.execute(
        "SELECT id, name, icon, color, currency, goal_amount FROM accounts "
        "WHERE kind='savings' AND archived=0 ORDER BY sort_order, id"
    ).fetchall()
    if not accounts:
        return None

    ids = [a["id"] for a in accounts]
    qs = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT type, amount, currency, account_id, dest_account_id,
               dest_amount, dest_currency, rate_at, occurred_at
        FROM transactions
        WHERE account_id IN ({qs}) OR dest_account_id IN ({qs})
        """,
        ids + ids,
    ).fetchall()

    id_set = set(ids)
    # Каждое событие — знаковое изменение баланса копилки: в валюте отчёта (по курсу
    # на дату операции) и в родной валюте счёта (для прогресса, независимого от курса).
    events = []  # (account_id, date, delta_report, delta_native)
    for r in rows:
        d = date.fromisoformat(r["occurred_at"])
        ra = r["rate_at"]
        if r["type"] == "transfer":
            if r["account_id"] in id_set:
                events.append((r["account_id"], d, -conv(r["amount"], r["currency"], ra), -(r["amount"] or 0)))
            if r["dest_account_id"] in id_set:
                dc = r["dest_currency"] or r["currency"]
                events.append((r["dest_account_id"], d, conv(r["dest_amount"], dc, ra), r["dest_amount"] or 0))
        elif r["type"] == "income":
            if r["account_id"] in id_set:
                events.append((r["account_id"], d, conv(r["amount"], r["currency"], ra), r["amount"] or 0))
        else:  # expense | debt_payment — расход из копилки
            if r["account_id"] in id_set:
                events.append((r["account_id"], d, -conv(r["amount"], r["currency"], ra), -(r["amount"] or 0)))

    s = date.fromisoformat(start)
    e = date.fromisoformat(end)

    bal = defaultdict(float)        # баланс в валюте отчёта (историческая база)
    bal_native = defaultdict(float) # баланс в родной валюте счёта
    period = defaultdict(float)     # изменение за выбранный период (в валюте отчёта)
    for aid, d, delta, delta_native in events:
        bal[aid] += delta
        bal_native[aid] += delta_native
        if s <= d <= e:
            period[aid] += delta

    items = []
    total_balance = total_goal = total_period = 0.0
    for a in accounts:
        b = round(bal[a["id"]], 2)
        bn = bal_native[a["id"]]
        goal_native = a["goal_amount"] or 0.0
        goal_report = round(conv(goal_native, a["currency"]), 2) if goal_native > 0 else 0.0
        pc = round(period[a["id"]], 2)
        total_balance += b
        total_goal += goal_report
        total_period += pc
        items.append({
            "id": a["id"], "name": a["name"], "icon": a["icon"], "color": a["color"],
            "currency": a["currency"],
            "balance": b,
            "goal": round(goal_native, 2),
            "goal_report": goal_report,
            # прогресс считаем по суммам в родной валюте — он не зависит от курса
            "progress": round(min(100, bn / goal_native * 100), 1) if goal_native > 0 else None,
            "period_change": pc,
        })

    # Помесячная динамика (чистое пополнение + накопленный итог) за период
    series = []
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        m_start = date(y, m, 1)
        m_end = date(y, m, monthrange(y, m)[1])
        net = sum(delta for _, d, delta, _n in events if m_start <= d <= m_end)
        cumulative = sum(delta for _, d, delta, _n in events if d <= m_end)
        series.append({
            "label": f"{RU_MONTHS[m - 1][:3]} {str(y)[2:]}",
            "net": round(net, 2),
            "cumulative": round(cumulative, 2),
        })
        y, m = _add_months(y, m, 1)

    return {
        "total_balance": round(total_balance, 2),
        "total_goal": round(total_goal, 2),
        "progress": round(min(100, total_balance / total_goal * 100), 1) if total_goal > 0 else None,
        "period_change": round(total_period, 2),
        "items": items,
        "series": series,
    }


MONTHS_IN_PERIOD = {"month": 1, "quarter": 3, "half": 6, "year": 12}


def _period_range(period: str, offset: int) -> tuple[str, str, str]:
    """Скользящее окно, которое заканчивается текущим месяцем (он входит в период).
    Календарные полугодия/кварталы затягивали в отчёт ещё не наступившие месяцы."""
    span = MONTHS_IN_PERIOD.get(period, 1)
    today = date.today()

    end_y, end_m = _add_months(today.year, today.month, offset * span)
    start_y, start_m = _add_months(end_y, end_m, -(span - 1))
    start = date(start_y, start_m, 1)
    end = date(end_y, end_m, monthrange(end_y, end_m)[1])

    if span == 1:
        label = f"{RU_MONTHS[end_m - 1]} {end_y}"
    elif start_y == end_y:
        label = f"{RU_MONTHS[start_m - 1][:3]} – {RU_MONTHS[end_m - 1][:3]} {end_y}"
    else:
        label = f"{RU_MONTHS[start_m - 1][:3]} {start_y} – {RU_MONTHS[end_m - 1][:3]} {end_y}"

    return start.isoformat(), end.isoformat(), label


@router.get("")
def stats(
    user: dict = Depends(get_current_user),
    period: str = Query(default="month"),
    offset: int = Query(default=0),
    currency: str | None = None,
):
    report_cur = (currency or user["report_currency"]).upper()
    if report_cur not in {"BYN", "USD"}:
        report_cur = "BYN"
    start, end, label = _period_range(period, offset)
    rate = get_rate()

    def conv(amount: float, cur: str, rate_at: float | None = None) -> float:
        # Конвертируем по курсу на дату операции (снимок), а не по текущему —
        # иначе итоги по прошлым тратам «плывут» вместе с курсом доллара.
        try:
            return convert(amount, cur, report_cur, rate_at or rate)
        except ValueError:
            return 0.0

    with get_conn() as conn:
        expense_rows = conn.execute(
            """
            -- rate_used приоритетнее: у платежа по долгу это фактический курс банка,
            -- по нему же уменьшился долг, иначе расход в отчёте разойдётся с погашением.
            SELECT t.type, t.amount, t.currency, COALESCE(t.rate_used, t.rate_at) AS rate_at,
                   t.category_id, t.debt_id, a.owner_id,
                   c.name AS cat_name, c.icon AS cat_icon, c.color AS cat_color,
                   dt.name AS debt_name, dt.icon AS debt_icon, dt.color AS debt_color
            FROM transactions t
            LEFT JOIN accounts a ON a.id = t.account_id
            LEFT JOIN categories c ON c.id = t.category_id
            LEFT JOIN debts dt ON dt.id = t.debt_id
            WHERE t.type IN ('expense', 'debt_payment') AND t.occurred_at BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchall()

        income_rows = conn.execute(
            """
            SELECT t.amount, t.currency, t.rate_at, a.owner_id
            FROM transactions t
            LEFT JOIN accounts a ON a.id = t.account_id
            WHERE t.type = 'income' AND t.occurred_at BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchall()

        users = conn.execute("SELECT id, display_name FROM users ORDER BY id").fetchall()

        savings = _savings_analytics(conn, start, end, report_cur, rate)

    by_category: dict = {}
    expense_total = 0.0
    for r in expense_rows:
        amount = conv(r["amount"], r["currency"], r["rate_at"])
        expense_total += amount
        if r["type"] == "debt_payment":
            key = f"debt-{r['debt_id']}"
            meta = {
                "id": key,
                "name": r["debt_name"] or "Долг/кредит",
                "icon": r["debt_icon"] or "landmark",
                "color": r["debt_color"] or "#f43f5e",
            }
        else:
            key = r["category_id"] or 0
            meta = {
                "id": r["category_id"],
                "name": r["cat_name"] or "Без категории",
                "icon": r["cat_icon"] or "help-circle",
                "color": r["cat_color"] or "#94a3b8",
            }
        if key not in by_category:
            by_category[key] = {**meta, "amount": 0.0}
        by_category[key]["amount"] += amount

    user_names = {u["id"]: u["display_name"] for u in users}
    by_user: dict = {}

    def bucket(owner_id):
        key = owner_id if owner_id is not None else 0
        if key not in by_user:
            by_user[key] = {
                "id": owner_id,
                "name": user_names.get(owner_id, "Общее"),
                "income": 0.0,
                "expense": 0.0,
            }
        return by_user[key]

    income_total = 0.0
    for r in income_rows:
        amount = conv(r["amount"], r["currency"], r["rate_at"])
        income_total += amount
        bucket(r["owner_id"])["income"] += amount
    for r in expense_rows:
        bucket(r["owner_id"])["expense"] += conv(r["amount"], r["currency"], r["rate_at"])

    categories = sorted(by_category.values(), key=lambda x: x["amount"], reverse=True)
    for c in categories:
        c["amount"] = round(c["amount"], 2)
        c["percent"] = round(c["amount"] / expense_total * 100, 1) if expense_total else 0.0

    users_out = []
    for u in by_user.values():
        u["income"] = round(u["income"], 2)
        u["expense"] = round(u["expense"], 2)
        users_out.append(u)

    return {
        "period": period,
        "offset": offset,
        "label": label,
        "date_from": start,
        "date_to": end,
        "report_currency": report_cur,
        "rate": rate,
        "income_total": round(income_total, 2),
        "expense_total": round(expense_total, 2),
        "net": round(income_total - expense_total, 2),
        "by_category": categories,
        "by_user": users_out,
        "savings": savings,
    }
