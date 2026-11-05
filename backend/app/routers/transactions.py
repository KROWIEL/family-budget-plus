from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..db import get_conn
from ..nbrb import convert, get_rate, get_rate_for_date
from ..schemas import TransactionIn
from ..security import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

VALID_TYPES = {"income", "expense", "transfer", "debt_payment"}


def cross_sides(
    card_amount: float,
    card_cur: str,
    target_cur: str,
    rate: float | None,
    applied_override: float | None,
) -> tuple[float, float | None]:
    """Сумма на стороне получателя (счёт перевода или долг) и курс операции.

    applied_override — фактическая сумма в валюте получателя, если банк сконвертировал
    не по НБРБ. Тогда rate_used — курс именно этой операции, а не официальный.
    """
    card_cur = card_cur.upper()
    target_cur = target_cur.upper()
    if applied_override is not None and card_cur != target_cur:
        applied = round(float(applied_override), 2)
        if applied <= 0:
            raise ValueError("Сумма зачисления должна быть больше нуля")
        return applied, _implied_rate(card_amount, card_cur, applied, target_cur)
    applied = convert(card_amount, card_cur, target_cur, rate)
    return applied, (rate if card_cur != target_cur else None)


def _implied_rate(card_amount: float, card_cur: str, applied: float, debt_cur: str) -> float | None:
    if card_amount <= 0 or applied <= 0:
        return None
    if card_cur == "USD" and debt_cur == "BYN":
        return round(applied / card_amount, 4)
    if card_cur == "BYN" and debt_cur == "USD":
        return round(card_amount / applied, 4)
    return None


def _get_account(conn, account_id: int):
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Счёт не найден")
    return row


def _build_payload(conn, body: TransactionIn) -> dict:
    if body.type not in VALID_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестный тип операции")

    occurred = body.occurred_at or date.today().isoformat()
    src = _get_account(conn, body.account_id)

    payload = {
        "type": body.type,
        "amount": round(body.amount, 2),
        "currency": src["currency"],
        "account_id": body.account_id,
        "dest_account_id": None,
        "dest_amount": None,
        "dest_currency": None,
        "rate_used": None,
        # Снимок курса USD->BYN на дату операции — чтобы статистика не «плавала»
        "rate_at": get_rate_for_date(occurred),
        "category_id": None,
        "debt_id": None,
        "note": body.note.strip(),
        "occurred_at": occurred,
    }

    if body.type == "expense":
        if body.category_id is not None:
            cat = conn.execute(
                "SELECT id FROM categories WHERE id = ?", (body.category_id,)
            ).fetchone()
            if cat is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Категория не найдена")
            payload["category_id"] = body.category_id

    elif body.type == "transfer":
        if not body.dest_account_id or body.dest_account_id == body.account_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нужен другой счёт назначения")
        dest = _get_account(conn, body.dest_account_id)
        rate = get_rate()
        try:
            dest_amount, used = cross_sides(
                payload["amount"], src["currency"], dest["currency"], rate, body.applied_amount
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        payload["dest_account_id"] = dest["id"]
        payload["dest_amount"] = dest_amount
        payload["dest_currency"] = dest["currency"]
        payload["rate_used"] = used

    elif body.type == "debt_payment":
        if not body.debt_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не указан долг/кредит")
        debt = conn.execute(
            "SELECT * FROM debts WHERE id = ?", (body.debt_id,)
        ).fetchone()
        if debt is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Обязательство не найдено")
        rate = get_rate()
        try:
            applied, used = cross_sides(
                payload["amount"], src["currency"], debt["currency"], rate, body.applied_amount
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        payload["debt_id"] = debt["id"]
        payload["dest_amount"] = applied            # сумма в валюте долга (идёт в погашение)
        payload["dest_currency"] = debt["currency"]
        payload["rate_used"] = used

    return payload


@router.get("")
def list_transactions(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=100, le=1000),
    type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    category_id: int | None = None,
    debt_id: int | None = None,
):
    where = ["1=1"]
    params: list = []
    if type in VALID_TYPES:
        where.append("t.type = ?")
        params.append(type)
    if date_from:
        where.append("t.occurred_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.occurred_at <= ?")
        params.append(date_to)
    if category_id is not None:
        where.append("t.category_id = ?")
        params.append(category_id)
    if debt_id is not None:
        where.append("t.debt_id = ?")
        params.append(debt_id)

    sql = f"""
        SELECT t.*,
               a.name AS account_name, a.icon AS account_icon, a.color AS account_color,
               d.name AS dest_account_name,
               c.name AS category_name, c.icon AS category_icon, c.color AS category_color,
               dt.name AS debt_name, dt.icon AS debt_icon, dt.color AS debt_color,
               u.display_name AS created_by_name
        FROM transactions t
        LEFT JOIN accounts a ON a.id = t.account_id
        LEFT JOIN accounts d ON d.id = t.dest_account_id
        LEFT JOIN categories c ON c.id = t.category_id
        LEFT JOIN debts dt ON dt.id = t.debt_id
        LEFT JOIN users u ON u.id = t.created_by
        WHERE {' AND '.join(where)}
        ORDER BY t.occurred_at DESC, t.id DESC
        LIMIT ?
    """
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.post("")
def create_transaction(body: TransactionIn, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        payload = _build_payload(conn, body)
        cur = conn.execute(
            """
            INSERT INTO transactions
                (type, amount, currency, account_id, dest_account_id, dest_amount,
                 dest_currency, rate_used, rate_at, category_id, debt_id, note, occurred_at, created_by)
            VALUES (:type, :amount, :currency, :account_id, :dest_account_id, :dest_amount,
                    :dest_currency, :rate_used, :rate_at, :category_id, :debt_id, :note,
                    :occurred_at, :created_by)
            """,
            {**payload, "created_by": user["id"]},
        )
        conn.commit()
        new_id = cur.lastrowid
    return {"id": new_id}


@router.patch("/{tx_id}")
def update_transaction(tx_id: int, body: TransactionIn, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        if not exists:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Операция не найдена")
        payload = _build_payload(conn, body)
        conn.execute(
            """
            UPDATE transactions SET
                type = :type, amount = :amount, currency = :currency, account_id = :account_id,
                dest_account_id = :dest_account_id, dest_amount = :dest_amount,
                dest_currency = :dest_currency, rate_used = :rate_used, rate_at = :rate_at,
                category_id = :category_id,
                debt_id = :debt_id, note = :note, occurred_at = :occurred_at
            WHERE id = :id
            """,
            {**payload, "id": tx_id},
        )
        conn.commit()
    return {"ok": True}


@router.delete("/{tx_id}")
def delete_transaction(tx_id: int, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
    return {"ok": True}
