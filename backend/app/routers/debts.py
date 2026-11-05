from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_conn
from ..nbrb import convert, get_rate
from ..periods import month_range
from ..schemas import DebtIn
from ..security import get_current_user

router = APIRouter(prefix="/api/debts", tags=["debts"])

VALID_KINDS = {"debt", "credit", "leasing"}
VALID_CURRENCIES = {"BYN", "USD"}


def _list_sql(with_date: bool, archived: bool) -> str:
    """Остаток по обязательству. Если with_date — учитываем платежи по конец месяца
    (историческое состояние остатка на конец выбранного периода)."""
    cond = " AND occurred_at <= :as_of" if with_date else ""
    return f"""
    SELECT d.*, (
        d.remaining_start
        - COALESCE((SELECT SUM(dest_amount) FROM transactions
                    WHERE type='debt_payment' AND debt_id=d.id{cond}), 0)
    ) AS remaining
    FROM debts d
    WHERE d.archived = {1 if archived else 0}
    ORDER BY d.sort_order, d.id
    """


@router.get("")
def list_debts(
    user: dict = Depends(get_current_user),
    month_offset: int | None = None,
    archived: bool = False,
):
    rate = get_rate()
    report_cur = user["report_currency"]
    if month_offset is not None:
        _, as_of, _ = month_range(month_offset)
        sql, params = _list_sql(True, archived), {"as_of": as_of}
    else:
        sql, params = _list_sql(False, archived), {}
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        remaining = max(0.0, round(d.pop("remaining") or 0.0, 2))
        total = round(d["total_amount"] or 0.0, 2)
        paid = round(max(0.0, total - remaining), 2)
        d["remaining"] = remaining
        d["paid"] = paid
        d["progress"] = round(paid / total * 100, 1) if total > 0 else 0.0
        try:
            d["remaining_report"] = convert(remaining, d["currency"], report_cur, rate)
        except ValueError:
            d["remaining_report"] = None
        result.append(d)
    return {"debts": result, "rate": rate, "report_currency": report_cur}


def _validate(body: DebtIn):
    if body.kind not in VALID_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестный тип обязательства")
    if body.currency.upper() not in VALID_CURRENCIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестная валюта")
    if body.pay_day < 0 or body.pay_day > 31:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "День платежа — от 0 до 31")


@router.post("")
def create_debt(body: DebtIn, user: dict = Depends(get_current_user)):
    _validate(body)
    with get_conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS m FROM debts"
        ).fetchone()["m"]
        cur = conn.execute(
            """
            INSERT INTO debts (name, kind, creditor, currency, total_amount,
                               remaining_start, monthly_payment, pay_day, icon, color, note, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.name.strip(), body.kind, body.creditor.strip(), body.currency.upper(),
                body.total_amount, body.remaining_start, body.monthly_payment, body.pay_day,
                body.icon, body.color, body.note.strip(), max_order + 1,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
    return {"id": new_id}


@router.patch("/{debt_id}")
def update_debt(debt_id: int, body: DebtIn, user: dict = Depends(get_current_user)):
    _validate(body)
    new_cur = body.currency.upper()
    with get_conn() as conn:
        old = conn.execute("SELECT * FROM debts WHERE id = ?", (debt_id,)).fetchone()
        if not old:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Обязательство не найдено")

        # Смена валюты: суммы (полная/остаток) приходят уже в новой валюте с фронтенда,
        # а исторические платежи пересчитываем здесь по текущему курсу НБРБ.
        if old["currency"] != new_cur:
            rate = get_rate()
            if not rate:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Курс НБРБ недоступен — смена валюты с пересчётом невозможна",
                )
            f = (1.0 / rate) if new_cur == "USD" else rate
            conn.execute(
                """
                UPDATE transactions SET dest_amount = ROUND(dest_amount * ?, 2), dest_currency = ?
                WHERE debt_id = ? AND type = 'debt_payment'
                """,
                (f, new_cur, debt_id),
            )

        conn.execute(
            """
            UPDATE debts SET name = ?, kind = ?, creditor = ?, currency = ?, total_amount = ?,
                             remaining_start = ?, monthly_payment = ?, pay_day = ?, icon = ?, color = ?, note = ?
            WHERE id = ?
            """,
            (
                body.name.strip(), body.kind, body.creditor.strip(), body.currency.upper(),
                body.total_amount, body.remaining_start, body.monthly_payment, body.pay_day,
                body.icon, body.color, body.note.strip(), debt_id,
            ),
        )
        conn.commit()
    return {"ok": True}


@router.post("/{debt_id}/archive")
def archive_debt(debt_id: int, archived: bool = True, user: dict = Depends(get_current_user)):
    """Убрать выплаченное с дашборда или вернуть обратно. Платежи остаются в истории."""
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM debts WHERE id = ?", (debt_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Обязательство не найдено")
        conn.execute("UPDATE debts SET archived = ? WHERE id = ?", (1 if archived else 0, debt_id))
        conn.commit()
    return {"ok": True, "archived": archived}


@router.delete("/{debt_id}")
def delete_debt(debt_id: int, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        tx = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE debt_id = ?", (debt_id,)
        ).fetchone()["c"]
        if tx > 0:
            conn.execute("UPDATE debts SET archived = 1 WHERE id = ?", (debt_id,))
        else:
            conn.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
        conn.commit()
    return {"ok": True, "archived": tx > 0}
