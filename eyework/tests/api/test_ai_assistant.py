"""
«اسأل سيمبول» عبر الواجهة البرمجية
==================================
التطبيق الحقيقي بالبوّابة المصطنعة: سؤالٌ جاهز وسؤالٌ مكتوب بعد إخفائه، والحالات
الثلاث، وأدوات القراءة بجولاتها وحدودها، والمحادثة السابقة، والوجهات، وكل خطأٍ برمزه
ورسالته، والسقوف كما ترفعها القاعدة، والشاشات بمهنتها، وبوّابة الموافقة؛ ثم ما يُثبت
الخصوصية: لا سؤال ولا جواب في أيّ جدول، ولا في السجلّ، ولا اسمٌ في الطلب.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

import pytest
from psycopg import sql

from eyework import auth, config
from eyework.assistant import CAMPAIGN, HOME
from eyework.assistant_prompt import DONT_KNOW_TEXT, OUT_OF_SCOPE_TEXT
from eyework.db import Database
from eyework.model_gateway import AnthropicGateway
from eyework.tests.api.conftest import LOGIN_KEY, ORIGIN, add_user, approve, expect, generate, log_in, set_budget, \
    set_days, upload
from eyework.tests.conftest import app_url_for
from eyework.tests.fakes import ANSWER, FakeGateway, assistant_reply, model_reply, tool_request
from eyework.web.app import create_app

MARKETER = "marketer@example.sa"
KEEPER = "keeper@example.sa"
NAME = "سارة"
CANARY = "CANARY-3c7b"
ANSWER_CANARY = "CANARY-a19f"


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def server(owner, owner_url, writer, gateway):
    settings = config.Settings(app_database_url=app_url_for(owner_url), login_key=LOGIN_KEY,
                               anthropic_api_key=None, public_origin=ORIGIN)
    database = Database(settings.app_database_url)
    try:
        yield create_app(settings, copywriter=writer, gateway=gateway, database=database)
    finally:
        database.close()


def _signed_in(owner, browser, username: str = MARKETER, *, profession: str = "MARKETING", terms: bool = True):
    # `terms=False`: حساب دعوةٍ لم يوافق قطّ (add_user يوافق على النسخة الحالية افتراضاً).
    user_id = add_user(owner, username, profession=profession, terms_version=None)
    if terms:
        with owner.cursor() as cursor:
            cursor.execute("UPDATE users SET display_name = %s, terms_version = %s, terms_accepted_at = now()"
                           " WHERE id = %s", (NAME, auth.TERMS_VERSION, user_id))
    client = browser()
    assert log_in(client, username).status_code == 204
    return client, user_id


@pytest.fixture
def marketer(owner, browser):
    return _signed_in(owner, browser)


def _ask(client, kind: str = "HOME", *, screen_id: str | None = None, question: str | None = None,
         ready: int | None = 0, history: list[dict] | None = None):
    screen = {"kind": kind}
    if screen_id is not None:
        screen["id"] = screen_id
    body = {"screen": screen}
    if question is not None:
        body["question"] = question
    if ready is not None:
        body["ready_question"] = ready
    if history is not None:
        body["history"] = history
    return client.post("/api/ai/assistant", json=body)


def _tokens(owner) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT input_tokens, output_tokens FROM ai_requests ORDER BY started_at")
        return [tuple(row) for row in cursor.fetchall()]


def _requests(owner) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT feature, outcome, subject_kind FROM ai_requests ORDER BY started_at")
        return [tuple(row) for row in cursor.fetchall()]


def _backdate(owner, user_id, rows: int, *, minutes: int) -> None:
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ai_requests (user_id, feature, started_at, finished_at, outcome)"
            " SELECT %s, 'ASSISTANT', now() - make_interval(mins => %s), now() - make_interval(mins => %s), 'OK'"
            "   FROM generate_series(1, %s)", (user_id, minutes, minutes, rows))


def _column_hits(owner, needle: str) -> list[str]:
    """كل عمودٍ نصّي أو JSON في المخطّط يحمل النصّ، بالمالك الذي يرى الصفوف كلها."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT table_name, column_name FROM information_schema.columns"
                       " WHERE table_schema = 'public' AND data_type IN ('text', 'character varying', 'jsonb', 'json', 'ARRAY')")
        columns = cursor.fetchall()
        hits = []
        for table, column in columns:
            cursor.execute(sql.SQL("SELECT count(*) FROM {} WHERE {}::text LIKE {}").format(
                sql.Identifier(table), sql.Identifier(column), sql.Literal(f"%{needle}%")))
            if cursor.fetchone()[0]:
                hits.append(f"{table}.{column}")
    return hits


