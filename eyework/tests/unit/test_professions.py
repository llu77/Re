"""
محتوى البوابات
==============
ما تعرضه البوابة نصٌّ مترجمٌ عن مصدرٍ رسمي، وكل وعدٍ فيه يُختبر هنا:

  • لكل مهنةٍ بوابة، واسمٌ، وسطرٌ في خطوة الاختيار.
  • كل بندٍ يتّسع لشاشةٍ واحدة بلا تمرير، ولا يحمل حرفاً لاتينياً.
  • `IN_APP` لا يظهر في بوابةٍ بلا أداة، ولا بلا ملاحظةٍ تسمّي ما تؤدّيه الأداة.
  • الأهمية كما في المصدر: رقمٌ من O*NET مرتّباً كما في صفحته، ولا رقم من ISCO-08.
  • المهارة الواحدة بنصٍّ واحد في كل البوابات.
  • سطر المصدر يذكر الجهة، وترخيص O*NET حين يكون منه.
"""

from __future__ import annotations

import re

import pytest

from eyework import professions as P

PORTALS = list(P.PORTALS.values())
LATIN = re.compile(r"[A-Za-z]")


def test_every_profession_has_a_portal_a_name_and_a_tagline():
    assert set(P.PORTALS) == set(P.Profession) == set(P.NAMES) == set(P.TAGLINES)
    for profession, portal in P.PORTALS.items():
        assert portal.profession is profession
        assert portal.tagline and portal.summary


@pytest.mark.parametrize("portal", PORTALS, ids=lambda p: p.profession.value)
def test_every_line_fits_one_screen_and_is_arabic(portal):
    assert portal.tasks and portal.skills
    for task in portal.tasks:
        assert 0 < len(task.ar) <= P.TASK_MAX, task.ar
        assert len(task.note) <= P.NOTE_MAX, task.note
        assert not LATIN.search(task.ar + task.note), task.ar
    for skill in portal.skills:
        assert 0 < len(skill.name) <= P.SKILL_MAX, skill.name
        assert 0 < len(skill.note) <= P.NOTE_MAX, skill.note
        assert not LATIN.search(skill.name + skill.note), skill.name
    assert not LATIN.search(portal.summary + portal.tagline)


@pytest.mark.parametrize("portal", PORTALS, ids=lambda p: p.profession.value)
def test_in_app_only_where_a_tool_does_it_and_says_which_part(portal):
    in_app = [task for task in portal.tasks if task.mode is P.Mode.IN_APP]
    if not portal.tools:
        assert in_app == [], [task.ar for task in in_app]
    for task in in_app:
        assert task.note.startswith("في التطبيق:"), task.ar


def test_only_marketing_has_a_tool_today():
    assert {p: portal.tools for p, portal in P.PORTALS.items() if portal.tools} == {
        P.Profession.MARKETING: ("CAMPAIGN",)}


@pytest.mark.parametrize("portal", PORTALS, ids=lambda p: p.profession.value)
def test_importance_is_the_sources_own(portal):
    from_onet = portal.tasks_source.label.startswith("O*NET")
    for task in portal.tasks:
        assert (task.importance is not None) == from_onet, task.ar
        if from_onet:
            assert 0 <= task.importance <= 100
    if from_onet:
        ranks = [task.importance for task in portal.tasks]
        assert ranks == sorted(ranks, reverse=True)
    ranks = [skill.importance for skill in portal.skills]
    assert ranks == sorted(ranks, reverse=True)
    assert all(0 <= rank <= 100 for rank in ranks)


@pytest.mark.parametrize("portal", PORTALS, ids=lambda p: p.profession.value)
def test_source_texts_are_unique_within_a_portal(portal):
    for items in (portal.tasks, portal.skills):
        texts = [item.source_text for item in items]
        assert len(texts) == len(set(texts))
        assert all(text.strip() == text and text for text in texts)


def test_one_skill_has_one_translation_everywhere():
    seen: dict[str, tuple[str, str]] = {}
    for portal in PORTALS:
        for skill in portal.skills:
            english = skill.source_text.split(" — ", 1)[0]
            assert seen.setdefault(english, (skill.name, skill.note)) == (skill.name, skill.note), english


@pytest.mark.parametrize("portal", PORTALS, ids=lambda p: p.profession.value)
def test_sources_name_the_body_and_the_licence(portal):
    for kind, source in (("tasks", portal.tasks_source), ("skills", portal.skills_source)):
        assert source.url.startswith("https://")
        line = P.source_line(portal, kind)
        assert source.label in line and "ترجمةٌ معدّلة" in line
        if source.label.startswith("O*NET"):
            assert "CC BY 4.0" in line and "وزارة العمل الأمريكية" in line
            assert source.url.endswith(source.label.removeprefix("O*NET OnLine "))
        else:
            assert source.label.startswith("ISCO-08") and "منظمة العمل الدولية" in line


@pytest.mark.parametrize("profession", list(P.Profession), ids=lambda p: p.value)
def test_the_view_puts_what_the_app_does_first_and_sends_no_english(profession):
    view = P.view(profession)
    modes = [task["mode"] for task in view["tasks"]]
    order = [mode.value for mode in (P.Mode.IN_APP, P.Mode.EMPLOYER_SYSTEM, P.Mode.VOICE, P.Mode.ON_SITE)]
    assert modes == sorted(modes, key=order.index)
    assert len(view["tasks"]) == len(P.PORTALS[profession].tasks)
    assert view["name"] == P.NAMES[profession]
    sent = repr(view)
    for item in P.PORTALS[profession].tasks + P.PORTALS[profession].skills:
        assert item.source_text not in sent
