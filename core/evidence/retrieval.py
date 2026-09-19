"""
الاسترجاع — المدخل الوحيد للأدلة
==================================
`search()` هي الدالة الوحيدة التي تُنتج مصادر في هذا النظام. ما لم يمرّ منها
لا يوجد له صفّ في `evidence_sources`، وما لا صفّ له لا يُستشهَد به — يرفضه
المفتاح الخارجي. بهذا يستحيل على نموذج لغوي أن يستشهد بمعرّف اختلقه.

ثلاثة قرارات تحكم هذا الملف:

  • **ذاكرة أولاً.** استعلام مطابق خلال `CACHE_TTL` يُخدَم من قاعدة البيانات
    بلا لمس الشبكة. هذا ليس تحسين أداء فحسب: مع قرار «المسترجَع آلياً فقط»،
    الذاكرةُ هي ما يُبقي العيادة عاملة حين ينقطع PubMed.
  • **الغياب رفض.** نتيجة فارغة ترفع `NoEvidence`. لا «تابع بلا مصدر»، ولا
    نصّ من ذاكرة النموذج يسدّ الفراغ — وهذه هي القاعدة 3 حرفياً.
  • **كل استعلام يُسجَّل بنصّه الذي غادر.** `evidence_queries.sent_term` هو
    الدليل على أنّ ما غادر لاتينيٌّ مُركَّب من مفردات مغلقة، لا ملاحظة مريض.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Sequence
from uuid import UUID

from core import db
from core.clock import now
from core.evidence import pubmed
from core.evidence.transport import Transport, default_transport
from core.evidence.types import EvidenceQuery, NoEvidence, RetrievedSource
from core.types import Actor

__all__ = ["CACHE_TTL", "search", "sources_for"]

#: أسبوع. الدليل المنشور لا يتغيّر يومياً، والبحث المكرر في اليوم نفسه شائع.
CACHE_TTL = timedelta(days=7)

_SOURCE_COLUMNS = (
    "s.id, s.source, s.external_id, s.title, s.url, s.journal,"
    " s.published_year, s.doi, s.abstract, s.mesh, s.retrieved_at"
)

_CACHED_QUERY = """
SELECT id FROM evidence_queries
WHERE query = %s::jsonb AND executed_at > %s
ORDER BY executed_at DESC
LIMIT 1
"""

_CACHED_SOURCES = """
SELECT s.id, s.source, s.external_id, s.title, s.url, s.journal,
       s.published_year, s.doi, s.abstract, s.mesh, s.retrieved_at
FROM evidence_query_result r
JOIN evidence_sources s ON s.id = r.source_id
WHERE r.query_id = %s
ORDER BY r.rank
"""

_SOURCES_BY_ID = """
SELECT s.id, s.source, s.external_id, s.title, s.url, s.journal,
       s.published_year, s.doi, s.abstract, s.mesh, s.retrieved_at
FROM evidence_sources s
WHERE s.id = ANY(%s)
"""

_RECORD_SOURCE = """
SELECT record_retrieved_source(%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) AS id
"""

_RECORD_QUERY = """
INSERT INTO evidence_queries
    (tenant_id, actor_id, query, sent_term, result_count, served_from_cache)
VALUES (%s, %s, %s::jsonb, %s, %s, %s)
RETURNING id
"""

_RECORD_RESULT = """
INSERT INTO evidence_query_result (query_id, source_id, rank) VALUES (%s, %s, %s)
"""


def _to_source(row) -> RetrievedSource:
    mesh = row["mesh"] or []
    return RetrievedSource(
        id=row["id"],
        source=row["source"],
        external_id=row["external_id"],
        title=row["title"],
        url=row["url"],
        journal=row["journal"],
        published_year=row["published_year"],
        doi=row["doi"],
        abstract=row["abstract"],
        mesh=tuple(mesh),
        retrieved_at=row["retrieved_at"],
    )


def _api_key() -> str | None:
    """مفتاح NCBI اختياري: يرفع الحدّ من 3 إلى 10 طلبات في الثانية."""
    return os.environ.get("NCBI_API_KEY") or None


def search(
    actor: Actor, query: EvidenceQuery, *, transport: Transport | None = None
) -> list[RetrievedSource]:
    """
    يسترجع مصادر لهذا الاستعلام، أو يرفع `NoEvidence`.

    `transport` محقون ليبقى الحدّ الخارجي قابلاً للقياس في الاختبار: نفس
    المسار، وناقلٌ يسجّل كل ما يغادر.
    """
    record = json.dumps(query.as_record(), ensure_ascii=False, sort_keys=True)
    term = pubmed.build_term(query)

    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_CACHED_QUERY, (record, now() - CACHE_TTL))
        hit = cursor.fetchone()
        if hit is not None:
            cursor.execute(_CACHED_SOURCES, (hit["id"],))
            cached = [_to_source(row) for row in cursor.fetchall()]
            if cached:
                _log(cursor, actor, record, term, cached, from_cache=True)
                return cached

    articles = _retrieve(transport or default_transport(), query)
    if not articles:
        raise NoEvidence(
            "لم يُسترجع أي مصدر لهذا الاستعلام. لا يُقترح محتوى سريري بلا مصدر."
        )

    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        stored: list[UUID] = []
        for article in articles:
            cursor.execute(
                _RECORD_SOURCE,
                ("PUBMED", article.external_id, article.title, article.url,
                 article.journal, article.published_year, article.doi,
                 article.abstract, json.dumps(list(article.mesh), ensure_ascii=False)),
            )
            stored.append(cursor.fetchone()["id"])

        cursor.execute(_SOURCES_BY_ID, (stored,))
        by_id = {row["id"]: _to_source(row) for row in cursor.fetchall()}
        sources = [by_id[identifier] for identifier in stored]

        _log(cursor, actor, record, term, sources, from_cache=False)

    return sources


def _retrieve(transport: Transport, query: EvidenceQuery) -> Sequence[pubmed.ParsedArticle]:
    _term, ids = pubmed.search_ids(transport, query, api_key=_api_key())
    return pubmed.fetch_articles(transport, ids, api_key=_api_key())


def _log(
    cursor,
    actor: Actor,
    record: str,
    term: str,
    sources: Sequence[RetrievedSource],
    *,
    from_cache: bool,
) -> None:
    cursor.execute(
        _RECORD_QUERY,
        (actor.tenant_id, actor.id, record, term, len(sources), from_cache),
    )
    query_id = cursor.fetchone()["id"]
    for rank, source in enumerate(sources):
        cursor.execute(_RECORD_RESULT, (query_id, source.id, rank))


def sources_for(actor: Actor, source_ids: Sequence[UUID]) -> list[RetrievedSource]:
    """قراءة مصادر بمعرّفاتها. للعرض بجانب المقترح في طابور المراجعة."""
    if not source_ids:
        return []
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_SOURCES_BY_ID, (list(source_ids),))
        return [_to_source(row) for row in cursor.fetchall()]
