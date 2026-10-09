"""
«سيمبول» في الواجهة
===================
التحية باسم المستخدم من قاعدة التطبيق، وكلمة المساعد بجانب النصّ المقترح —
وكلاهما في حدود عقد النظر (بلا تمرير) الذي تفرضه `test_gaze.py` على الشاشات.
"""

from __future__ import annotations

from eyework import auth
from eyework.tests.fakes import NOTE
from eyework.tests.ui.conftest import LOGIN, LOGIN_KEY
from eyework.tests.ui.flow import Flow


def _greeting(page) -> str:
    page.wait_for_function("() => document.querySelector('#home-greeting').textContent.length > 0")
    return page.inner_text("#home-greeting")


def test_the_greeting_names_the_user_only_when_a_name_is_set(page_factory, server, owner):
    page = page_factory()
    page.goto(server["base"] + "/#/")
    assert _greeting(page) == "أنا سيمبول، مساعدك الشخصي."

    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = 'عبد الله' WHERE login_hmac = %s",
                       (auth.login_hmac(LOGIN_KEY, LOGIN),))
    page.reload()
    assert _greeting(page) == "أنا سيمبول، مساعدك الشخصي يا عبد الله."


def test_the_assistants_note_is_shown_beside_the_proposed_copy(page_factory, server):
    page = page_factory()
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.screen("home")
    flow.press("#home-new", lambda: flow.screen("photo"), "حملة جديدة")
    from eyework.tests.ui.flow import sample_photo

    page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                 "buffer": sample_photo()}])
    flow.until("!document.querySelector('#photo-generate').disabled")
    flow.press("#photo-generate", lambda: flow.until("!document.querySelector('#proposal-copy').hidden"),
               "اكتب لي العنوان والوصف")
    assert page.inner_text("#proposal-note") == f"سيمبول: {NOTE}"
    assert page.is_visible("#proposal-note")
