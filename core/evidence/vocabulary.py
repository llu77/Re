"""
المفردات المغلقة
=================
الحارس الوحيد بين ما يطلبه المستدعي وما يغادر إلى الشبكة.

فحصان متعاقبان على كل مصطلح، والثاني لا يُغني عن الأول:

  1. **الشكل** — `TERM_SHAPE`: لاتينية وأرقام وعلامات قليلة. يرفض العربية
     كلها، وهي لغة كل بيانات المريض في هذا النظام.
  2. **العضوية** — المصطلح مذكور في `vocabulary.yaml`. الشكل وحده يسمح بنصّ
     إنجليزي حرّ؛ العضوية تُغلق ذلك أيضاً.

التوسيع بتعديل الملف ومراجعته كشيفرة. لا واجهة هنا تضيف مصطلحاً وقت التشغيل،
لأن تلك الواجهة هي الثغرة نفسها.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from core.evidence.types import (
    ARTICLE_TYPE,
    CONDITION,
    INTERVENTION,
    POPULATION,
    TERM_SHAPE,
    Facet,
    UnknownTerm,
)

__all__ = ["FACETS", "check", "label_of", "terms"]

_VOCABULARY = Path(__file__).resolve().parent / "vocabulary.yaml"

#: الأوجه المعروفة. وجه غير مذكور هنا خطأ برمجي لا إدخال مستخدم.
FACETS: tuple[Facet, ...] = (CONDITION, INTERVENTION, POPULATION, ARTICLE_TYPE)


@lru_cache(maxsize=1)
def _loaded() -> Mapping[str, Mapping[str, str]]:
    """{وجه: {مصطلح: تسمية عربية}}. يُقرأ مرة واحدة."""
    raw = yaml.safe_load(_VOCABULARY.read_text(encoding="utf-8")) or {}

    table: dict[str, dict[str, str]] = {}
    for facet in FACETS:
        entries = raw.get(facet) or []
        table[facet] = {}
        for entry in entries:
            term = str(entry["term"]).strip()
            # ملف المفردات نفسه يخضع للفحص: مصطلح مشوّه فيه عيبٌ يجب أن يظهر
            # عند التحميل لا عند أول بحث.
            if not TERM_SHAPE.match(term):
                raise ValueError(f"مصطلح بشكل غير مسموح في المفردات: {term!r}")
            table[facet][term] = str(entry["label"]).strip()

    missing = [facet for facet in FACETS if not table[facet]]
    if missing:
        raise ValueError(f"أوجه فارغة في المفردات: {missing}")
    return table


def terms(facet: Facet) -> Sequence[tuple[str, str]]:
    """المصطلحات المسموحة لوجه، مع تسمياتها العربية للعرض."""
    if facet not in FACETS:
        raise ValueError(f"وجه غير معروف: {facet}")
    return tuple(_loaded()[facet].items())


def label_of(facet: Facet, term: str) -> str:
    """التسمية العربية لمصطلح. للعرض وحده — لا تغادر هذا الخادم."""
    return _loaded()[facet][term]


def check(facet: Facet, term: str) -> str:
    """
    يُعيد المصطلح إن كان مسموحاً، ويرفع `UnknownTerm` وإلا.

    لا تصحيح ولا تقريب ولا «أقرب مصطلح»: التخمين هنا يعني بحثاً عن غير ما
    قصده الممارس، وهو أسوأ من الرفض لأنه يُنتج دليلاً يبدو سليماً.
    """
    if facet not in FACETS:
        raise ValueError(f"وجه غير معروف: {facet}")

    candidate = term.strip()
    if not TERM_SHAPE.match(candidate):
        raise UnknownTerm(f"شكل مصطلح غير مسموح في {facet}")

    if candidate not in _loaded()[facet]:
        raise UnknownTerm(f"مصطلح خارج المفردات المغلقة في {facet}: {candidate}")
    return candidate
