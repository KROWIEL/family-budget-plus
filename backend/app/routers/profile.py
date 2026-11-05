from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
import sqlite3

from ..config import settings
from ..db import SCHEMA, _migrate, get_conn
from ..schemas import PasswordIn, ProfileIn
from ..security import get_current_user, hash_password, make_salt, verify_password

router = APIRouter(prefix="/api/profile", tags=["profile"])

VALID_AVATARS = {
    "fox", "cat", "dog", "owl", "bear", "panda", "penguin", "koala",
    "lion", "tiger", "rabbit", "hamster", "mouse", "frog", "monkey", "chick",
    "unicorn", "dragon", "wolf", "hedgehog", "pig", "cow", "elephant", "octopus",
    "whale", "turtle", "butterfly", "parrot", "deer", "raccoon", "crab", "dolphin",
}
VALID_THEMES = {"dark", "light"}
VALID_CURRENCIES = {"BYN", "USD"}


@router.get("/users")
def list_users(user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, display_name, avatar FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


@router.patch("")
def update_profile(body: ProfileIn, user: dict = Depends(get_current_user)):
    fields, values = [], []
    if body.display_name is not None:
        fields.append("display_name = ?")
        values.append(body.display_name.strip())
    if body.avatar is not None:
        if body.avatar not in VALID_AVATARS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестный аватар")
        fields.append("avatar = ?")
        values.append(body.avatar)
    if body.theme is not None:
        if body.theme not in VALID_THEMES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестная тема")
        fields.append("theme = ?")
        values.append(body.theme)
    if body.report_currency is not None:
        cur = body.report_currency.upper()
        if cur not in VALID_CURRENCIES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестная валюта")
        fields.append("report_currency = ?")
        values.append(cur)

    if fields:
        values.append(user["id"])
        with get_conn() as conn:
            conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "avatar": row["avatar"],
        "theme": row["theme"],
        "report_currency": row["report_currency"],
    }


@router.post("/password")
def change_password(body: PasswordIn, user: dict = Depends(get_current_user)):
    if not verify_password(body.current_password, user["salt"], user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Текущий пароль неверный")
    salt = make_salt()
    new_hash = hash_password(body.new_password, salt)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (new_hash, salt, user["id"]),
        )
        conn.commit()
    return {"ok": True}


@router.get("/backup")
def download_backup(user: dict = Depends(get_current_user)):
    dest = settings.data_dir / "budget-export.db"
    if dest.exists():
        dest.unlink()
    src = sqlite3.connect(settings.db_path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return FileResponse(dest, filename="budget.db", media_type="application/octet-stream")


# Переносим только данные: логины, пароли и сессии остаются текущими,
# иначе после отката все вылетят из аккаунтов со старыми паролями.
# Порядок важен — сначала то, на что ссылаются остальные таблицы.
RESTORE_TABLES = [
    ("accounts", "id, name, kind, owner_id, currency, icon, color, goal_amount, sort_order, archived, created_at"),
    ("categories", "id, name, description, icon, color, monthly_limit, limit_currency, sort_order, archived, created_at"),
    ("debts", "id, name, kind, creditor, currency, total_amount, remaining_start, monthly_payment, icon, color, note, pay_day, sort_order, archived, created_at"),
    ("transactions", "id, type, amount, currency, account_id, dest_account_id, dest_amount, dest_currency, rate_used, rate_at, category_id, debt_id, note, occurred_at, created_by, created_at"),
    ("rates", "rate_date, usd_byn, fetched_at"),
]

# Старые id пользователей заменяем своими: сперва по логину, иначе по тому же id.
_USER_REF = {
    "accounts": "owner_id",
    "transactions": "created_by",
}


def _prepare_upload(raw: bytes) -> Path:
    """Кладём копию на диск и догоняем её до текущей схемы (старым не хватает полей)."""
    if not raw.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Это не файл базы SQLite")
    tmp = settings.data_dir / "restore-upload.db"
    tmp.write_bytes(raw)
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл базы повреждён")
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"accounts", "transactions", "users"} <= tables:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Это база не от Budget+")
        conn.executescript(SCHEMA)   # добавит таблицы, которых в старой копии не было
        _migrate(conn)               # добавит недостающие колонки и заполнит rate_at
        conn.commit()
    finally:
        conn.close()
    return tmp


@router.post("/restore")
async def restore_backup(request: Request, user: dict = Depends(get_current_user)):
    tmp = _prepare_upload(await request.body())

    # Страховка: текущее состояние остаётся на диске рядом с базой.
    safety = settings.data_dir / "budget-before-restore.db"
    if safety.exists():
        safety.unlink()
    live, snap = sqlite3.connect(settings.db_path), sqlite3.connect(safety)
    try:
        live.backup(snap)
    finally:
        snap.close()
        live.close()

    with get_conn() as conn:
        conn.execute("ATTACH DATABASE ? AS src", (str(tmp),))
        try:
            for table, _ in reversed(RESTORE_TABLES):
                conn.execute(f"DELETE FROM main.{table}")
            for table, cols in RESTORE_TABLES:
                ref = _USER_REF.get(table)
                select = ", ".join(
                    f"""(SELECT COALESCE(
                             (SELECT u.id FROM main.users u WHERE u.username = su.username),
                             (SELECT u2.id FROM main.users u2 WHERE u2.id = su.id))
                         FROM src.users su WHERE su.id = s.{c})"""
                    if c == ref else f"s.{c}"
                    for c in (x.strip() for x in cols.split(","))
                )
                conn.execute(f"INSERT INTO main.{table} ({cols}) SELECT {select} FROM src.{table} s")
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Не удалось перенести данные: {e}")
        finally:
            conn.execute("DETACH DATABASE src")

    tmp.unlink(missing_ok=True)
    return {"ok": True}
