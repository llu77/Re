"""
التأسيس على مقالات قاعدة المعرفة
================================
مسودة الدعم (الحزمة 4) لا تُعرض إلا مؤسَّسةً على اقتباساتٍ حرفية من مقالاتٍ
منشورة. هنا ما يشترك فيه ذلك مع سائر الأدوات ولا يحتاج قاعدةً ولا شبكة:
تطبيع النصّ للمقارنة، وحزم المقالات في رسالة المستخدم، والتحقّق من الاقتباس.

**اقتباسٌ محقَّق لا واجهة الاستشهادات.** واجهة الاستشهادات لا تجتمع مع
المخرجات المنظّمة (400)، والمسودة تحتاج حقولاً منظّمة. فيُثبت الاقتباس بالمطابقة
الحرفية بعد التطبيع — هنا، ثم في القاعدة مرةً ثانية. ومسودةٌ تدّعي مصدراً لا
تملكه لا تُعرض: إسقاط الاقتباس وحده يُبقي نصّاً زال سنده.

**مقالاتٌ كاملة في رسالة المستخدم.** بيانات كل مستخدمٍ لا تدخل البادئة
المخزّنة؛ والمقالة لا تُقصّ في منتصفها: ما لا يتّسع يُترك كلّه.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence

from eyework.ai_limits import KB_CHARS, QUOTE_LENGTH
from eyework.prompt_kit import data, tag

__all__ = ["MAX_ARTICLES", "Article", "kb_norm", "package", "verify"]

#: أفضل خمس مطابقات، بمراجع A1 إلى A5. المعرّفات تبقى في الخادم.
MAX_ARTICLES = 5

#: الحركات والشدّة والسكون وعلامات القرآن (U+064B–U+065F) والألف الخنجرية (U+0670) والتطويل
#: (U+0640) — لا الأرقام الهندية ولا علاماتها (U+0660–U+066F) التي يحويها مدى «ً-ٰ» لو كُتب مدىً.
_TASHKEEL = re.compile("[\u064b-\u065f\u0670\u0640]")
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Article:
    #: معرّف المقالة ونسختها المنشورة، لا يُرسل أيٌّ منهما.
    id: str
    version: int
    title: str
    #: نصّ المقالة كما تُعرض للنموذج: العنوان والمشكلة والبيئة والحلّ والسبب.
    text: str


def kb_norm(text: str) -> str:
    """
    شكلٌ واحد للمقارنة: NFKC، وأحرفٌ صغيرة، وبلا تشكيلٍ ولا تطويل، ومسافاتٌ
    مفردة. نظير `ew_kb_norm` في قاعدة الدعم؛ اختبارٌ يقارنهما على مجموعة نصوص.
    """
    text = unicodedata.normalize("NFKC", text).lower()
    return _SPACES.sub(" ", _TASHKEEL.sub("", text)).strip()


def package(articles: Sequence[Article], *, budget: int = KB_CHARS) -> tuple[str, dict[str, tuple[str, int]]]:
    """
    كتلة `<kb>` ومعها خريطة المرجع إلى (المعرّف، النسخة). المقالات كاملةً
    بترتيبها حتى تتجاوز التالية الميزانية؛ لا تُقصّ مقالة.
    """
    used = 0
    blocks: list[str] = []
    refs: dict[str, tuple[str, int]] = {}
    for article in articles[:MAX_ARTICLES]:
        if used + len(article.text) > budget:
            break
        ref = f"A{len(refs) + 1}"
        refs[ref] = (article.id, article.version)
        blocks.append(tag("article", data(article.text), ref=ref, title=article.title))
        used += len(article.text)
    return tag("kb", "".join(blocks)), refs


def verify(quote: str, article_text: str) -> bool:
    """الاقتباس موجودٌ حرفياً في المقالة بعد تطبيع الطرفين، وطوله ضمن الحدّين."""
    needle = kb_norm(quote)
    if not QUOTE_LENGTH[0] <= len(needle) <= QUOTE_LENGTH[1]:
        return False
    return needle in kb_norm(article_text)
