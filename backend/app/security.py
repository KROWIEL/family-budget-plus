import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Cookie, HTTPException, status

from .config import settings
from .db import get_conn

SESSION_COOKIE = "bp_session"


def make_salt() -> str:
    return secrets.token_hex(16)


SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
SCRYPT_PREFIX = "scrypt$"


def _scrypt(password: str, salt: str, n: int, r: int, p: int) -> str:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt.encode("utf-8"), n=n, r=r, p=p, dklen=32
    ).hex()


def hash_password(password: str, salt: str) -> str:
    """Формат: scrypt$n$r$p$hex — параметры хранятся рядом с хешем."""
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"{SCRYPT_PREFIX}{SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${digest}"


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    if expected_hash.startswith(SCRYPT_PREFIX):
        try:
            n, r, p, digest = expected_hash[len(SCRYPT_PREFIX):].split("$")
            actual = _scrypt(password, salt, int(n), int(r), int(p))
        except ValueError:
            return False
        return secrets.compare_digest(actual, digest)
    # Старые базы: md5(salt + password). Такой хеш заменяется на scrypt при входе.
    legacy = hashlib.md5((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(legacy, expected_hash)


def needs_rehash(stored_hash: str) -> bool:
    return not stored_hash.startswith(f"{SCRYPT_PREFIX}{SCRYPT_N}${SCRYPT_R}${SCRYPT_P}$")


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(days=settings.session_days)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires),
        )
        conn.commit()
    return token


def destroy_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def get_current_user(bp_session: str | None = Cookie(default=None)) -> dict:
    if not bp_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не авторизован")
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (bp_session, datetime.utcnow().isoformat()),
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия истекла")
    return dict(row)
