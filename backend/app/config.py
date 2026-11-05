import os
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Простые настройки из переменных окружения (без лишних зависимостей)."""

    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("DATA_DIR", "/data"))
        self.db_path = self.data_dir / "budget.db"

        self.session_days = int(os.getenv("SESSION_DAYS", "30"))
        # Secure-cookie: включать за HTTPS (прод). Для локального http — false.
        self.cookie_secure = _bool(os.getenv("COOKIE_SECURE"), False)

        # Статика собранного фронтенда
        self.static_dir = Path(os.getenv("STATIC_DIR", "/app/static"))

        self.nbrb_auto_refresh = _bool(os.getenv("NBRB_AUTO_REFRESH"), True)
        self.seed_default_accounts = _bool(os.getenv("SEED_DEFAULT_ACCOUNTS"), True)

        self.seed_users = self._read_seed_users()

    def _read_seed_users(self) -> list[dict]:
        users: list[dict] = []
        for idx in (1, 2):
            username = os.getenv(f"SEED_USER{idx}_USERNAME")
            password = os.getenv(f"SEED_USER{idx}_PASSWORD")
            if not username or not password:
                continue
            users.append(
                {
                    "username": username.strip().lower(),
                    "display_name": os.getenv(f"SEED_USER{idx}_NAME", username).strip(),
                    "password": password,
                    "avatar": os.getenv(f"SEED_USER{idx}_AVATAR", "fox").strip(),
                }
            )
        return users


settings = Settings()
