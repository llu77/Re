"""
بوابة الاستشهاد — معيارا القبول 2 و3
======================================
2. لا بيانات مريض في استعلامات المصادر الخارجية.
3. مقترح بلا استشهاد قابل للتحقق لا يدخل طابور المراجعة.

الناقل محقون، فكل ما يغادر إلى الشبكة يُقاس هنا على المسار الحقيقي لا يُراجَع
في الشيفرة. والبوابة تُختبر على قاعدة البيانات لا على الوحدة: المنع يجب أن
يصمد لأي مسار، بما فيه `UPDATE` مباشر بدور الممارس.
"""

from __future__ import annotations

import json
import re
from uuid import uuid4

import pytest
from psycopg import errors as pg_errors

from core import citations, proposals
from core.evidence import EvidenceQuery, NoEvidence, UnknownTerm, retrieval
from core.evidence.transport import Request, Response
from core.types import Actor
from tests.conftest import requires_db

pytestmark = requires_db

ARABIC = re.compile(r"[؀-ۿ]")

#: علامات فارقة تُزرع في ملف المريض. ظهور أيٍّ منها في أي طلب خارجي تسريب.
SENTINELS = (
    "محمد عبدالله الفارقة",
    "SENTINEL-FILE-90210",
    "يشكو من ألم حاد في الكتف الأيمن منذ ثلاثة أسابيع",
)

ESEARCH = json.dumps({"esearchresult": {"count": "2", "idlist": ["30000001", "30000002"]}})

EFETCH = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">30000001</PMID>
      <Article>
        <Journal><Title>Journal of Rehabilitation Medicine</Title>
          <JournalIssue><PubDate><Year>2021</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Exercise therapy after <i>stroke</i>: a systematic review</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Motor recovery varies widely.</AbstractText>
          <AbstractText Label="RESULTS">Task-specific practice improved gait speed.</AbstractText>
        </Abstract>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Stroke Rehabilitation</DescriptorName></MeshHeading>
        <MeshHeading><DescriptorName>Exercise Therapy</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData><ArticleIdList>
      <ArticleId IdType="pubmed">30000001</ArticleId>
      <ArticleId IdType="doi">10.1234/jrm.2021.0001</ArticleId>
    </ArticleIdList></PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">30000002</PMID>
      <Article>
        <Journal><Title>Clinical Rehabilitation</Title>
          <JournalIssue><PubDate><MedlineDate>2019 Jan-Feb</MedlineDate></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Home-based programmes for hemiplegia</ArticleTitle>
      </Article>
    </MedlineCitation>
    <PubmedData><ArticleIdList>
      <ArticleId IdType="pubmed">30000002</ArticleId>
    </ArticleIdList></PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
