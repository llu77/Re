"""
حوض المراجعة والانتظار
======================
بلا قاعدةٍ ولا شبكة: البوّابة المصطنعة تُحبس فيُختبر PENDING بعد المهلة، ثم
تُطلق فتكمل المهمّة وتسجّل؛ والقاطع يُسجَّل من استدعاءات الحوض نفسها.
"""

from __future__ import annotations

import threading

from eyework.model_gateway import Guard
from eyework.reviewer import ReviewRunner
from eyework.reviewer_prompt import Catalogue, Check, call
from eyework.tests.fakes import FakeGateway, model_reply, review_reply

CATALOGUE = Catalogue("STOCK_REVIEW", (Check("PRICE_IMPLAUSIBLE", frozenset({"PURCHASE"}), frozenset({"unit_cost"}),
                                             True, "سعر", lambda payload, line: ()),), "رقم السطر")
REQUEST = call(CATALOGUE, "PURCHASE", {"lines": [{"line": 1}]})


def _runner(gateway: FakeGateway, **options) -> ReviewRunner:
    runner = ReviewRunner(gateway, Guard(slots=2), wait_seconds=options.pop("wait_seconds", 5.0), **options)
    runner.start()
    return runner


def test_a_job_that_finishes_inside_the_wait_is_done():
    gateway = FakeGateway(review_reply())
    runner = _runner(gateway)
    try:
        future = runner.submit(lambda: runner.call(REQUEST).outcome)
        assert runner.wait(future) == "OK"
        assert gateway.calls == [REQUEST]
    finally:
        runner.close()


def test_a_held_job_is_pending_after_the_wait_and_still_records_when_released():
    gateway = FakeGateway(review_reply())
    gateway.hold()
    runner = _runner(gateway, wait_seconds=0.05)
    recorded: list[str] = []
    done = threading.Event()

    def job() -> str:
        outcome = runner.call(REQUEST).outcome
        recorded.append(outcome)
        done.set()
        return outcome

    try:
        future = runner.submit(job)
        assert runner.wait(future) is None and recorded == []
        gateway.release()
        assert done.wait(5.0) and recorded == ["OK"]
        assert future.result(timeout=5.0) == "OK"
    finally:
        runner.close()


def test_the_runner_records_every_reply_in_the_breaker():
    gateway = FakeGateway(*(model_reply("UPSTREAM_TIMEOUT") for _ in range(3)))
    runner = _runner(gateway)
    try:
        for _ in range(3):
            runner.call(REQUEST)
        assert runner.guard.breaker.is_open and runner.guard.acquire() == "DOWN"
    finally:
        runner.close()


def test_submitting_before_start_or_after_close_is_refused():
    runner = ReviewRunner(FakeGateway(), Guard())
    try:
        runner.submit(lambda: None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("حوضٌ لم يبدأ قبل مهمّة")
    runner.start()
    runner.close()
    try:
        runner.submit(lambda: None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("حوضٌ أُغلق يقبل مهمّة")
