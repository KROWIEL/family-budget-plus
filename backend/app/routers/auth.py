import time

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from ..config import settings
from ..db import get_conn
from ..schemas import LoginIn
from ..security import (
    SESSION_COOKIE,
    create_session,
    destroy_session,
    get_current_user,
    hash_password,
    make_salt,
    needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _public_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "avatar": row["avatar"],
        "theme": row["theme"],
        "report_currency": row["report_currency"],
    }


MAX_FAILED_LOGINS = 10
FAILED_LOGIN_WINDOW = 15 * 60
# ponytail: счётчик в памяти процесса — сбрасывается при рестарте и не делится между
# воркерами; для одного контейнера с одним воркером этого достаточно.
_failed_logins: dict[str, list[float]] = {}


def _recent_failures(ip: str, now: float) -> list[float]:
    recent = [t for t in _failed_logins.get(ip, []) if now - t < FAILED_LOGIN_WINDOW]
    _failed_logins[ip] = recent
    return recent


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if len(_recent_failures(ip, now)) >= MAX_FAILED_LOGINS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Слишком много попыток, попробуйте позже")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (body.username.strip().lower(),)
        ).fetchone()
    if row is None or not verify_password(body.password, row["salt"], row["password_hash"]):
        _failed_logins[ip] = [*_failed_logins[ip], now]
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    _failed_logins.pop(ip, None)

    if needs_rehash(row["password_hash"]):
        salt = make_salt()
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                (hash_password(body.password, salt), salt, row["id"]),
            )
            conn.commit()

    token = create_session(row["id"])
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=60 * 60 * 24 * settings.session_days,
        path="/",
    )
    return _public_user(dict(row))


@router.post("/logout")
def logout(response: Response, bp_session: str | None = Cookie(default=None)):
    if bp_session:
        destroy_session(bp_session)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return _public_user(user)
