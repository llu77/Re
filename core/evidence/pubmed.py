"""
عميل PubMed — بناء الاستعلام وتحليل الاستجابة
===============================================
يبني نصّ البحث من `EvidenceQuery` المفحوص، ثم `esearch` فـ`efetch`. طلبان لا
ثلاثة: `efetch` يحمل الملخّص ورؤوس MeSH التي لا يحملها `esummary`، وهي ما
يحتاجه الممارس ليقرّر أنّ المصدر يخصّ مريضه فعلاً.

منطق التحليل منقول من `tools/pubmed.py` (الملخّصات المقسَّمة، MeSH، DOI): كان
صحيحاً ومُجرَّباً، والعيب فيه لم يكن التحليل بل ما قبله — نصّ استعلام حرّ
ونتيجةٌ لا تُخزَّن.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from typing import Sequence

from core.evidence.transport import Request, Transport, TransportError
from core.evidence.types import EvidenceQuery

__all__ = ["ParsedArticle", "build_term", "fetch_articles", "search_ids"]

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_YEAR = re.compile(r"(1[89]\d{2}|20\d{2})")

#: حدّ أعلى لما يُطلب دفعةً واحدة. القارئ بشر، والطابور يُراجَع بالعين.
MAX_RESULTS = 10


@dataclass(frozen=True, slots=True)
class ParsedArticle:
    """مقال كما وصل من PubMed، قبل أن يُخزَّن ويصير `RetrievedSource`."""

    external_id: str
    title: str
    url: str
    journal: str | None
    published_year: int | None
    doi: str | None
    abstract: str | None
    mesh: tuple[str, ...]


def build_term(query: EvidenceQuery) -> str:
    """
    نصّ البحث كما سيغادر إلى الشبكة.

    يُبنى هنا لا عند المستدعي: هذه هي النقطة التي يصير فيها «لا نصّ حرّ»
    خاصيةً في الشيفرة لا قاعدةَ سلوك. كل جزء منه مصطلحٌ مرّ على المفردات
    المغلقة وقت إنشاء `EvidenceQuery`.
    """
    parts = [f'"{query.condition}"', f'"{query.intervention}"']
    if query.population:
        parts.append(f'"{query.population}"')

    term = " AND ".join(parts)
    if query.article_types:
        types = " OR ".join(f"{kind}[pt]" for kind in sorted(query.article_types))
        term += f" AND ({types})"
    return term


def _date_params(query: EvidenceQuery) -> dict[str, str]:
    if not query.years:
        return {}
    first, last = query.years
    return {"datetype": "pdat", "mindate": str(first), "maxdate": str(last)}


def search_ids(
    transport: Transport, query: EvidenceQuery, *, api_key: str | None = None
) -> tuple[str, list[str]]:
    """يُعيد (النصّ المُرسَل، معرّفات المقالات). لا استثناء على نتيجة فارغة."""
    term = build_term(query)
    params = {
        "db": "pubmed",
        "term": term,
        "retmax": str(MAX_RESULTS),
        "retmode": "json",
        "sort": "relevance",
        **_date_params(query),
    }
    if api_key:
        params["api_key"] = api_key

    response = transport.fetch(Request(url=f"{_BASE}/esearch.fcgi", params=params))
    if response.status != 200:
        raise TransportError(f"PubMed أعاد {response.status} للبحث")

    try:
        payload = json.loads(response.text)
    except ValueError as exc:
        raise TransportError("استجابة بحث غير صالحة من PubMed") from exc

    ids = payload.get("esearchresult", {}).get("idlist", [])
    return term, [str(one) for one in ids if str(one).isdigit()]


def fetch_articles(
    transport: Transport, pmids: Sequence[str], *, api_key: str | None = None
) -> list[ParsedArticle]:
    """يجلب المقالات كاملة ويحلّلها. قائمة فارغة إن لم يُطلب شيء."""
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if api_key:
        params["api_key"] = api_key

    response = transport.fetch(Request(url=f"{_BASE}/efetch.fcgi", params=params))
    if response.status != 200:
        raise TransportError(f"PubMed أعاد {response.status} للجلب")

    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise TransportError("تعذّر تحليل استجابة XML من PubMed") from exc

    return [
        parsed
        for element in root.findall(".//PubmedArticle")
        if (parsed := _parse_article(element)) is not None
    ]


def _text_of(element) -> str:
    """نصّ العنصر بكل ما فيه. `findtext` يُسقط ما داخل الوسوم مثل <i>."""
    return " ".join("".join(element.itertext()).split())


def _parse_article(article) -> ParsedArticle | None:
    pmid_element = article.find(".//MedlineCitation/PMID")
    if pmid_element is None or not (pmid_element.text or "").strip():
        return None
    pmid = pmid_element.text.strip()

    title_element = article.find(".//ArticleTitle")
    title = _text_of(title_element) if title_element is not None else ""
    if not title:
        # عنوان فارغ يعني صفّاً بلا معنى للممارس. نُسقطه بدل تخزين فراغ.
        return None

    sections = []
    for part in article.findall(".//AbstractText"):
        body = _text_of(part)
        if not body:
            continue
        label = (part.get("Label") or "").strip()
        sections.append(f"{label}: {body}" if label else body)
    abstract = " ".join(sections) or None

    journal_element = article.find(".//Journal/Title")
    journal = _text_of(journal_element) if journal_element is not None else None

    doi = None
    for identifier in article.findall(".//ArticleId"):
        if identifier.get("IdType") == "doi" and (identifier.text or "").strip():
            doi = identifier.text.strip()
            break

    mesh = tuple(
        _text_of(descriptor)
        for descriptor in article.findall(".//MeshHeading/DescriptorName")
        if _text_of(descriptor)
    )

    return ParsedArticle(
        external_id=pmid,
        title=title,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        journal=journal or None,
        published_year=_published_year(article),
        doi=doi,
        abstract=abstract,
        mesh=mesh[:15],
    )


def _published_year(article) -> int | None:
    """
    السنة من `PubDate/Year`، وإلا من `MedlineDate` مثل «2019 Jan-Feb».

    لا نخمّن سنة غائبة: غيابها يُخزَّن غياباً، فالممارس يرى ما لا نعرفه.
    """
    year = article.findtext(".//PubDate/Year")
    if year and year.strip().isdigit():
        return int(year.strip())

    medline = article.findtext(".//PubDate/MedlineDate") or ""
    found = _YEAR.search(medline)
    return int(found.group(1)) if found else None
