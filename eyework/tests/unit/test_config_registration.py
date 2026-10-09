"""
وضع التسجيل وبريد المشغّل
=========================
`EYEWORK_REGISTRATION` غير مضبوطٍ يعني `open`، والوضع المفتوح لا يُقلع بلا
`EYEWORK_SUPPORT_CONTACT`: نشرٌ قديم يُحدَّث لا ينفتح تسجيله بصمتٍ ولا بلا طريقٍ
إلى المشغّل. الوضعان الآخران يعملان بلا بريد؛ والبريد إن ضُبط يُفحص ويُوحَّد كما
يُوحَّد اسم الدخول.
"""

from __future__ import annotations

import base64

import pytest

from eyework import config

CONTACT = "help@example.sa"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("EYEWORK_APP_DATABASE_URL", "postgresql://x@localhost/eyework_test")
    monkeypatch.setenv("EYEWORK_LOGIN_KEY", base64.b64encode(b"k" * 32).decode())
    monkeypatch.setenv("EYEWORK_PUBLIC_ORIGIN", "https://work.example.sa")
    for name in (*config.SDK_ENVIRONMENT, "EYEWORK_REGISTRATION", "EYEWORK_SUPPORT_CONTACT"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_unset_means_open_and_requires_a_contact(env):
    with pytest.raises(config.ConfigError, match="EYEWORK_SUPPORT_CONTACT"):
        config.load()
    env.setenv("EYEWORK_SUPPORT_CONTACT", CONTACT)
    settings = config.load()
    assert (settings.registration, settings.support_contact) == ("open", CONTACT)


@pytest.mark.parametrize("value", ["", "  ", "open", "OPEN", " Open "])
def test_open_is_read_whatever_its_case_and_spacing(env, value):
    env.setenv("EYEWORK_REGISTRATION", value)
    with pytest.raises(config.ConfigError, match="EYEWORK_SUPPORT_CONTACT"):
        config.load()
    env.setenv("EYEWORK_SUPPORT_CONTACT", CONTACT)
    assert config.load().registration == "open"


@pytest.mark.parametrize("mode", ["code", "closed"])
def test_code_and_closed_work_without_a_contact(env, mode):
    env.setenv("EYEWORK_REGISTRATION", mode)
    settings = config.load()
    assert (settings.registration, settings.support_contact) == (mode, None)
    # الحقل القديم ذهب: من يقرأ الوضع يقرأ `registration`.
    assert not hasattr(settings, "registration_open")


@pytest.mark.parametrize("mode", ["code", "closed"])
def test_a_contact_is_kept_in_the_other_modes_too(env, mode):
    env.setenv("EYEWORK_REGISTRATION", mode)
    env.setenv("EYEWORK_SUPPORT_CONTACT", CONTACT)
    assert config.load().support_contact == CONTACT


@pytest.mark.parametrize("value", ["invite", "true", "1", "opened", "code,closed"])
def test_an_unknown_mode_fails(env, value):
    env.setenv("EYEWORK_REGISTRATION", value)
    env.setenv("EYEWORK_SUPPORT_CONTACT", CONTACT)
    with pytest.raises(config.ConfigError, match="EYEWORK_REGISTRATION"):
        config.load()


@pytest.mark.parametrize("value", [
    "help", "help@", "@example.sa", "help@example", "سارة@example.sa", "help@exam ple.sa",
    "a" * 250 + "@example.sa", "mailto:help@example.sa",
])
@pytest.mark.parametrize("mode", config.REGISTRATION_MODES)
def test_an_invalid_contact_fails_in_every_mode(env, mode, value):
    env.setenv("EYEWORK_REGISTRATION", mode)
    env.setenv("EYEWORK_SUPPORT_CONTACT", value)
    with pytest.raises(config.ConfigError, match="EYEWORK_SUPPORT_CONTACT"):
        config.load()


@pytest.mark.parametrize("raw", [" Help@Example.SA ", "Ｈｅｌｐ@Example.SA", "help@example.sa\n"])
def test_the_contact_is_normalised_like_a_login(env, raw):
    """ما يُعرض للمستخدم هو ما سيكتب إليه: حروفٌ صغيرة بلا مسافاتٍ ولا أشكالٍ كاملة العرض."""
    env.setenv("EYEWORK_SUPPORT_CONTACT", raw)
    assert config.load().support_contact == CONTACT


def test_the_modes_are_the_three_the_server_knows():
    assert config.REGISTRATION_MODES == ("open", "code", "closed")
