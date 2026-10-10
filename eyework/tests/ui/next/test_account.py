"""
حسابي على الواجهة الجديدة
=========================
طريقة الاستخدام تُحفظ في الحساب ثم يتبدّل الحجم كلّه؛ و«المصادر» نسبة المحتوى؛ والخروج
والحذف بخطوتين، وما يقع تحت الضغطة بعدها لا يعتمد شيئاً.
"""

from __future__ import annotations

from eyework import professions
from eyework.tests.ui.next.conftest import LOGIN, member
from eyework.tests.ui.next.flow import Flow


def test_the_size_is_saved_in_the_account_then_applied(next_page, server, owner):
    member(owner, size="COMPACT")
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next + "#/account")
    flow.screen("#account-ui-size-apply")
    flow.audit("account")
    assert page.locator("#account-ui-size-apply").is_disabled()
    flow.press("[role=radiogroup] [role=radio] >> nth=1", lambda: flow.until(
        "!document.querySelector('#account-ui-size-apply').disabled"), "بتتبّع العين")
    assert page.evaluate("() => document.documentElement.dataset.size") == "compact"   # الاختيار لا يطبّق
    flow.press("#account-ui-size-apply", lambda: flow.until(
        "document.documentElement.dataset.size === 'gaze'"), "طبّق")
    flow.audit("account-gaze")
    with owner.cursor() as cursor:
        cursor.execute("SELECT ui_size FROM users")
        assert cursor.fetchone() == ("GAZE",)
    assert [url for method, url in page.requests if method == "PUT"] == [server["base"] + "/api/me/ui-size"]
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_the_sources_name_the_content_licence(next_page, server, owner):
    member(owner)
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next + "#/account/sources")
    flow.screen("text=" + professions.ATTRIBUTION[:20])
    flow.audit("sources")
    assert professions.ATTRIBUTION in page.text_content("main")
    assert not flow.failures(), "\n".join(flow.failures())


def test_signing_out_takes_two_steps_and_lands_on_the_welcome(next_page, server, owner):
    member(owner, size="GAZE")
    page = next_page(login=LOGIN, size="gaze")
    flow = Flow(page)
    page.goto(page.next + "#/account")
    flow.screen("text=تسجيل الخروج")
    flow.press("text=تسجيل الخروج", lambda: flow.screen("#account-confirm-yes"), "تسجيل الخروج")
    flow.audit("logout")
    flow.press("#account-confirm-back", lambda: flow.screen("text=تسجيل الخروج"), "رجوع")
    flow.press("text=تسجيل الخروج", lambda: flow.screen("#account-confirm-yes"), "تسجيل الخروج")
    flow.press("#account-confirm-yes", lambda: flow.screen("#welcome-login"), "نعم، اخرج")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert page.request.get(server["base"] + "/api/me").status == 401


def test_deleting_takes_two_steps_and_removes_the_account(next_page, server, owner):
    member(owner, size="GAZE")
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next + "#/account")
    flow.screen("text=احذف حسابي")
    flow.press("text=احذف حسابي", lambda: flow.screen("#account-confirm-yes"), "احذف حسابي")
    flow.audit("delete")
    flow.press("#account-confirm-yes", lambda: flow.screen("#welcome-login"), "نعم، احذف حسابي")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone() == (0,)
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)


def test_on_gaze_the_size_has_its_own_page_and_switching_back_to_touch_is_two_presses(next_page, server, owner):
    """
    في الحجم الكبير «حسابي» صفحتان (صفحةٌ واحدة لا تتّسع بفجوة 40 بين الأهداف): «طريقة الاستخدام: …» يفتح
    صفحة الخيارين و«طبّق»، و«رجوع» يعود. ما تحت كل ضغطةٍ بعدها لا يعتمد ولا يغيّر قيمة، والرجوع إلى اللمس
    اختيارٌ ثم «طبّق».
    """
    member(owner, size="GAZE")
    page = next_page(login=LOGIN, size="gaze")
    flow = Flow(page)
    page.goto(page.next + "#/account")
    flow.screen("#account-size")
    flow.audit("account-gaze")
    assert page.locator("#account-ui-size-apply").count() == 0
    flow.press("#account-size", lambda: flow.screen("#account-ui-size-apply"), "طريقة الاستخدام")
    flow.audit("account-gaze-size")
    assert page.locator("#account-ui-size-apply").is_disabled()
    flow.press("#account-size-back", lambda: flow.screen("#account-size"), "رجوع")
    flow.press("#account-size", lambda: flow.screen("#account-ui-size-apply"), "طريقة الاستخدام")
    flow.press("[aria-label='طريقة الاستخدام'] button[aria-pressed='false']", lambda: flow.until(
        "!document.querySelector('#account-ui-size-apply').disabled"), "باللمس")
    assert page.evaluate("() => document.documentElement.dataset.size") == "gaze"   # الاختيار لا يطبّق
    flow.press("#account-ui-size-apply", lambda: flow.until(
        "document.documentElement.dataset.size === 'compact'"), "طبّق")
    with owner.cursor() as cursor:
        cursor.execute("SELECT ui_size FROM users")
        assert cursor.fetchone() == ("COMPACT",)
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
