"""Принудительная смена пароля из консоли, без старого пароля.

    python -m app.set_password <логин>

Пароль спрашивается дважды без эха и хешируется так же, как в приложении (scrypt с новой
солью). Все сессии пользователя закрываются: войти можно будет только с новым паролем.
"""
import getpass
import sys

from .db import get_conn
from .security import hash_password, make_salt

MIN_LENGTH = 4  # как у смены пароля в профиле (schemas.PasswordIn)


def set_password(username: str, password: str) -> int:
    """Возвращает число закрытых сессий. LookupError, если такого логина нет."""
    if not MIN_LENGTH <= len(password) <= 100:
        raise ValueError(f"Пароль должен быть от {MIN_LENGTH} до 100 символов")
    salt = make_salt()
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            raise LookupError(f"Пользователь {username!r} не найден")
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (hash_password(password, salt), salt, row["id"]),
        )
        closed = conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],)).rowcount
        conn.commit()
    return closed


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    username = sys.argv[1]
    password = getpass.getpass(f"Новый пароль для {username}: ")
    if password != getpass.getpass("Ещё раз: "):
        print("Пароли не совпали, ничего не изменено", file=sys.stderr)
        return 1
    try:
        closed = set_password(username, password)
    except (LookupError, ValueError) as e:
        print(f"{e}, ничего не изменено", file=sys.stderr)
        return 1
    print(f"Пароль для {username} изменён, закрыто сессий: {closed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
