"""
نسخة الموافقة ونصّها
====================
كل حسابٍ مسجَّل يحفظ `terms.TERMS_VERSION`: نسخة الإشعار الذي وافق عليه صاحبه.
فتغيير النصّ دون رفع النسخة يحفظ لحساباتٍ جديدة موافقةً على نصٍّ لم يقرؤوه بتلك
النسخة. هنا لكل نسخةٍ بصمة نصّها: تغيير النصّ يُفشل الاختبار حتى تُرفع النسخة
وتُضاف بصمتها، ولا تُستبدل بصمةٌ قديمة.

حتى حزمة التبديل يعرض العميل الثابت إشعار `index.html` (شاشة «قبل أن تبدأ»)،
وهو نصّ النسخة الحالية، فتُحفظ بصمته من الصفحة كما كانت. و`terms.py` يحمل نصّ
النسخة القادمة — شاشتان وسطرٌ لكل بوابة — الذي يخدمه `/api/choices`؛ بصمته
`PENDING_DIGEST` هنا، وحزمة التبديل تضع تاريخ الإصدار في `TERMS_VERSION` وتنقلها
إلى `DIGESTS` تحته.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from eyework import auth, terms
from eyework.professions import Profession

INDEX = Path(__file__).resolve().parents[2] / "static" / "index.html"

#: بصمة نصّ الإشعار لكل نسخة. نسخةٌ جديدة تُضاف هنا ولا تُستبدل بها القديمة.
DIGESTS = {
    "2026-10-08": "6b063626efc919d01a00838aa9ea4ad4d738ec6714e39c7a53155137ddc544af",
    "2026-10-09": "baba6ba6022f7aa9ce3c4b637b967bd6349bb0167af64f7b48d6dc9758d6993b",
}
#: بصمة `terms.normalized_text()`، نصّ النسخة القادمة. حزمة التبديل تنقلها إلى DIGESTS
#: تحت تاريخ الإصدار حين يصير `TERMS_VERSION` ذلك التاريخ.
PENDING_DIGEST = "b2469df38e49e020296508685262eff6247c2f4d140d11e9dd11d9cf2c229e35"

#: أول كل سطرٍ في «ما يُرسَل»: اسم البوابة كما يعرفه المستخدم، أو «كل البوابات».
LINE_STARTS = {
    Profession.MARKETING: "التسويق:",
    Profession.STOREKEEPER: "المخزون:",
    Profession.SUPPORT: "الدعم الفني:",
    None: "كل البوابات:",
}
LINE_MAX = 60


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Text(HTMLParser):
    """نصّ شاشة الإشعار كلّه كما يُقرأ، بلا التنبيه: أيّ وسمٍ وأيّ تقسيمٍ للأسطر في الملف سواء."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if self._skip or "alert" in classes:
            self._skip += 1

    def handle_endtag(self, tag):
        if self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _static_notice_text() -> str:
    page = INDEX.read_text(encoding="utf-8")
    section = re.search(r'<section class="screen" data-screen="signup-notice".*?</section>', page, re.S)
    assert section, "شاشة الإشعار غير موجودة"
    parser = _Text()
    parser.feed(section.group(0))
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


# ── النسخة والبصمات ─────────────────────────────────────────────────────
def test_the_notice_text_matches_the_consent_version_stored_with_accounts():
    """العميل الثابت المُقدَّم يعرض نصّ النسخة الحالية حرفاً بحرف."""
    text = _static_notice_text()
    assert "يُحفظ في هذا التطبيق" in text
    assert terms.TERMS_VERSION in DIGESTS, "نسخةٌ بلا بصمة: أضف بصمة النصّ الجديد"
    assert DIGESTS[terms.TERMS_VERSION] == _digest(text), (
        "تغيّر نصّ الإشعار: ارفع terms.TERMS_VERSION وأضف بصمته إلى DIGESTS", _digest(text))


