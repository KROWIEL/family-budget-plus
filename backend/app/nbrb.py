from datetime import date

import httpx

from .config import settings
from .db import get_conn

NBRB_URL = "https://api.nbrb.by/exrates/rates/USD?parammode=2"


def _cached_rate(rate_date: str) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT usd_byn FROM rates WHERE rate_date = ?", (rate_date,)
        ).fetchone()
    return float(row["usd_byn"]) if row else None


def _latest_rate() -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT usd_byn FROM rates ORDER BY rate_date DESC LIMIT 1"
        ).fetchone()
    return float(row["usd_byn"]) if row else None


def _rate_on_or_before(rate_date: str) -> float | None:
    """Ближайший известный курс на дату или раньше неё."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT usd_byn FROM rates WHERE rate_date <= ? ORDER BY rate_date DESC LIMIT 1",
            (rate_date,),
        ).fetchone()
    return float(row["usd_byn"]) if row else None


def _store_rate(rate_date: str, usd_byn: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO rates (rate_date, usd_byn) VALUES (?, ?)
            ON CONFLICT(rate_date) DO UPDATE SET usd_byn = excluded.usd_byn,
                                                 fetched_at = datetime('now')
            """,
            (rate_date, usd_byn),
        )
        conn.commit()


def fetch_from_nbrb(on_date: str | None = None) -> float:
    """Запрос официального курса USD с сайта НБРБ. 1 USD = X BYN.
    Если задана on_date (YYYY-MM-DD) — курс на конкретную дату."""
    url = NBRB_URL if on_date is None else f"{NBRB_URL}&ondate={on_date}"
    resp = httpx.get(url, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    usd_byn = float(data["Cur_OfficialRate"]) / float(data.get("Cur_Scale", 1))
    return round(usd_byn, 4)


def refresh_rate() -> float:
    """Принудительно обновить курс на сегодня."""
    usd_byn = fetch_from_nbrb()
    _store_rate(date.today().isoformat(), usd_byn)
    return usd_byn


def get_rate() -> float | None:
    """Актуальный курс USD->BYN. Кэш на день, при необходимости — запрос к НБРБ."""
    today = date.today().isoformat()
    cached = _cached_rate(today)
    if cached is not None:
        return cached
    if settings.nbrb_auto_refresh:
        try:
            return refresh_rate()
        except Exception:
            pass
    # Фолбэк: последний известный курс, если сеть недоступна
    return _latest_rate()


def get_rate_for_date(rate_date: str) -> float | None:
    """Курс USD->BYN на дату операции (снимок). Кэшируется в таблице rates,
    чтобы статистика по прошлым тратам не «плавала» вместе с текущим курсом."""
    today = date.today().isoformat()
    if rate_date >= today:
        return get_rate()

    cached = _cached_rate(rate_date)
    if cached is not None:
        return cached

    if settings.nbrb_auto_refresh:
        try:
            usd_byn = fetch_from_nbrb(rate_date)
            _store_rate(rate_date, usd_byn)
            return usd_byn
        except Exception:
            pass

    # Фолбэк: ближайший ранее известный курс, иначе последний вообще
    return _rate_on_or_before(rate_date) or _latest_rate()


def convert(amount: float, from_cur: str, to_cur: str, rate: float | None) -> float:
    from_cur = from_cur.upper()
    to_cur = to_cur.upper()
    if from_cur == to_cur:
        return round(amount, 2)
    if rate is None or rate <= 0:
        raise ValueError("Курс НБРБ недоступен")
    if from_cur == "USD" and to_cur == "BYN":
        return round(amount * rate, 2)
    if from_cur == "BYN" and to_cur == "USD":
        return round(amount / rate, 2)
    raise ValueError(f"Неизвестная пара валют: {from_cur}->{to_cur}")
