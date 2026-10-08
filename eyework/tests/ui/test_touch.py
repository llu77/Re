"""
اللمس كالنظر
============
كل ما يُضغط بالنظر يُضغط بالإصبع: الواجهة تستمع إلى click وحده (لا pointer ولا
touch)، وiOS يرسله من الإقامة بالنظر ومن النقر باللمس. هنا المسارات بالنقر
(`tap`) في سياقٍ لمسي، لا بالفأرة.
"""

from __future__ import annotations

from eyework.tests.ui.conftest import LOGIN, PASSWORD, VIEWPORTS
from eyework.tests.ui.flow import Flow
from eyework.tests.ui.test_portals import _issue_code, _set_profession


def test_signing_in_and_moving_through_a_portal_by_touch(page_factory, server, owner):
    _set_profession(owner, "STOREKEEPER")
    page = page_factory(*VIEWPORTS[0], session=False)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    page.tap("#login-username")
    page.keyboard.type(LOGIN)
    page.tap("#login-password")
    page.keyboard.type(PASSWORD)
    page.tap("#login-form [type='submit']")
    flow.until("document.querySelector('#home-portal').textContent === 'بوابة أمين المخزون'")

    page.tap("#home-tasks")
    flow.until("document.querySelector('#portal-item-position').textContent.startsWith('المهمة 1 ')")
    page.tap("#portal-item-next")
    flow.until("document.querySelector('#portal-item-position').textContent.startsWith('المهمة 2 ')")
    page.tap(".screen[data-screen='portal-item'] [data-back]")
    flow.screen("home")

    page.tap("#home-account")
    flow.screen("account")
    page.tap("#account-sources")
    flow.until("document.querySelector('#account-attribution').textContent !== ''")
    page.tap(".screen[data-screen='account-sources'] [data-back]")
    flow.screen("account")
    page.tap("#account-delete")
    flow.screen("account-delete")
    page.tap("#account-delete-back")
    flow.screen("account")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 1
    assert not page.errors, page.errors


def test_signing_up_by_touch(page_factory, server, owner):
    page = page_factory(*VIEWPORTS[0], session=False)
    flow = Flow(page, server["base"])
    page.goto(f"{server['base']}/#signup={_issue_code(owner)}")
    flow.screen("signup-notice")
    page.tap("#signup-agree")
    flow.screen("signup-name")
    page.tap("#signup-name-input")
    page.keyboard.type("سارة")
    page.tap("#signup-name-next")
    flow.screen("signup-year")
    page.tap("#signup-year-presets .chip >> nth=3")
    page.tap("#signup-year-next")
    flow.screen("signup-month")
    page.tap("#signup-month-presets .chip >> nth=1")
    page.tap("#signup-month-next")
    flow.screen("signup-day")
    page.tap("#signup-day-presets .chip >> nth=2")
    page.tap("#signup-day-next")
    flow.screen("signup-profession")
    page.tap("#signup-professions [data-key='SUPPORT']")
    page.tap("#signup-profession-next")
    flow.screen("signup-email")
    page.tap("#signup-email-input")
    page.keyboard.type("touch@example.sa")
    page.tap("#signup-email-next")
    flow.screen("signup-review")
    page.tap("#signup-review-next")
    flow.screen("signup-password")
    page.tap("#signup-password-input")
    page.keyboard.type("Strong-Password-2026-t")
    page.tap("#signup-create")
    flow.until("document.querySelector('#home-portal') && document.querySelector('#home-portal').textContent"
               " === 'بوابة الدعم الفني'")
    with owner.cursor() as cursor:
        cursor.execute("SELECT profession, self_registered FROM users WHERE profession = 'SUPPORT'")
        assert cursor.fetchall() == [("SUPPORT", True)]
    assert not page.errors, page.errors
