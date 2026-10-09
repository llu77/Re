"""
حدود المعدّل: الفحص بلا تسجيل، والتسجيل بلا فحص
=================================================
`blocked()` يقول كم ننتظر ولا يعدّ شيئاً، و`record()` يعدّ ما وقع بلا فحص: جواب
«البريد مأخوذ» بلا رابط يُفحص قبل القاعدة ويُحسب بعدها، فلا يُحسب ما لم يقع ولا
يُرفض ما لم يُعدّ. والساعة هنا مزيّفة: الوحدة تقرأ `clock.monotonic` وحده.
"""

from __future__ import annotations

import pytest

from eyework import rate_limit
from eyework.rate_limit import RateLimit, RateLimiter, RateLimitExceeded


@pytest.fixture
def clock(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(rate_limit, "monotonic", lambda: now)

    def advance(seconds: float) -> None:
        nonlocal now
        now += seconds

    return advance


def test_blocked_records_nothing_and_returns_the_wait(clock):
    limiter = RateLimiter(RateLimit(2, 60.0))
    for _ in range(10):
        assert limiter.blocked("k") is None
    limiter.check("k")
    limiter.check("k")
    with pytest.raises(RateLimitExceeded):
        limiter.check("k")
    clock(10)
    assert limiter.blocked("k") == pytest.approx(50.0)
    for _ in range(10):
        limiter.blocked("k")
    clock(50)
    # انقضت النافذة؛ ولو عدّ `blocked` شيئاً لبقي المفتاح ممتلئاً.
    assert limiter.blocked("k") is None
    limiter.check("k")


def test_record_counts_without_checking(clock):
    limiter = RateLimiter(RateLimit(2, 60.0))
    for _ in range(3):
        limiter.record("k")
    assert limiter.blocked("k") == pytest.approx(60.0)
    with pytest.raises(RateLimitExceeded) as caught:
        limiter.check("k")
    assert caught.value.retry_after_seconds == pytest.approx(60.0)
    assert limiter.blocked("other") is None
    clock(60)
    assert limiter.blocked("k") is None


def test_check_and_record_share_one_window(clock):
    limiter = RateLimiter(RateLimit(3, 60.0))
    limiter.check("k")
    limiter.record("k")
    clock(30)
    limiter.check("k")
    with pytest.raises(RateLimitExceeded) as caught:
        limiter.check("k")
    # ينتظر أقدم الأحداث الثلاثة لا أحدثها.
    assert caught.value.retry_after_seconds == pytest.approx(30.0)
    assert limiter.blocked("k") == pytest.approx(30.0)
    clock(30)
    assert limiter.blocked("k") is None


def test_reset_frees_one_key_or_all(clock):
    limiter = RateLimiter(RateLimit(1, 60.0))
    limiter.record("a")
    limiter.record("b")
    limiter.reset("a")
    assert limiter.blocked("a") is None
    assert limiter.blocked("b") == pytest.approx(60.0)
    limiter.reset()
    assert limiter.blocked("b") is None


def test_record_sweeps_keys_whose_window_passed(clock):
    """عناوين كثيرة لا تملأ الذاكرة بلا حدّ: ما انقضى يُكنس حين يكثر المفاتيح."""
    limiter = RateLimiter(RateLimit(3, 60.0))
    for n in range(rate_limit._SWEEP_ABOVE + 1):
        limiter.record(f"old-{n}")
    clock(61)
    limiter.record("fresh")
    assert set(limiter._events) == {"fresh"}