# ── الأسئلة والأجوبة ───────────────────────────────────────────────────
def test_a_ready_question_is_answered_from_the_screens_data(marketer, owner, gateway):
    client, _ = marketer
    generate(client, upload(client))
    body = expect(_ask(client, "HOME", ready=0))
    assert body == {
        "status": "ANSWER", "text": ANSWER, "question_sent": HOME.ready_questions[0],
        "usage": {"per_day": 60, "used_today": 1}, "tools": [], "open": None,
    }
    assert _requests(owner) == [("ASSISTANT", "OK", None)]

    (call,) = gateway.calls
    assert call.feature == "ASSISTANT" and call.effort == "low" and not call.stream
    assert "حملاتك: 1 نصٌّ مقترح" in call.user and "عنوان النسخة رقم 1 للمنتج" in call.user
    assert "<label>حملة جديدة</label>" in call.user and HOME.ready_questions[0] in call.user
    # من المهنة اسمها وحده، ومعه أدواتها ووجهاتها: لا مهامّ ولا مهارات.
    assert call.system[1]["text"].startswith('<profession name="التسويق"></profession>\n<tools>')
    assert NAME not in call.user and NAME not in json.dumps(call.system, ensure_ascii=False)
    assert "tools" not in AnthropicGateway.params(call)


def test_a_typed_question_is_masked_before_it_leaves_and_echoed_as_sent(marketer, owner, gateway):
    client, _ = marketer
    body = expect(_ask(client, question="هل أتصل بالعميل على 0551234567؟", ready=None))
    assert body["question_sent"] == "هل أتصل بالعميل على [رقم]؟"
    (call,) = gateway.calls
    assert "[رقم]" in call.user and "0551234567" not in call.user


@pytest.mark.parametrize(("status", "text"), [("DONT_KNOW", DONT_KNOW_TEXT), ("OUT_OF_SCOPE", OUT_OF_SCOPE_TEXT)])
def test_the_two_other_statuses_show_their_fixed_text_and_are_recorded(marketer, owner, gateway, status, text):
    client, _ = marketer
    gateway.queue(assistant_reply(status, "نصٌّ من النموذج لا يُعرض"))
    body = expect(_ask(client))
    assert (body["status"], body["text"], body["open"]) == (status, text, None)
    assert _requests(owner) == [("ASSISTANT", status, None)]


def test_the_campaign_screen_sends_the_campaigns_data_without_its_id(marketer, owner, gateway):
    client, _ = marketer
    view = generate(client, upload(client))
    view = set_days(client, set_budget(client, approve(client, view), 500), 7)
    body = expect(_ask(client, "CAMPAIGN", screen_id=view["id"], ready=1))
    assert body["status"] == "ANSWER" and body["question_sent"] == CAMPAIGN.ready_questions[1]
    (call,) = gateway.calls
    assert "الحالة: نصٌّ معتمد" in call.user and "العنوان: عنوان النسخة رقم 1 للمنتج" in call.user
    assert "الميزانية: 500 ريال" in call.user and "المدّة: 7 يوم" in call.user
    assert view["id"] not in call.user and "<label>نعم، اعتمد الحملة</label>" in call.user



