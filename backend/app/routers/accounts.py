from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_conn
from ..nbrb import convert, get_rate
from ..periods import month_range
from ..schemas import AccountIn
from ..security import get_current_user

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

VALID_KINDS = {"income", "card", "cash", "savings"}
VALID_CURRENCIES = {"BYN", "USD"}


def _balance_sql(with_date: bool) -> str:
    """Баланс счёта. Если with_date — учитываем только операции по конец месяца
    (состояние на конец периода: остаток естественно переходит в следующий месяц)."""
    cond = " AND occurred_at <= :as_of" if with_date else ""
    return f"""
    SELECT a.*, (
          COALESCE((SELECT SUM(amount)      FROM transactions WHERE type='income'       AND account_id=a.id{cond}), 0)
        + COALESCE((SELECT SUM(dest_amount) FROM transactions WHERE type='transfer'     AND dest_account_id=a.id{cond}), 0)
        - COALESCE((SELECT SUM(amount)      FROM transactions WHERE type='expense'      AND account_id=a.id{cond}), 0)
        - COALESCE((SELECT SUM(amount)      FROM transactions WHERE type='transfer'     AND account_id=a.id{cond}), 0)
        - COALESCE((SELECT SUM(amount)      FROM transactions WHERE type='debt_payment' AND account_id=a.id{cond}), 0)
    ) AS balance
    FROM accounts a
    WHERE a.archived = 0
    ORDER BY a.sort_order, a.id
    """


@router.get("")
def list_accounts(
    user: dict = Depends(get_current_user),
    month_offset: int | None = None,
):
    rate = get_rate()
    report_cur = user["report_currency"]
    if month_offset is not None:
        _, as_of, _ = month_range(month_offset)
        sql, params = _balance_sql(True), {"as_of": as_of}
    else:
        sql, params = _balance_sql(False), {}
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        balance = round(d.pop("balance") or 0.0, 2)
        d["balance"] = balance
        try:
            d["balance_report"] = convert(balance, d["currency"], report_cur, rate)
        except ValueError:
            d["balance_report"] = None
        result.append(d)
    return {"accounts": result, "rate": rate, "report_currency": report_cur}


def _validate(body: AccountIn):
    if body.kind not in VALID_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестный тип счёта")
    if body.currency.upper() not in VALID_CURRENCIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестная валюта")


@router.post("")
def create_account(body: AccountIn, user: dict = Depends(get_current_user)):
    _validate(body)
    owner_id = None if body.kind == "savings" else body.owner_id
    goal = body.goal_amount if body.kind == "savings" else 0.0
    with get_conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS m FROM accounts"
        ).fetchone()["m"]
        cur = conn.execute(
            """
            INSERT INTO accounts (name, kind, owner_id, currency, icon, color, goal_amount, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.name.strip(),
                body.kind,
                owner_id,
                body.currency.upper(),
                body.icon,
                body.color,
                goal,
                max_order + 1,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
    return {"id": new_id}


def _conversion_factor(old_cur: str, new_cur: str, rate: float) -> float:
    """Множитель для перевода суммы из old_cur в new_cur (только BYN<->USD)."""
    if old_cur == "BYN" and new_cur == "USD":
        return 1.0 / rate
    if old_cur == "USD" and new_cur == "BYN":
        return rate
    return 1.0


@router.patch("/{account_id}")
def update_account(account_id: int, body: AccountIn, user: dict = Depends(get_current_user)):
    _validate(body)
    owner_id = None if body.kind == "savings" else body.owner_id
    goal = body.goal_amount if body.kind == "savings" else 0.0
    new_cur = body.currency.upper()
    with get_conn() as conn:
        old = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not old:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Счёт не найден")

        # Смена валюты: пересчитываем операции этого счёта по текущему курсу НБРБ,
        # чтобы баланс автоматически стал корректным в новой валюте.
        if old["currency"] != new_cur:
            rate = get_rate()
            if not rate:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Курс НБРБ недоступен — смена валюты с пересчётом невозможна",
                )
            f = _conversion_factor(old["currency"], new_cur, rate)
            conn.execute(
                "UPDATE transactions SET amount = ROUND(amount * ?, 2), currency = ? WHERE account_id = ?",
                (f, new_cur, account_id),
            )
            conn.execute(
                """
                UPDATE transactions SET dest_amount = ROUND(dest_amount * ?, 2), dest_currency = ?
                WHERE dest_account_id = ? AND dest_amount IS NOT NULL
                """,
                (f, new_cur, account_id),
            )
            # цель копилки тоже пересчитываем в новую валюту
            goal = round(goal * f, 2)

        conn.execute(
            """
            UPDATE accounts SET name = ?, kind = ?, owner_id = ?, currency = ?, icon = ?, color = ?, goal_amount = ?
            WHERE id = ?
            """,
            (body.name.strip(), body.kind, owner_id, new_cur, body.icon, body.color, goal, account_id),
        )
        conn.commit()
    return {"ok": True}


@router.delete("/{account_id}")
def delete_account(account_id: int, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        tx = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE account_id = ? OR dest_account_id = ?",
            (account_id, account_id),
        ).fetchone()["c"]
        if tx > 0:
            # Есть операции — архивируем, чтобы не терять историю и статистику
            conn.execute("UPDATE accounts SET archived = 1 WHERE id = ?", (account_id,))
        else:
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
    return {"ok": True, "archived": tx > 0}
