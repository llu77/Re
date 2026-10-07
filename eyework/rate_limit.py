"""
حدود المعدّل في الذاكرة
=======================
دلوٌ ثابت النافذة لكل مفتاح — نسخةٌ من نمط المنصّة لا استيرادٌ منه.

حدٌّ مقصود: المخزن داخل العملية الواحدة، فمع عدّة عمليات يتضاعف الحدّ
الفعلي. ولذلك ما كلفتُه مال — توليد النصّ بالذكاء الاصطناعي — لا يُحدّ هنا
بل في القاعدة (`ew_begin_generation`)، فيصمد مهما تعدّدت العمليات. ما هنا
للدخول والرفع وسائر الطلبات.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from eyework.clock import monotonic

__all__ = ["RateLimit", "RateLimitExceeded", "RateLimiter"]

#: فوق هذا العدد من المفاتيح يُكنس ما انقضى قبل كل تسجيل.
_SWEEP_ABOVE = 10_000


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__("تجاوز حدّ المعدّل")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class RateLimit:
    max_events: int
    window_seconds: float


class RateLimiter:
    """آمنٌ للخيوط. المفتاح يحدّده المستدعي."""

    def __init__(self, limit: RateLimit) -> None:
        self._limit = limit
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """يسجّل محاولة، ويرفع `RateLimitExceeded` إن تجاوزت الحدّ."""
        timestamp = monotonic()
        cutoff = timestamp - self._limit.window_seconds
        with self._lock:
            if len(self._events) > _SWEEP_ABOVE:
                self._sweep(cutoff)
            window = self._events.setdefault(key, deque())
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self._limit.max_events:
                raise RateLimitExceeded(window[0] + self._limit.window_seconds - timestamp)
            window.append(timestamp)

    def _sweep(self, cutoff: float) -> None:
        """يحذف المفاتيح التي انقضت كل أحداثها — عناوين كثيرة لا تملأ الذاكرة بلا حدّ."""
        stale = [key for key, window in self._events.items() if not window or window[-1] <= cutoff]
        for key in stale:
            del self._events[key]

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)
