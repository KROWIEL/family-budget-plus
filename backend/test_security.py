"""Хеширование паролей: scrypt, совместимость со старыми md5-хешами.

Запуск из backend/:  DATA_DIR=/tmp/bp python test_security.py
"""
import hashlib

from app.security import hash_password, needs_rehash, verify_password

h = hash_password("secret", "salt")
assert h.startswith("scrypt$") and not needs_rehash(h), h
assert verify_password("secret", "salt", h)
assert not verify_password("wrong", "salt", h)
assert not verify_password("secret", "salt", "scrypt$broken")

legacy = hashlib.md5(b"saltsecret").hexdigest()
assert verify_password("secret", "salt", legacy) and needs_rehash(legacy)
assert not verify_password("wrong", "salt", legacy)

print("ok")
