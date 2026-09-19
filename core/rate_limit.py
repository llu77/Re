"""
حدود المعدل
============
دلو رموز ثابت النافذة، في الذاكرة.

حدّ واضح ومقصود: هذا المخزن داخل العملية الواحدة. مع عدة عمليات يصبح الحد
الفعلي = الحد × عدد العمليات. النشر متعدد العمليات يحتاج مخزناً مشتركاً
(Redis) خلف نفس الواجهة `check()`، والتبديل لا يمس المستدعين.

يُطبَّق على المصادقة هنا (القسم 1)، وعلى المصادر الخارجية وتوليد الصور في
القسمين 3 و4.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from core.clock import now

__all__ = [
    "AUTH_LIMIT",
    "EVIDENCE_LIMIT",
    "RateLimit",
    "RateLimitExceeded",
    "RateLimiter",
]


class RateLimitExceeded(Exception):
    """تجاوز الحد. تحمل الثواني المتبقية حتى السماح التالي."""

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__(f"تجاوز حد المعدل. أعد المحاولة بعد {retry_after_seconds:.0f} ثانية")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class RateLimit:
    max_events: int
    window_seconds: float


#: المصادقة: عشر محاولات في الدقيقة لكل معرّف.
AUTH_LIMIT = RateLimit(max_events=10, window_seconds=60.0)

#: بحث الأدلة: عشرون بحثاً في الدقيقة لكل ممارس. مراجعة مقترح واحد تحتاج
#: بحثاً أو اثنين، والعشرون هامشٌ واسع لجلسة عمل لا لحلقة آلية.
EVIDENCE_LIMIT = RateLimit(max_events=20, window_seconds=60.0)


class RateLimiter:
    """آمن للخيوط. المفتاح يحدده المستدعي (بريد، عنوان IP، معرّف مستخدم)."""

    def __init__(self, limit: RateLimit) -> None:
        self._limit = limit
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """يسجّل محاولة ويرفع `RateLimitExceeded` إن تجاوزت الحد."""
        timestamp = now().timestamp()
        cutoff = timestamp - self._limit.window_seconds

        with self._lock:
            window = self._events.setdefault(key, deque())
            while window and window[0] <= cutoff:
                window.popleft()

            if len(window) >= self._limit.max_events:
                raise RateLimitExceeded(window[0] + self._limit.window_seconds - timestamp)

            window.append(timestamp)

    def reset(self, key: str | None = None) -> None:
        """يُستخدم في الاختبارات وعند تسجيل دخول ناجح."""
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)