# ── الأدوات والمحادثة والوجهات ──────────────────────────────────────────
def test_a_tool_round_reads_the_users_own_campaigns_and_suggests_a_screen(marketer, owner, gateway):
    client, _ = marketer
    generate(client, upload(client))
    gateway.queue(tool_request("CAMPAIGNS"), assistant_reply(used=("TOOL",), open="campaigns"))
    body = expect(_ask(client, question="ما حال آخر حملةٍ لي؟", ready=None))
    assert (body["status"], body["text"]) == ("ANSWER", ANSWER)
    assert body["tools"] == [{"name": "CAMPAIGNS", "label": "حملاتك", "input": ""}]
    assert body["open"] == {"id": "campaigns", "label": "حملاتي"}

    first, second = gateway.calls
    assert "<tool_result" not in first.user and "<tools>" in json.dumps(first.system, ensure_ascii=False)
    assert '<tool_result name="CAMPAIGNS">' in second.user and "«عنوان النسخة رقم 1 للمنتج» — نصٌّ مقترح" in second.user
    assert first.system == second.system and "tools" not in AnthropicGateway.params(second)
    # سؤالٌ واحد صفٌّ واحد في الدفتر، بما استهلكه الاستدعاءان معاً.
    assert _requests(owner) == [("ASSISTANT", "OK", None)] and _tokens(owner) == [(2400, 300)]


def test_a_tool_reads_under_isolation_and_the_calculator_reads_arabic_digits(owner, browser, gateway):
    """أداة الحملات لموظفٍ آخر لا ترى حملات الأوّل؛ والحاسبة تقرأ الأرقام العربية وتحسب الوجهين."""
    first, _ = _signed_in(owner, browser)
    generate(first, upload(first))
    second, _ = _signed_in(owner, browser, "second@example.sa")
    gateway.queue(tool_request("CAMPAIGNS"), assistant_reply(used=("TOOL",)))
    expect(_ask(second, question="ما حال حملاتي؟", ready=None))
    assert "لا حملات بعد." in gateway.calls[-1].user and "عنوان النسخة" not in gateway.calls[-1].user

    gateway.queue(tool_request("VAT", "١١٥ ريال"), assistant_reply(used=("TOOL",)))
    body = expect(_ask(second, question="كم الضريبة في 115 ريالاً؟", ready=None))
    assert body["tools"] == [{"name": "VAT", "label": "حاسبة الضريبة", "input": "١١٥ ريال"}]
    assert "<input>١١٥ ريال</input>" in gateway.calls[-1].user
    assert "115.00 ر.س قبل الضريبة: الضريبة 17.25 ر.س، والإجمالي 132.25 ر.س." in gateway.calls[-1].user
    assert "115.00 ر.س شاملةً الضريبة: قبلها 100.00 ر.س، والضريبة 15.00 ر.س." in gateway.calls[-1].user


def test_a_third_or_repeated_tool_ends_as_dont_know_without_a_fourth_call(marketer, owner, gateway):
    client, _ = marketer
    gateway.queue(tool_request("VAT", "100"), tool_request("VAT", "200"), tool_request("VAT", "300"))
    body = expect(_ask(client, question="كم الضريبة في 100 و200 و300؟", ready=None))
    assert (body["status"], body["text"], body["open"]) == ("DONT_KNOW", DONT_KNOW_TEXT, None)
    assert [tool["input"] for tool in body["tools"]] == ["100", "200"] and len(gateway.calls) == 3

    gateway.queue(tool_request("VAT", "100"), tool_request("VAT", "100"))
    body = expect(_ask(client, question="كم الضريبة في 100؟", ready=None))
    assert body["status"] == "DONT_KNOW" and len(body["tools"]) == 1 and len(gateway.calls) == 5
    assert _requests(owner) == [("ASSISTANT", "DONT_KNOW", None)] * 2


