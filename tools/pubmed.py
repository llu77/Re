"""
PubMed Integration — البحث في المصادر العلمية
==============================================
يستخدم NCBI E-Utilities API للبحث الحر والمجاني في PubMed
"""

import os
import requests
import xml.etree.ElementTree as ET
from typing import Optional

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _get_api_key() -> Optional[str]:
    """جلب NCBI API Key من متغيرات البيئة"""
    return os.environ.get("NCBI_API_KEY")


def search_pubmed_api(params: dict) -> dict:
    """
    البحث في PubMed عبر E-Utilities API

    Args:
        params: {
            query (str): مصطلحات البحث بالإنجليزية
            max_results (int): عدد النتائج (افتراضي: 10)
            date_range (str): "2020:2026"
            article_types (list): ["review", "clinical-trial", ...]
        }

    Returns:
        dict: نتائج البحث أو رسالة خطأ
    """
    query = params.get("query", "")
    max_results = params.get("max_results", 10)
    date_range = params.get("date_range", "")
    article_types = params.get("article_types", [])

    if not query:
        return {"error": "يجب تحديد مصطلحات البحث"}

    # الخطوة 1: ESearch — البحث والحصول على IDs
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }

    api_key = _get_api_key()
    if api_key:
        search_params["api_key"] = api_key

    # إضافة فلتر التاريخ
    if date_range and ":" in date_range:
        parts = date_range.split(":")
        if len(parts) == 2:
            search_params["datetype"] = "pdat"
            search_params["mindate"] = parts[0].strip()
            search_params["maxdate"] = parts[1].strip()

    # إضافة فلتر نوع المقال
    if article_types:
        type_filters = " OR ".join([f"{t}[pt]" for t in article_types])
        search_params["term"] += f" AND ({type_filters})"

    try:
        response = requests.get(
            f"{NCBI_BASE}/esearch.fcgi",
            params=search_params,
            timeout=15
        )
        response.raise_for_status()
        search_data = response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"فشل الاتصال بـ PubMed: {str(e)}"}
    except ValueError:
        return {"error": "استجابة غير صالحة من PubMed"}

    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    total_count = search_data.get("esearchresult", {}).get("count", "0")

    if not id_list:
        return {
            "results": [],
            "total_count": 0,
            "query_used": query,
            "message": "لم يتم العثور على نتائج لهذا البحث"
        }

    # الخطوة 2: ESummary — جلب ملخصات المقالات
    summary_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "json",
    }
    if api_key:
        summary_params["api_key"] = api_key

    try:
        summary_response = requests.get(
            f"{NCBI_BASE}/esummary.fcgi",
            params=summary_params,
            timeout=15
        )
        summary_response.raise_for_status()
        summary_data = summary_response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"فشل جلب ملخصات المقالات: {str(e)}"}

    # تنظيم النتائج
    articles = []
    for pmid in id_list:
        article_data = summary_data.get("result", {}).get(pmid, {})
        if not article_data:
            continue

        articles.append({
            "pmid": pmid,
            "title": article_data.get("title", ""),
            "authors": [
                a.get("name", "")
                for a in article_data.get("authors", [])[:5]
            ],
            "journal": article_data.get("source", ""),
            "pub_date": article_data.get("pubdate", ""),
            "doi": next(
                (
                    aid["value"]
                    for aid in article_data.get("articleids", [])
                    if aid.get("idtype") == "doi"
                ),
                ""
            ),
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        })

    return {
        "results": articles,
        "total_count": int(total_count),
        "returned_count": len(articles),
        "query_used": search_params["term"]
    }


def fetch_pubmed_article(pmid: str) -> dict:
    """
    جلب الملخص الكامل لمقال عبر PMID

    Args:
        pmid: معرف المقال في PubMed

    Returns:
        dict: بيانات المقال الكاملة أو رسالة خطأ
    """
    if not pmid or not str(pmid).strip().isdigit():
        return {"error": "PMID غير صالح"}

    fetch_params = {
        "db": "pubmed",
        "id": str(pmid).strip(),
        "retmode": "xml",
        "rettype": "abstract",
    }

    api_key = _get_api_key()
    if api_key:
        fetch_params["api_key"] = api_key

    try:
        response = requests.get(
            f"{NCBI_BASE}/efetch.fcgi",
            params=fetch_params,
            timeout=15
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": f"فشل جلب المقال: {str(e)}"}

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return {"error": "فشل في قراءة استجابة XML"}

    article = root.find(".//PubmedArticle")
    if article is None:
        return {"error": f"المقال {pmid} غير موجود أو تم سحبه"}

    # استخراج العنوان
    title = article.findtext(".//ArticleTitle", "")

    # استخراج الملخص (مع دعم الملخصات المقسمة)
    abstract_parts = article.findall(".//AbstractText")
    abstract_sections = []
    for part in abstract_parts:
        label = part.get("Label", "")
        text = part.text or ""
        if label:
            abstract_sections.append(f"**{label}:** {text}")
        else:
            abstract_sections.append(text)
    abstract = " ".join(abstract_sections)

    # استخراج معلومات النشر
    pub_year = article.findtext(".//PubDate/Year", "")
    journal = article.findtext(".//Journal/Title", "")

    # استخراج المؤلفين
    authors = []
    for author in article.findall(".//Author")[:10]:
        last = author.findtext("LastName", "")
        first = author.findtext("ForeName", "")
        if last:
            authors.append(f"{last} {first}".strip())

    # استخراج MeSH Terms
    mesh_terms = [
        m.findtext("DescriptorName", "")
        for m in article.findall(".//MeshHeading")
    ]

    # استخراج DOI
    doi = ""
    for article_id in article.findall(".//ArticleId"):
        if article_id.get("IdType") == "doi":
            doi = article_id.text or ""
            break

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "pub_year": pub_year,
        "abstract": abstract,
        "mesh_terms": mesh_terms[:15],
        "doi": doi,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    }
