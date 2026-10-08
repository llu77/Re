"""
نسخة الموافقة ونصّها
====================
كل حسابٍ مسجَّل يحفظ `auth.TERMS_VERSION`: نسخة الإشعار الذي وافق عليه صاحبه
(`index.html`، شاشة «قبل أن تبدأ»). فتغيير النصّ دون رفع النسخة يحفظ لحساباتٍ
جديدة موافقةً على نصٍّ لم يقرؤوه بتلك النسخة. هنا لكل نسخةٍ بصمة نصّها: تغيير
النصّ يُفشل الاختبار حتى تُرفع النسخة وتُضاف بصمتها.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

from eyework import auth

INDEX = Path(__file__).resolve().parents[2] / "static" / "index.html"

#: بصمة نصّ الإشعار لكل نسخة. نسخةٌ جديدة تُضاف هنا ولا تُستبدل بها القديمة.
DIGESTS = {
    "2026-10-08": "6b063626efc919d01a00838aa9ea4ad4d738ec6714e39c7a53155137ddc544af",
}


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


def _notice_text() -> str:
    page = INDEX.read_text(encoding="utf-8")
    section = re.search(r'<section class="screen" data-screen="signup-notice".*?</section>', page, re.S)
    assert section, "شاشة الإشعار غير موجودة"
    parser = _Text()
    parser.feed(section.group(0))
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def test_the_notice_text_matches_the_consent_version_stored_with_accounts():
    text = _notice_text()
    assert "يُحفظ في هذا التطبيق" in text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert auth.TERMS_VERSION in DIGESTS, "نسخةٌ بلا بصمة: أضف بصمة النصّ الجديد"
    assert DIGESTS[auth.TERMS_VERSION] == digest, (
        "تغيّر نصّ الإشعار: ارفع auth.TERMS_VERSION وأضف بصمته إلى DIGESTS", digest)