def test_the_pending_text_has_its_digest_pinned():
    digest = _digest(terms.normalized_text())
    assert digest == PENDING_DIGEST, ("تغيّر نصّ terms.py: حدّث PENDING_DIGEST (أو DIGESTS بعد الإصدار)", digest)
    # نصٌّ جديد لم يُصدَر بعد: ليس نصّ نسخةٍ قائمة.
    assert digest not in DIGESTS.values()


def test_the_current_version_is_the_newest_with_a_digest_and_auth_re_exports_it():
    assert auth.TERMS_VERSION == terms.TERMS_VERSION
    assert terms.TERMS_VERSION == max(DIGESTS)
    assert all(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", version) for version in DIGESTS)
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in DIGESTS.values())


# ── «ما يُحفظ هنا» ──────────────────────────────────────────────────────
def test_kept_names_the_operator_the_usage_mode_and_the_open_registration_trade_off():
    assert any("مَن يدير التطبيق" in line for line in terms.KEPT)
    assert "وطريقة الاستخدام" in terms.KEPT[0]
    assert terms.KEPT[-1] == "ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا."
    assert any("لا يُحفظ" in line and "البريد" in line for line in terms.KEPT)


# ── «ما يُرسَل إلى Anthropic» ───────────────────────────────────────────
def test_sent_has_one_line_per_workspace_and_one_for_all_within_sixty_characters():
    scopes = [scope for scope, _ in terms.SENT]
    assert len(scopes) == len(set(scopes)), "مجالٌ مكرّر"
    assert set(scopes) == {*Profession, None}
    for scope, text in terms.SENT:
        assert text.startswith(LINE_STARTS[scope] + " "), text
        assert len(text) <= LINE_MAX, (len(text), text)
        assert text.endswith(".")


def test_the_intro_promises_what_is_never_sent_and_the_outro_names_the_retention():
    assert "Anthropic" in terms.SENT_INTRO
    assert "بلا اسمك ولا ميلادك ولا طريقة استخدامك" in terms.SENT_INTRO
    assert terms.SENT_INTRO.endswith(":")
    assert "30 يوماً" in terms.SENT_OUTRO


@pytest.mark.parametrize("part", [*terms.KEPT, terms.SENT_INTRO, *(text for _, text in terms.SENT), terms.SENT_OUTRO])
def test_no_line_is_empty_or_still_the_draft_placeholder(part):
    assert part.strip() == part and part
    assert "…" not in part and "..." not in part
    assert "\n" not in part


# ── ما يُخدم ────────────────────────────────────────────────────────────
def test_the_notice_is_served_as_data_in_display_order():
    served = terms.notice()
    assert served["version"] == terms.TERMS_VERSION
    assert served["kept"] == list(terms.KEPT)
    assert served["sent"]["intro"] == terms.SENT_INTRO
    assert served["sent"]["outro"] == terms.SENT_OUTRO
    assert [item["scope"] for item in served["sent"]["items"]] == [
        scope.value if scope else "ALL" for scope, _ in terms.SENT]
    assert [item["text"] for item in served["sent"]["items"]] == [text for _, text in terms.SENT]
    # البصمة على النصّ بترتيب عرضه نفسه، سطراً سطراً.
    assert terms.normalized_text().split("\n") == [
        *served["kept"], served["sent"]["intro"], *(item["text"] for item in served["sent"]["items"]),
        served["sent"]["outro"]]


def test_the_normalized_text_ignores_how_whitespace_is_written(monkeypatch):
    monkeypatch.setattr(terms, "KEPT", ("  سطرٌ   بمسافاتٍ \n كثيرة ",))
    assert terms.normalized_text().split("\n")[0] == "سطرٌ بمسافاتٍ كثيرة"


# ── قاعدة البوّابة ──────────────────────────────────────────────────────
@pytest.mark.parametrize(("accepted", "current"), [
    (None, False),
    ("2026-10-08", False),
    (terms.TERMS_VERSION, True),
    ("2027-01-01", True),
])
def test_is_current_accepts_the_current_or_a_newer_version_only(accepted, current):
    assert terms.is_current(accepted) is current
