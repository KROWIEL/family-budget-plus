"""Смена пароля из консоли: новый хеш проходит проверку, сессии закрыты.

Запуск из backend/:  DATA_DIR=/tmp/bp python test_set_password.py
"""
from app.db import get_conn, init_db
from app.security import create_session, verify_password
from app.set_password import set_password

init_db()
with get_conn() as conn:
    conn.execute("DELETE FROM users WHERE username = 'cli-test'")
    conn.execute(
        "INSERT INTO users (username, display_name, password_hash, salt) VALUES ('cli-test', 'T', 'x', 'y')"
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE username = 'cli-test'").fetchone()["id"]
create_session(user_id)

assert set_password("cli-test", "new-secret") == 1
with get_conn() as conn:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    left = conn.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)).fetchone()[0]
assert verify_password("new-secret", row["salt"], row["password_hash"])
assert row["password_hash"].startswith("scrypt$") and left == 0

for bad, err in (("nobody", LookupError), ("cli-test", ValueError)):
    try:
        set_password(bad, "abc" if err is ValueError else "long-enough")
    except err:
        pass
    else:
        raise AssertionError(f"{bad}: expected {err.__name__}")

with get_conn() as conn:
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
print("ok")
