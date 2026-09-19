"""
ناقل الشبكة — الحدّ الخارجي الوحيد
===================================
هذه هي الوحدة الوحيدة في المستودع التي تتصل بالشبكة، واختبار معماري يفشل إن
استورد أي ملف آخر `requests` أو `urllib` أو `httpx`. حدٌّ واحد يعني أن سؤال
«ما الذي يغادر هذا النظام؟» له جواب واحد يُقرأ في ملف واحد.

النقل محقون لا مستورَد: `Transport` بروتوكول، والمنفّذ الفعلي واحدٌ من عدة
تحقيقات. الاختبارات تحقن ناقلاً يسجّل كل طلب، فيصير إثبات «لا PHI يغادر»
قياساً على المسار الحقيقي لا مراجعةً للشيفرة.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from core.rate_limit import RateLimit, RateLimiter

__all__ = [
    "NCBI_LIMIT",
    "NCBI_LIMIT_WITH_KEY",
    "Request",
    "RequestsTransport",
    "Response",
    "Transport",
    "TransportError",
    "USER_AGENT",
    "default_transport",
]

#: يطلب NCBI تعريفاً بالعميل. بلا `email` ولا أي شيء يخص مريضاً.
USER_AGENT = "symbol-rehab/1.0 (clinical evidence retrieval; +https://symbolai.net)"

#: حدود NCBI المعلنة لـE-utilities: ثلاثة طلبات في الثانية بلا مفتاح، وعشرة
#: معه. نطبّقها على أنفسنا قبل أن يطبّقها الطرف الآخر بالحظر.
NCBI_LIMIT = RateLimit(max_events=3, window_seconds=1.0)
NCBI_LIMIT_WITH_KEY = RateLimit(max_events=10, window_seconds=1.0)

_TIMEOUT_SECONDS = 15.0


class TransportError(Exception):
    """تعذّر الوصول إلى المصدر الخارجي. لا يُفسَّر غيابُ الشبكة غيابَ دليل."""


@dataclass(frozen=True, slots=True)
class Request:
    url: str
    params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class Transport(Protocol):
    """كل ما يحتاجه هذا النظام من الشبكة: طلب واحد بلا حالة."""

    def fetch(self, request: Request) -> Response: ...


class RequestsTransport:
    """
    المنفّذ الفعلي. **الموضع الوحيد الذي يُستورد فيه `requests`.**

    إعادة محاولة واحدة على خطأ خادم أو انقطاع، لا أكثر: مصدرٌ يفشل مرتين
    متتاليتين مصدرٌ غير متاح، وتكرار المحاولة عليه إغراقٌ له وتأخيرٌ لنا.
    """

    def __init__(self, *, timeout: float = _TIMEOUT_SECONDS) -> None:
        self._timeout = timeout
        self._limiter = RateLimiter(
            NCBI_LIMIT_WITH_KEY if os.environ.get("NCBI_API_KEY") else NCBI_LIMIT
        )

    def fetch(self, request: Request) -> Response:
        import requests   # استيراد موضعي: يبقى اسم المكتبة داخل هذه الدالة

        self._limiter.check("ncbi")

        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                response = requests.get(
                    request.url,
                    params=dict(request.params),
                    timeout=self._timeout,
                    headers={"User-Agent": USER_AGENT},
                )
            except requests.exceptions.RequestException as exc:
                last_error = exc
            else:
                if response.status_code < 500:
                    return Response(status=response.status_code, content=response.content)
                last_error = TransportError(f"خطأ خادم {response.status_code}")

            if attempt == 2:
                break
            self._limiter.check("ncbi")

        raise TransportError(f"تعذّر الوصول إلى المصدر الخارجي: {last_error}")


def default_transport() -> Transport:
    """يُستدعى عند الحاجة لا عند التحميل، فتبقى الاختبارات بلا شبكة."""
    return RequestsTransport()
