"""Курс НБРБ подставляет сумму зачисления, ручная правка её не затирает.

Запуск из backend/:  DATA_DIR=/tmp/bp python test_cross_sides.py
"""
from app.routers.transactions import cross_sides

applied, used = cross_sides(100, "USD", "BYN", 3.0, 320)
assert applied == 320 and used == 3.2, (applied, used)

applied, used = cross_sides(100, "USD", "BYN", 3.0, None)
assert applied == 300 and used == 3.0, (applied, used)

applied, used = cross_sides(50, "BYN", "BYN", 3.0, 999)
assert applied == 50 and used is None, (applied, used)

applied, used = cross_sides(310, "BYN", "USD", None, 100)
assert applied == 100 and used == 3.1, (applied, used)

print("ok")
