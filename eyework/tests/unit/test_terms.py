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
import html
import re
from pathlib import Path

from eyework import auth

INDEX = Path(__file__).resolve().parents[2] / "static" / "index.html"

#: بصمة نصّ الإشعار لكل نسخة. نسخةٌ جديدة تُضاف هنا ولا تُستبدل بها القديمة.
DIGESTS = {
    "2026-10-08": "836260968b16309dec9d2cfa4b4a3db01dbb39e348d4fbc1c3481ead30a4b43d",
}


def _notice_lines() -> list[str]:
    page = INDEX.read_text(encoding="utf-8")
    section = re.search(r'<section class="screen" data-screen="signup-notice".*?</section>', page, re.S)
    assert section, "شاشة الإشعار غير موجودة"
    return [html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
            for line in re.findall(r'<p class="line">(.*?)</p>', section.group(0), re.S)]


def test_the_notice_text_matches_the_consent_version_stored_with_accounts():
    lines = _notice_lines()
    assert lines and all(lines)
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    assert auth.TERMS_VERSION in DIGESTS, "نسخةٌ بلا بصمة: أضف بصمة النصّ الجديد"
    assert DIGESTS[auth.TERMS_VERSION] == digest, (
        "تغيّر نصّ الإشعار: ارفع auth.TERMS_VERSION وأضف بصمته إلى DIGESTS", digest)
