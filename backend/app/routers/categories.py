from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_conn
from ..schemas import CategoryIn
from ..security import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _limit_cur(value: str) -> str:
    cur = (value or "BYN").upper()
    if cur not in {"BYN", "USD"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестная валюта лимита")
    return cur


@router.get("")
def list_categories(user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM categories WHERE archived = 0 ORDER BY sort_order, id"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("")
def create_category(body: CategoryIn, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS m FROM categories"
        ).fetchone()["m"]
        cur = conn.execute(
            """
            INSERT INTO categories (name, description, icon, color, monthly_limit, limit_currency, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.name.strip(), body.description.strip(), body.icon, body.color,
                body.monthly_limit or 0, _limit_cur(body.limit_currency), max_order + 1,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
    return {"id": new_id}


@router.patch("/{category_id}")
def update_category(category_id: int, body: CategoryIn, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not exists:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Категория не найдена")
        conn.execute(
            "UPDATE categories SET name = ?, description = ?, icon = ?, color = ?, monthly_limit = ?, limit_currency = ? WHERE id = ?",
            (
                body.name.strip(), body.description.strip(), body.icon, body.color,
                body.monthly_limit or 0, _limit_cur(body.limit_currency), category_id,
            ),
        )
        conn.commit()
    return {"ok": True}


@router.delete("/{category_id}")
def delete_category(category_id: int, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        tx = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE category_id = ?", (category_id,)
        ).fetchone()["c"]
        if tx > 0:
            conn.execute("UPDATE categories SET archived = 1 WHERE id = ?", (category_id,))
        else:
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
    return {"ok": True, "archived": tx > 0}