def test_a_tool_or_screen_outside_the_profession_is_an_invalid_answer(marketer, owner, gateway):
    client, _ = marketer
    gateway.queue(tool_request("ITEMS", "ماء"))
    response = _ask(client, question="كم رصيد الماء؟", ready=None)
    assert (response.status_code, response.json()["code"]) == (502, "AI_INVALID") and len(gateway.calls) == 1

    gateway.queue(assistant_reply(open="stock"))
    response = _ask(client, question="أين المخزون؟", ready=None)
    assert (response.status_code, response.json()["code"]) == (502, "AI_INVALID")
    assert _requests(owner) == [("ASSISTANT", "OUTPUT_INVALID", None)] * 2
    schema = gateway.calls[-1].schema["properties"]
    assert schema["tool"]["enum"] == ["NONE", "VAT", "CAMPAIGNS"]
    assert schema["open"]["enum"] == ["NONE", "new", "campaigns"]


def test_the_storekeepers_tools_find_items_and_low_stock(owner, browser, gateway):
    keeper, _ = _signed_in(owner, browser, KEEPER, profession="STOREKEEPER")
    expect(keeper.put("/api/inventory/settings", json={"cost_includes_vat": False}))
    expect(keeper.post("/api/inventory/items", json={"name": "ماء نقي 330 مل", "kind": "STOCK", "unit": "CARTON",
                                                    "price_halalas": 1500, "reorder_level_milli": 5000}), 201)
    gateway.queue(tool_request("ITEMS", "ماء"), tool_request("LOW_STOCK"),
                  assistant_reply(used=("TOOL",), open="stock"))
    body = expect(_ask(keeper, question="هل أطلب ماءً؟", ready=None))
    assert [tool["name"] for tool in body["tools"]] == ["ITEMS", "LOW_STOCK"]
    assert body["open"] == {"id": "stock", "label": "المخزون"}
    last = gateway.calls[-1].user
    assert '<tool_result name="ITEMS">' in last and "ماء نقي 330 مل (رقم" in last and ": الرصيد 0 كرتون" in last
    assert '<tool_result name="LOW_STOCK">' in last and "وحدّ الطلب 5 كرتون" in last


def test_the_support_tools_search_published_articles_and_count_the_desk(owner, browser, gateway):
    agent, _ = _signed_in(owner, browser, "agent@example.sa", profession="SUPPORT")
    for title, publish in (("الطابعة تطبع صفحاتٍ فارغة", True), ("الطابعة لا تتصل بالشبكة", False)):
        a = expect(agent.post("/api/support/kb", json={
            "client_token": str(uuid4()), "title": title, "issue": f"{title} في المكتب.",
            "resolution": "1. أعد تشغيل الطابعة.\n2. اتصل بنا على 0551234567 إن بقيت."}), 201)
        if publish:
            expect(agent.post(f"/api/support/kb/{a['id']}/publish",
                              json={"expected_row_version": a["row_version"], "version": a["latest_version"]}))
    gateway.queue(tool_request("KB", "الطابعة"), tool_request("DESK"), assistant_reply(used=("TOOL",), open="knowledge"))
    body = expect(_ask(agent, question="كيف أحلّ مشكلة الطابعة؟", ready=None))
    assert [tool["label"] for tool in body["tools"]] == ["بحث في قاعدة المعرفة", "أعداد المكتب"]
    assert body["open"] == {"id": "knowledge", "label": "قاعدة المعرفة"}
    last = gateway.calls[-1].user
    assert "«الطابعة تطبع صفحاتٍ فارغة»" in last and "لا تتصل بالشبكة" not in last
    assert "0551234567" not in last and "[رقم]" in last
    assert "بانتظار قرارك: 0، والتذاكر المفتوحة: 0" in last


