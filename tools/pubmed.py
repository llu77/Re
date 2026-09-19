"""
PubMed — واجهة الأداة القديمة فوق طبقة الأدلة
===============================================
لم يعد في هذا الملف اتصالٌ بالشبكة ولا نصّ استعلام حرّ. كلاهما انتقل إلى
`core.evidence`: الاتصال إلى `transport.py` وحده، والاستعلام إلى مفردات
مغلقة يفحصها `vocabulary.py`.

**ما تغيّر ولماذا:** كان هذا الملف يمرّر `params["query"]` — نصّاً يؤلّفه
النموذج — إلى NCBI كما هو. سياق المريض في هذا النظام عربيّ، ولا شيء كان
يمنع ملاحظةً سريرية من الخروج في سطر عنوان HTTP. القاعدة 5 تمنع ذلك،
ومعيار القبول 2 يختبره.

**حدّ مُعلَن:** ما يُسترجع هنا لا يُخزَّن، فلا يصلح للاستشهاد. التخزين يحتاج
فاعلاً ومستأجراً، وهما لا يوجدان في هذا المسار القديم. المقترحات تُنشأ
وتُستشهَد عبر بوابة الممارس (`/practitioner/evidence/search` ثم
`/practitioner/proposals/{id}/citations`)، حيث يُخزَّن كل مصدر ويصير
الاستشهاد به قابلاً للتحقق.
"""

from typing import Any, Dict

from core.evidence import vocabulary
from core.evidence.pubmed import fetch_articles, search_ids
from core.evidence.transport import TransportError, default_transport
from core.evidence.types import (
    ARTICLE_TYPE,
    CONDITION,
    INTERVENTION,
    POPULATION,
    EvidenceQuery,
    UnknownTerm,
)

_NOT_CITABLE = (
    "هذه النتائج للاطلاع فقط ولا تصلح للاستشهاد: الاستشهاد يحتاج مصدراً"
    " مخزَّناً يُسترجع عبر بوابة الممارس."
)


def _allowed(facet: str) -> list[Dict[str, str]]:
    return [{"term": term, "label": label} for term, label in vocabulary.terms(facet)]


def _refusal(facet: str, exc: Exception) -> Dict[str, Any]:
    """
    رفضٌ يقول ما المسموح، لا رفضٌ صامت.

    النموذج لا يخمّن مصطلحاً بديلاً من عنده: القائمة تُعطى له صريحةً ليختار
    منها، وما ليس فيها لا يُبحَث به.
    """
    return {
        "error": str(exc),
        "allowed_terms": {facet: _allowed(facet)},
        "note": "المصطلحات مغلقة عمداً: لا نصّ حرّ يغادر هذا النظام.",
    }


def search_pubmed_api(params: dict) -> dict:
    """
    بحث في PubMed باستعلام مُركَّب من مفردات مغلقة.

    `params`: condition · intervention · population? · from_year? · to_year?
    · article_types?
    """
    condition = str(params.get("condition", "")).strip()
    intervention = str(params.get("intervention", "")).strip()
    population = str(params.get("population", "")).strip() or None

    if not condition or not intervention:
        return {
            "error": "البحث يحتاج حالة وتدخّلاً من المفردات المغلقة",
            "allowed_terms": {
                CONDITION: _allowed(CONDITION),
                INTERVENTION: _allowed(INTERVENTION),
            },
        }

    years = None
    first, last = params.get("from_year"), params.get("to_year")
    if first and last:
        years = (int(first), int(last))

    try:
        query = EvidenceQuery(
            condition=condition,
            intervention=intervention,
            population=population,
            years=years,
            article_types=frozenset(params.get("article_types") or []),
        )
    except UnknownTerm as exc:
        message = str(exc)
        for facet in (CONDITION, INTERVENTION, POPULATION, ARTICLE_TYPE):
            if facet in message:
                return _refusal(facet, exc)
        return {"error": message}

    transport = default_transport()
    try:
        term, ids = search_ids(transport, query)
        articles = fetch_articles(transport, ids)
    except TransportError as exc:
        # انقطاع المصدر ليس غياب دليل، ولا يُقرأ نتيجةً سلبية.
        return {"error": f"تعذّر الوصول إلى PubMed: {exc}", "results": []}

    if not articles:
        return {
            "results": [],
            "returned_count": 0,
            "query_used": term,
            "message": "لم يُعثر على مصادر. لا يُقترح محتوى سريري بلا مصدر.",
        }

    return {
        "results": [
            {
                "pmid": article.external_id,
                "title": article.title,
                "journal": article.journal,
                "pub_year": article.published_year,
                "doi": article.doi,
                "abstract": article.abstract,
                "mesh_terms": list(article.mesh),
                "pubmed_url": article.url,
            }
            for article in articles
        ],
        "returned_count": len(articles),
        "query_used": term,
        "citable": False,
        "note": _NOT_CITABLE,
    }


def fetch_pubmed_article(pmid: str) -> dict:
    """تفاصيل مقال واحد بمعرّفه. الرقم وحده يغادر، ولا شيء سواه."""
    identifier = str(pmid).strip()
    if not identifier.isdigit():
        return {"error": "PMID غير صالح"}

    try:
        articles = fetch_articles(default_transport(), [identifier])
    except TransportError as exc:
        return {"error": f"تعذّر جلب المقال: {exc}"}

    if not articles:
        return {"error": f"المقال {identifier} غير موجود أو تم سحبه"}

    article = articles[0]
    return {
        "pmid": article.external_id,
        "title": article.title,
        "journal": article.journal,
        "pub_year": article.published_year,
        "abstract": article.abstract,
        "mesh_terms": list(article.mesh),
        "doi": article.doi,
        "pubmed_url": article.url,
        "citable": False,
        "note": _NOT_CITABLE,
    }
