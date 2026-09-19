"""
أنواع طبقة الأدلة
==================
القاعدة 3: لا محتوى سريري بلا مصدر مسترجَع، وغياب المصدر رفضٌ صريح لا تخمين.
القاعدة 5 (الشقّ الثاني): لا بيانات مريض في استعلامات المصادر الخارجية.

الثاني مفروض هنا **بنيوياً لا بفحص**: لا يوجد في `EvidenceQuery` وسيطٌ يحمل
نصاً حراً. من أراد أن يبحث فليملأ حقولاً من مفردات مغلقة، ووحدة الاسترجاع
تبني نصّ الاستعلام بنفسها. فلا مسار — لا صحيحاً ولا خاطئاً — يحمل ملاحظة
مريض إلى الشبكة، لأن لا شيء يقبلها أصلاً.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

__all__ = [
    "ARTICLE_TYPE",
    "CONDITION",
    "EvidenceQuery",
    "EvidenceSourceKind",
    "Facet",
    "INTERVENTION",
    "NoEvidence",
    "POPULATION",
    "RetrievedSource",
    "TERM_SHAPE",
    "UnknownTerm",
]

#: النسخة الأولى بمصدر واحد. إضافة مصدر لاحقاً توسيعٌ لهذا النوع لا التفاف عليه.
EvidenceSourceKind = Literal["PUBMED"]

CONDITION = "conditions"
INTERVENTION = "interventions"
POPULATION = "populations"
ARTICLE_TYPE = "article_types"

Facet = Literal["conditions", "interventions", "populations", "article_types"]

#: شكل المصطلح المسموح. لاتينية وأرقام وعلامات بحثية قليلة، لا غير.
#:
#: هذا وحده يمنع كل PHI في هذا النظام: أسماء المرضى وشكاواهم وملاحظاتهم عربية
#: بلا استثناء، فمحرف عربي واحد يُسقط المصطلح قبل أن يقترب من الشبكة.
TERM_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.'()\-]*$")

#: أقدم سنة نشر مقبولة في مدى التاريخ. أقدم من ذلك ليس مدى بل خطأ إدخال.
_EARLIEST_YEAR = 1900


class UnknownTerm(Exception):
    """مصطلح خارج المفردات المغلقة، أو بشكل غير مسموح. رفضٌ لا تخمين."""


class NoEvidence(Exception):
    """لم يُسترجع مصدر. القاعدة 3: هذا رفض صريح، لا مسوّغ لمحتوى بلا مصدر."""


@dataclass(frozen=True, slots=True)
class EvidenceQuery:
    """
    استعلام مُركَّب من مفردات مغلقة.

    التحقق في `__post_init__` لا في المستدعي: الكائن نفسه لا يوجد إلا صالحاً،
    فلا يمكن أن يُمرَّر استعلامٌ غير مفحوص إلى الاسترجاع بالسهو.
    """

    condition: str
    intervention: str
    population: str | None = None
    years: tuple[int, int] | None = None
    article_types: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        # استيراد متأخر: المفردات تستورد هذه الوحدة لأجل `UnknownTerm`، وهذا
        # الاستدعاء يقع وقت الإنشاء لا وقت التحميل، فلا دورة استيراد.
        from core.evidence import vocabulary

        vocabulary.check(CONDITION, self.condition)
        vocabulary.check(INTERVENTION, self.intervention)
        if self.population is not None:
            vocabulary.check(POPULATION, self.population)
        for article_type in sorted(self.article_types):
            vocabulary.check(ARTICLE_TYPE, article_type)

        if self.years is not None:
            first, last = self.years
            if not (_EARLIEST_YEAR <= first <= last):
                raise UnknownTerm(f"مدى سنوات غير صالح: {self.years}")

    def as_record(self) -> dict[str, object]:
        """تمثيل قابل للتخزين في `evidence_queries.query`."""
        return {
            "condition": self.condition,
            "intervention": self.intervention,
            "population": self.population,
            "years": list(self.years) if self.years else None,
            "article_types": sorted(self.article_types),
        }


@dataclass(frozen=True, slots=True)
class RetrievedSource:
    """
    مصدر استُرجع فعلاً وخُزِّن.

    وجوده صفّاً في `evidence_sources` هو ما يجعل الاستشهاد به ممكناً؛ معرّفٌ
    لم يُسترجع لا يملك صفّاً، فالمفتاح الخارجي يرفض الاستشهاد به. بهذا يستحيل
    على النموذج أن يستشهد برقم اختلقه.
    """

    id: UUID
    source: EvidenceSourceKind
    external_id: str
    title: str
    url: str
    journal: str | None = None
    published_year: int | None = None
    doi: str | None = None
    abstract: str | None = None
    mesh: tuple[str, ...] = ()
    retrieved_at: datetime | None = None