def test_the_conversation_goes_with_the_question_after_the_same_checks(marketer, gateway):
    client, _ = marketer
    history = [{"question": "هل أتصل بالعميل على 0551234567؟", "answer": DONT_KNOW_TEXT},
               {"question": "وكيف أبدأ حملة؟", "answer": ANSWER}]
    expect(_ask(client, question="وبعد الصورة؟", ready=None, history=history))
    user = gateway.calls[-1].user
    assert user.index("<conversation>") < user.index("<question>وبعد الصورة؟</question>")
    assert user.count("<turn>") == 2 and "[رقم]" in user and "0551234567" not in user

    calls = len(gateway.calls)
    four = _ask(client, question="وبعد الصورة؟", ready=None, history=history * 2)
    assert four.status_code == 422
    bidi = _ask(client, question="وبعد الصورة؟", ready=None, history=[{"question": "سؤالٌ سابق", "answer": "جواب\u202e"}])
    assert bidi.status_code == 422 and bidi.json() == {
        "code": "INVALID", "detail": "في المحادثة السابقة ما لا يُرسل؛ ابدأ محادثةً جديدة.", "field": "history"}
    short = _ask(client, question="وبعد الصورة؟", ready=None, history=[{"question": "سؤ", "answer": ANSWER}])
    assert short.status_code == 422 and short.json()["field"] == "history"
    assert len(gateway.calls) == calls

# ── الأخطاء ────────────────────────────────────────────────────────────
def test_an_invalid_answer_is_502_and_recorded_as_billable(marketer, owner, gateway):
    client, _ = marketer
    gateway.queue(assistant_reply(answer="زر https://x.example الآن"))
    response = _ask(client)
    assert response.status_code == 502 and response.json()["code"] == "AI_INVALID"
    assert _requests(owner) == [("ASSISTANT", "OUTPUT_INVALID", None)]


@pytest.mark.parametrize(("reply", "status", "code", "retry_after", "outcome"), [
    pytest.param(model_reply("REFUSED", refusal_category="cyber"), 422, "AI_REFUSED", None, "REFUSED", id="refused"),
    pytest.param(model_reply("UPSTREAM_BUSY", retry_after=45), 503, "AI_UNAVAILABLE", "45", "UPSTREAM_BUSY", id="busy"),
    pytest.param(model_reply("UPSTREAM_UNREACHABLE", retry_after=30), 503, "AI_UNAVAILABLE", "30",
                 "UPSTREAM_UNREACHABLE", id="unreachable"),
    pytest.param(model_reply("UPSTREAM_TIMEOUT"), 503, "AI_UNAVAILABLE", "30", "UPSTREAM_TIMEOUT", id="timeout"),
    pytest.param(model_reply("UPSTREAM_ERROR", status=500), 503, "AI_UNAVAILABLE", "30", "UPSTREAM_ERROR", id="error"),
])
def test_each_upstream_outcome_has_its_error_and_closes_the_request(marketer, owner, gateway, reply, status, code,
                                                                     retry_after, outcome):
    client, _ = marketer
    gateway.queue(reply)
    response = _ask(client)
    assert (response.status_code, response.json()["code"]) == (status, code)
    assert response.headers.get("Retry-After") == retry_after
    assert _requests(owner) == [("ASSISTANT", outcome, None)]


def test_an_open_breaker_or_no_slot_refuses_before_any_row(marketer, owner, gateway, server):
    client, _ = marketer
    for _ in range(3):
        server.state.ai_guard.record(model_reply("UPSTREAM_TIMEOUT"))
    down = _ask(client)
    assert (down.status_code, down.json()["code"], down.headers["Retry-After"]) == (503, "AI_UNAVAILABLE", "30")
    server.state.ai_guard.breaker.reset()
    held = 0
    while server.state.ai_guard.acquire() is None:
        held += 1
    try:
        busy = _ask(client)
        assert (busy.status_code, busy.json()["code"]) == (503, "AI_BUSY")
    finally:
        for _ in range(held):
            server.state.ai_guard.release()
    assert _requests(owner) == [] and gateway.calls == []


