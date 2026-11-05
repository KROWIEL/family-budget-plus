from calendar import monthrange
from datetime import date

RU_MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def add_months(y: int, m: int, delta: int) -> tuple[int, int]:
    idx = (y * 12 + (m - 1)) + delta
    return idx // 12, idx % 12 + 1


def month_range(offset: int) -> tuple[str, str, str]:
    """Границы календарного месяца со сдвигом offset от текущего.
    Возвращает (start ISO, end ISO, подпись)."""
    today = date.today()
    yy, mm = add_months(today.year, today.month, offset)
    start = date(yy, mm, 1)
    end = date(yy, mm, monthrange(yy, mm)[1])
    return start.isoformat(), end.isoformat(), f"{RU_MONTHS[mm - 1]} {yy}"
