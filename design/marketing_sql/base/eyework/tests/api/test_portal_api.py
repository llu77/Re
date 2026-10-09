"""
البوابة عبر الواجهة البرمجية
============================
كل حسابٍ يرى بوابة مهنته وحدها، والمهنة من القاعدة لا من الطلب.
"""

from __future__ import annotations

import pytest

from eyework import professions
from eyework.tests.api.conftest import signed_in


def test_the_portal_needs_a_session(browser):
    response = browser().get("/api/portal")
    assert response.status_code == 401


@pytest.mark.parametrize("profession", list(professions.Profession), ids=lambda p: p.value)
def test_each_account_gets_its_own_professions_portal(owner, browser, profession):
    client = signed_in(owner, browser, f"{profession.value.lower()}@example.sa", profession=profession.value)
    response = client.get("/api/portal")
    assert response.status_code == 200
    assert response.json() == professions.view(profession)
    assert client.get("/api/me").json()["profession"] == profession.value


def test_the_request_cannot_choose_another_portal(owner, browser):
    client = signed_in(owner, browser, "keeper@example.sa", profession="STOREKEEPER")
    for query in ({"profession": "MARKETING"}, {"code": "SUPPORT"}):
        assert client.get("/api/portal", params=query).json()["profession"] == "STOREKEEPER"


def test_a_profession_change_shows_on_the_next_request(owner, browser):
    client = signed_in(owner, browser, "mover@example.sa", profession="MARKETING")
    assert client.get("/api/portal").json()["tools"] == ["CAMPAIGN"]
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET profession = 'SUPPORT'")
    portal = client.get("/api/portal").json()
    assert (portal["profession"], portal["tools"]) == ("SUPPORT", [])
    assert client.get("/api/campaigns").status_code == 403