""".encode("utf-8")

EMPTY_SEARCH = json.dumps({"esearchresult": {"count": "0", "idlist": []}})


class RecordingTransport:
    """ناقل يسجّل كل ما يغادر. هو أداة القياس لمعيار القبول 2."""

    def __init__(self, *, search_body: str = ESEARCH, fetch_body: bytes = EFETCH) -> None:
        self.requests: list[Request] = []
        self._search = search_body
        self._fetch = fetch_body

    def fetch(self, request: Request) -> Response:
        self.requests.append(request)
        if "esearch" in request.url:
            return Response(status=200, content=self._search.encode("utf-8"))
        return Response(status=200, content=self._fetch)

    def everything_sent(self) -> str:
        return " ".join(
            request.url + " " + " ".join(f"{k}={v}" for k, v in request.params.items())
            for request in self.requests
        )


QUERY = EvidenceQuery(
    condition="Stroke",
    intervention="Exercise Therapy",
    population="Aged",
    years=(2015, 2026),
    article_types=frozenset({"systematic review"}),
)


@pytest.fixture
def actor(seed) -> Actor:
    return Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)


@pytest.fixture
def marked_patient(owner, seed):
    """ملف مريض مزروع بعلامات فارقة، عربية ورقمية."""
    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE patients SET display_name = %s, file_number = 90210 WHERE id = %s",
            (SENTINELS[0], seed.patient_a),
        )
    return seed.patient_a


def _cited_plan(actor, patient_id, transport, *, kind="PLAN"):
    """مقترح ومعه استشهاد من مصدر مسترجَع — الحالة السليمة."""
    sources = retrieval.search(actor, QUERY, transport=transport)
    proposal = proposals.create(
        actor, patient_id=patient_id, kind=kind, payload={"steps": []}
    )
    citations.cite(actor, proposal_id=proposal.id, source_id=sources[0].id)
    return proposal, sources


# ── معيار القبول 2: لا PHI يغادر ────────────────────────────────────────
def test_no_patient_data_reaches_the_wire(actor, marked_patient):
    """
    كل ما غادر لاتينيٌّ مُركَّب من المفردات المغلقة.

    الفحص على المسار الحقيقي بناقل يسجّل: لا مراجعة شيفرة، ولا ثقة في نيّة
    المستدعي.
    """
    transport = RecordingTransport()
    retrieval.search(actor, QUERY, transport=transport)

    sent = transport.everything_sent()
    assert transport.requests, "لم يُرسَل شيء — الاختبار بلا معنى"
    for sentinel in SENTINELS:
        assert sentinel not in sent
    assert not ARABIC.search(sent), f"محرف عربي في طلب خارجي: {sent[:200]}"


def test_the_query_type_has_no_free_text_field(actor):
    """لا وسيط يقبل نصاً حراً: الرفض في بناء الكائن لا في فحص لاحق."""
    for bad in (
        {"condition": SENTINELS[0], "intervention": "Exercise Therapy"},
        {"condition": "Stroke", "intervention": SENTINELS[2]},
        {"condition": "Stroke[All Fields] OR patient", "intervention": "Exercise Therapy"},
        {"condition": "Stroke", "intervention": "Crystal Healing"},
    ):
        with pytest.raises(UnknownTerm):
            EvidenceQuery(**bad)


def test_the_database_refuses_to_record_a_non_latin_query(owner, seed):
    """الطبقة الثالثة: حتى لو غادر نصّ عربي، لا يمكن تسجيله فيصير السجل دليلاً."""
    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.CheckViolation):
            cursor.execute(
                "INSERT INTO evidence_queries"
                " (tenant_id, actor_id, query, sent_term, result_count)"
                " VALUES (%s, %s, '{}'::jsonb, %s, 0)",
                (seed.tenant_a, seed.practitioner_a, SENTINELS[2]),
            )


def test_every_search_is_recorded_with_the_term_that_was_sent(actor):
    transport = RecordingTransport()
    retrieval.search(actor, QUERY, transport=transport)

    from core import db

    with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
        cursor.execute(
            "SELECT sent_term, result_count, served_from_cache FROM evidence_queries"
        )
        rows = cursor.fetchall()

    assert len(rows) == 1
    assert rows[0]["result_count"] == 2
    assert rows[0]["served_from_cache"] is False
    assert '"Stroke"' in rows[0]["sent_term"]
    assert "systematic review[pt]" in rows[0]["sent_term"]


# ── القاعدة 3: الغياب رفض ───────────────────────────────────────────────
def test_an_empty_result_is_an_explicit_refusal(actor):
    transport = RecordingTransport(search_body=EMPTY_SEARCH)
    with pytest.raises(NoEvidence):
        retrieval.search(actor, QUERY, transport=transport)


# ── الذاكرة ─────────────────────────────────────────────────────────────
def test_a_repeated_query_is_served_without_touching_the_wire(actor):
    first = RecordingTransport()
    retrieval.search(actor, QUERY, transport=first)

    second = RecordingTransport()
    again = retrieval.search(actor, QUERY, transport=second)

    assert not second.requests, "الاستعلام المكرر لمس الشبكة"
    assert [source.external_id for source in again] == ["30000001", "30000002"]


def test_another_tenant_does_not_reuse_this_tenants_query(seed):
    """الذاكرة داخل المستأجر: أثر بحث عيادة لا يظهر لعيادة أخرى."""
    first = Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)
    second = Actor(id=seed.practitioner_b, role="PRACTITIONER", tenant_id=seed.tenant_b)

    retrieval.search(first, QUERY, transport=RecordingTransport())
    transport = RecordingTransport()
    retrieval.search(second, QUERY, transport=transport)

    assert transport.requests, "المستأجر الثاني خُدِم من ذاكرة الأول"


# ── معيار القبول 3: البوابة ─────────────────────────────────────────────
@pytest.mark.parametrize("kind", ["PLAN", "PLAN_UPDATE", "READINESS"])
def test_a_proposal_without_a_citation_cannot_enter_the_queue(actor, seed, kind):
    proposal = proposals.create(
        actor, patient_id=seed.patient_a, kind=kind, payload={"steps": []}
    )
    with pytest.raises(proposals.EvidenceRequired):
        proposals.submit(proposal.id, actor)


@pytest.mark.parametrize("kind", ["PLAN", "PLAN_UPDATE", "READINESS"])
def test_a_cited_proposal_enters_the_queue(actor, seed, kind):
    transport = RecordingTransport()
    proposal, _sources = _cited_plan(actor, seed.patient_a, transport, kind=kind)
    assert proposals.submit(proposal.id, actor).status == "PENDING"


def test_documentation_needs_no_citation(actor, seed):
    """التوثيق يسجّل ما جرى لا توصية — إلزامه باستشهاد يُنتج استشهاداً شكلياً."""
    proposal = proposals.create(
        actor, patient_id=seed.patient_a, kind="DOCUMENTATION", payload={"note": "x"}
    )
    assert proposals.submit(proposal.id, actor).status == "PENDING"


def test_the_gate_holds_for_a_direct_update(actor, seed, practitioner_conn):
    """المنع في المحفّز لا في `core.proposals`: `UPDATE` مباشر يُرفض أيضاً."""
    from tests.conftest import set_actor

    proposal = proposals.create(
        actor, patient_id=seed.patient_a, kind="PLAN", payload={"steps": []}
    )
    set_actor(practitioner_conn, tenant_id=seed.tenant_a, actor_id=seed.practitioner_a)
    with practitioner_conn.cursor() as cursor:
        with pytest.raises(pg_errors.CheckViolation):
            cursor.execute(
                "UPDATE proposals SET status = 'PENDING', queued_at = now() WHERE id = %s",
                (proposal.id,),
            )


# ── الاستشهاد نفسه ──────────────────────────────────────────────────────
def test_a_fabricated_identifier_cannot_be_cited(actor, seed):
    """معرّف لم يُسترجع لا يملك صفّاً — والمفتاح الخارجي يرفضه."""
    proposal = proposals.create(
        actor, patient_id=seed.patient_a, kind="PLAN", payload={"steps": []}
    )
    with pytest.raises(citations.CitationRefused):
        citations.cite(actor, proposal_id=proposal.id, source_id=uuid4())


def test_a_citation_cannot_be_added_after_a_decision(actor, seed):
    transport = RecordingTransport()
    proposal, sources = _cited_plan(actor, seed.patient_a, transport)
    proposals.submit(proposal.id, actor)
    proposals.approve(proposal.id, actor)

    with pytest.raises(citations.CitationRefused):
        citations.cite(actor, proposal_id=proposal.id, source_id=sources[1].id)


def test_a_citation_is_immutable(actor, seed, owner):
    transport = RecordingTransport()
    proposal, sources = _cited_plan(actor, seed.patient_a, transport)

    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE proposal_citations SET locator = 'مُغيَّر' WHERE proposal_id = %s",
                (proposal.id,),
            )
    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute(
                "DELETE FROM proposal_citations WHERE proposal_id = %s", (proposal.id,)
            )


def test_citing_twice_is_safe(actor, seed):
    transport = RecordingTransport()
    proposal, sources = _cited_plan(actor, seed.patient_a, transport)
    again = citations.cite(actor, proposal_id=proposal.id, source_id=sources[0].id)

    assert again.source_id == sources[0].id
    assert len(citations.for_proposal(actor, proposal.id)) == 1


def test_the_reviewer_sees_the_evidence_beside_the_proposal(actor, seed):
    transport = RecordingTransport()
    proposal, sources = _cited_plan(actor, seed.patient_a, transport)

    listed = citations.for_proposal(actor, proposal.id)
    assert [item.external_id for item in listed] == [sources[0].external_id]
    assert listed[0].title.startswith("Exercise therapy after stroke")
    assert listed[0].url.endswith("/30000001/")


# ── «المسترجَع آلياً فقط» مفروض بالصلاحيات ──────────────────────────────
def test_a_practitioner_cannot_insert_a_source_by_hand(practitioner_conn, seed):
    """
    القرار المثبَّت: لا استشهاد يدوي. المنع صلاحية لا قاعدة سلوك — فدالة
    `record_retrieved_source` هي المسار الوحيد، ووحدة الاسترجاع وحدها تستدعيها.
    """
    from tests.conftest import set_actor

    set_actor(practitioner_conn, tenant_id=seed.tenant_a, actor_id=seed.practitioner_a)
    with practitioner_conn.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute(
                "INSERT INTO evidence_sources (source, external_id, title, url)"
                " VALUES ('PUBMED', '99999999', 'مصدر ملفَّق', 'https://example.test/')"
            )


def test_the_patient_role_cannot_read_evidence(patient_conn, seed):
    """المريض يرى المحتوى المعتمد، لا أدلّته ولا ما بُحث عنه لأجله."""
    from tests.conftest import set_actor

    set_actor(patient_conn, patient_id=seed.patient_a)
    for table in ("evidence_sources", "evidence_queries", "proposal_citations"):
        with patient_conn.cursor() as cursor:
            with pytest.raises(pg_errors.InsufficientPrivilege):
                cursor.execute(f"SELECT * FROM {table}")  # noqa: S608 - اسم من ثابت


# ── الجدولان لا ينحرفان ─────────────────────────────────────────────────
def test_evidence_required_kinds_match_the_python_source(owner):
    from core.types import EVIDENCE_REQUIRED_KINDS

    with owner.cursor() as cursor:
        cursor.execute("SELECT kind FROM evidence_required_kind")
        in_database = {row[0] for row in cursor.fetchall()}

    assert in_database == set(EVIDENCE_REQUIRED_KINDS)


# ── التحليل ─────────────────────────────────────────────────────────────
def test_parsing_keeps_what_the_practitioner_needs(actor):
    transport = RecordingTransport()
    sources = retrieval.search(actor, QUERY, transport=transport)

    first, second = sources
    assert first.title == "Exercise therapy after stroke: a systematic review"
    assert first.journal == "Journal of Rehabilitation Medicine"
    assert first.published_year == 2021
    assert first.doi == "10.1234/jrm.2021.0001"
    assert "BACKGROUND: Motor recovery" in first.abstract
    assert "Stroke Rehabilitation" in first.mesh

    # سنة من MedlineDate، ومقال بلا ملخّص ولا DOI يُخزَّن كما هو لا مُلفَّقاً
    assert second.published_year == 2019
    assert second.abstract is None
    assert second.doi is None
