"""
كلمات المرور
============
`hashlib.scrypt` من المكتبة القياسية بمعاملات المنصّة نفسها (N=2^15, r=8,
p=1) — منسوخة لا مستوردة. والمعاملات مضمَّنة في الصيغة فتبقى قابلة للترقية.

`maxmem` صريح: حدّ OpenSSL الافتراضي 32 MiB هو بالضبط ما تحتاجه هذه
المعاملات (128·N·r) فيفشل بلا هامش.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

__all__ = ["hash_password", "verify_password"]

_SCRYPT = {"n": 2**15, "r": 8, "p": 1, "dklen": 64, "maxmem": 64 * 1024 * 1024}
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """`scrypt$<salt>$<hash>`."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """مقارنةٌ بزمنٍ ثابت. صيغةٌ مجهولة ⇒ `False`، لا استثناءٌ يكشف السبب."""
    try:
        scheme, salt_hex, expected_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived.hex(), expected_hex)