def test_the_database_caps_reach_the_user_with_their_codes(marketer, owner, gateway):
    client, user_id = marketer
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO ai_requests (user_id, feature) VALUES (%s, 'ASSISTANT')", (user_id,))
    in_flight = _ask(client)
    assert (in_flight.status_code, in_flight.json()["code"]) == (409, "AI_BUSY")

    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM ai_requests")
    _backdate(owner, user_id, 10, minutes=5)
    rate = _ask(client)
    assert (rate.status_code, rate.json()["code"], rate.headers["Retry-After"]) == (429, "AI_RATE", "600")

    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM ai_requests")
    _backdate(owner, user_id, 60, minutes=60)
    daily = _ask(client)
    assert (daily.status_code, daily.json()["code"], daily.headers["Retry-After"]) == (429, "AI_DAILY", "3600")

    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM ai_requests")
    other = add_user(owner, KEEPER, profession="STOREKEEPER")
    _backdate(owner, other, 1000, minutes=60)
    app = _ask(client)
    assert (app.status_code, app.json()["code"], app.headers["Retry-After"]) == (503, "AI_APP_BUSY", "3600")
    assert gateway.calls == []


def test_screens_follow_the_profession_and_inputs_are_checked_before_any_call(owner, browser, gateway):
    client, _ = _signed_in(owner, browser)
    assert _ask(client, "TICKET").json()["code"] == "SCREEN" and _ask(client, "TICKET").status_code == 404
    missing = _ask(client, "CAMPAIGN")
    assert missing.status_code == 422 and missing.json()["field"] == "screen"
    assert _ask(client, "CAMPAIGN", screen_id=str(uuid4())).status_code == 404
    short = _ask(client, question="سؤ", ready=None)
    assert short.status_code == 422 and short.json() == {
        "code": "QUESTION", "detail": "اكتب سؤالاً من 3 إلى 300 حرف.", "field": "question"}
    assert _ask(client, ready=5).status_code == 422
    assert _ask(client, question="سؤالٌ مكتوب", ready=0).status_code == 422
    assert _ask(client, ready=None).status_code == 422

    keeper, _ = _signed_in(owner, browser, KEEPER, profession="STOREKEEPER")
    foreign = _ask(keeper, "CAMPAIGN", screen_id=str(uuid4()))
    assert (foreign.status_code, foreign.json()["code"]) == (404, "SCREEN")
    # لأمين المخزون في الرئيسية بيانات مخزنه وأزرار بوابته السبعة (الحزمة الثالثة).
    assert expect(_ask(keeper, "HOME"))["status"] == "ANSWER"
    assert "الأصناف النشطة: 0" in gateway.calls[-1].user
    assert gateway.calls[-1].user.count("<label>") == 8


def test_the_consent_gate_refuses_an_account_on_an_older_notice(owner, browser, gateway):
    client, _ = _signed_in(owner, browser, terms=False)
    response = _ask(client)
    assert (response.status_code, response.json()["code"]) == (403, "TERMS")
    assert gateway.calls == []


# ── الخصوصية ───────────────────────────────────────────────────────────
def test_neither_the_question_nor_the_answer_is_stored_or_logged(marketer, owner, gateway, caplog, capsys):
    client, _ = marketer
    caplog.set_level(logging.DEBUG)
    gateway.queue(assistant_reply(answer=f"ابدأ من حملة جديدة ثم راجع حملاتي قبل {ANSWER_CANARY}"))
    body = expect(_ask(client, question=f"ما الذي أفعله مع {CANARY}؟", ready=None))
    assert CANARY in body["question_sent"] and ANSWER_CANARY in body["text"]
    assert _column_hits(owner, CANARY) == [] and _column_hits(owner, ANSWER_CANARY) == []
    captured = capsys.readouterr().out
    assert CANARY not in caplog.text and CANARY not in captured
    assert ANSWER_CANARY not in caplog.text and ANSWER_CANARY not in captured
    assert _requests(owner) == [("ASSISTANT", "OK", None)]
