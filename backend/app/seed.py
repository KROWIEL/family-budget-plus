from .config import settings
from .db import get_conn
from .security import hash_password, make_salt


def seed_users() -> None:
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count > 0:
            return
        for u in settings.seed_users:
            salt = make_salt()
            conn.execute(
                """
                INSERT INTO users (username, display_name, password_hash, salt, avatar)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    u["username"],
                    u["display_name"],
                    hash_password(u["password"], salt),
                    salt,
                    u["avatar"],
                ),
            )
        conn.commit()


def seed_accounts() -> None:
    if not settings.seed_default_accounts:
        return
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"]
        if count > 0:
            return
        users = conn.execute(
            "SELECT id, display_name FROM users ORDER BY id LIMIT 2"
        ).fetchall()
        if len(users) < 1:
            return

        u1 = users[0]
        u2 = users[1] if len(users) > 1 else None

        rows: list[tuple] = []
        order = 0

        def add(name, kind, owner_id, currency, icon, color):
            nonlocal order
            rows.append((name, kind, owner_id, currency, icon, color, order))
            order += 1

        add(f"Доход — {u1['display_name']}", "income", u1["id"], "BYN", "briefcase", "#22c55e")
        if u2:
            add(f"Доход — {u2['display_name']}", "income", u2["id"], "BYN", "briefcase", "#10b981")
        add(f"Карта — {u1['display_name']}", "card", u1["id"], "BYN", "credit-card", "#6366f1")
        add(f"Наличные — {u1['display_name']}", "cash", u1["id"], "BYN", "banknote", "#f59e0b")
        if u2:
            add(f"Карта — {u2['display_name']}", "card", u2["id"], "BYN", "credit-card", "#8b5cf6")
            add(f"Наличные — {u2['display_name']}", "cash", u2["id"], "BYN", "banknote", "#f97316")
        add("Общая копилка", "savings", None, "BYN", "piggy-bank", "#ec4899")

        conn.executemany(
            """
            INSERT INTO accounts (name, kind, owner_id, currency, icon, color, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def run_seed() -> None:
    seed_users()
    seed_accounts()
