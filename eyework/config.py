"""
الإعداد
=======
يُقرأ من البيئة مرةً واحدة عند بناء التطبيق، ويُتحقَّق منه كلّه قبل أن يُخدم
أيّ طلب. لا قيمة افتراضية لسرّ: سرٌّ غائب يُسقط الإقلاع ولا يُستبدل بقيمةٍ
صامتة.

لا يُقرأ عند الاستيراد: اختبارٌ يستورد وحدةً من التطبيق لا يحتاج أسراره.

كل المتغيّرات بالبادئة `EYEWORK_` وحدها. ولا يُقرأ `ANTHROPIC_API_KEY` أبداً:
مفتاح المنصّة السريرية لا يصل هذا التطبيق ولو وُجد في البيئة نفسها —
الفوترة وحدود الإنفاق والإلغاء منفصلة.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass

__all__ = ["ConfigError", "Settings", "load", "login_key", "public_origin"]


class ConfigError(RuntimeError):
    """إعدادٌ مفقود أو غير صالح. الرسالة تسمّي المتغيّر ولا تطبع قيمته."""


@dataclass(frozen=True, slots=True)
class Settings:
    #: اتصال الدور `eyework_app` — الوحيد الذي يحمله خادم الويب.
    app_database_url: str
    #: مفتاح HMAC لأسماء الدخول (32 بايتاً). فقدُه يُغلق كل الحسابات.
    login_key: bytes
    #: مطلوبٌ ما لم يُحقن كاتبٌ (في الاختبارات). يتحقّق منه `create_app`.
    anthropic_api_key: str | None
    #: الأصل العام بلا مسار، مثل https://work.example.sa — لفحص Origin والروابط.
    public_origin: str


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} غير مضبوط")
    return value


#: أصلٌ كامل بلا مسار ولا استعلام: مخطّط، ومضيف، ومنفذ اختياري.
_ORIGIN = re.compile(r"^(?P<scheme>https?)://(?P<host>[a-z0-9.-]+)(?P<port>:[0-9]{1,5})?/?$")


def _origin(value: str) -> str:
    match = _ORIGIN.match(value.lower())
    if not match:
        raise ConfigError("EYEWORK_PUBLIC_ORIGIN يجب أن يكون أصلاً كاملاً مثل https://host")
    if match["scheme"] == "http" and match["host"] not in ("localhost", "127.0.0.1"):
        # ملفّ الجلسة `__Host-` يشترط Secure؛ http خارج الجهاز المحلي لا يحمله.
        raise ConfigError("EYEWORK_PUBLIC_ORIGIN يجب أن يكون https خارج localhost")
    return f"{match['scheme']}://{match['host']}{match['port'] or ''}"


def _login_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigError("EYEWORK_LOGIN_KEY ليس base64 صالحاً") from exc
    if len(key) != 32:
        raise ConfigError("EYEWORK_LOGIN_KEY يجب أن يكون 32 بايتاً")
    return key


def load() -> Settings:
    return Settings(
        app_database_url=_required("EYEWORK_APP_DATABASE_URL"),
        login_key=_login_key(_required("EYEWORK_LOGIN_KEY")),
        anthropic_api_key=os.environ.get("EYEWORK_ANTHROPIC_API_KEY", "").strip() or None,
        public_origin=_origin(_required("EYEWORK_PUBLIC_ORIGIN")),
    )


def login_key() -> bytes:
    """مفتاح HMAC وحده — لأداة المشغّل التي لا تحتاج بقية الإعداد."""
    return _login_key(_required("EYEWORK_LOGIN_KEY"))


def public_origin() -> str:
    return _origin(_required("EYEWORK_PUBLIC_ORIGIN"))
