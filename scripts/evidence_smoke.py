#!/usr/bin/env python3
"""
تحقّق حيّ من عميل الأدلة — استعلام واحد حقيقي إلى PubMed
=========================================================
الاختبارات تعمل بناقل محقون وعيّنات ثابتة، فتثبت الضمانات ولا تثبت أن صيغة
استجابة NCBI اليوم كما نتوقّعها. هذا السكربت يسدّ تلك الفجوة وحدها.

لا قاعدة بيانات ولا مريض ولا فاعل: استعلام من المفردات المغلقة، وطباعة ما
عاد. شغّله في بيئة تصل إلى `eutils.ncbi.nlm.nih.gov`:

    python3 scripts/evidence_smoke.py

يُخرج صفر عند النجاح، وواحداً عند فشل الاتصال أو التحليل.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evidence.pubmed import build_term, fetch_articles, search_ids  # noqa: E402
from core.evidence.transport import TransportError, default_transport  # noqa: E402
from core.evidence.types import EvidenceQuery  # noqa: E402

QUERY = EvidenceQuery(
    condition="Stroke",
    intervention="Exercise Therapy",
    population="Aged",
    years=(2020, 2026),
    article_types=frozenset({"systematic review"}),
)


def main() -> int:
    print("النصّ المُرسَل:", build_term(QUERY))

    transport = default_transport()
    try:
        _term, ids = search_ids(transport, QUERY)
        print(f"معرّفات: {len(ids)}")
        if not ids:
            print("لا نتائج — هذا رفض صريح في الإنتاج، لا خطأ في العميل.")
            return 0

        articles = fetch_articles(transport, ids)
    except TransportError as exc:
        print(f"فشل الاتصال: {exc}", file=sys.stderr)
        return 1

    if not articles:
        print("وصلت معرّفات ولم يُحلَّل أي مقال — صيغة الاستجابة تغيّرت.", file=sys.stderr)
        return 1

    for article in articles[:3]:
        print("─" * 60)
        print(f"PMID  : {article.external_id}")
        print(f"العنوان: {article.title[:90]}")
        print(f"المجلة : {article.journal}  ({article.published_year})")
        print(f"DOI   : {article.doi}")
        print(f"MeSH  : {', '.join(article.mesh[:5])}")
        print(f"ملخّص  : {(article.abstract or '')[:120]}")

    missing = [
        name
        for name, value in (
            ("العنوان", articles[0].title),
            ("الرابط", articles[0].url),
        )
        if not value
    ]
    if missing:
        print(f"حقول ناقصة في أول مقال: {missing}", file=sys.stderr)
        return 1

    print("─" * 60)
    print(f"تمّ: {len(articles)} مقالاً حُلِّل بنجاح.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
