"""
البوابتان عبر HTTP
===================
تُشغّل التطبيق الحقيقي وتتحقق من الضمانات كما يراها العميل: المصادقة مستقلة
لكل بوابة، والمحتوى غير المعتمد لا يظهر للمريض بأي مسار.
"""

from __future__ import annotations

import pytest

from uuid import uuid4

from core import db, escalation, identity
from tests.conftest import requires_db

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from api.app import create_app  # noqa: E402
from api.deps import auth_limiter  # noqa: E402

pytestmark = requires_db

PRACTITIONER_EMAIL = "practitioner.A@example.test"
PATIENT_EMAIL = "patient.a@example.test"
SECRET = "كلمة-مرور-قوية-جداً"


@pytest.fixture(autouse=True)
def _reset_state():
    auth_limiter.reset()
    yield
    auth_limiter.reset()
    db.shutdown()


@pytest.fixture
def accounts(owner, seed):
    """يضبط كلمة مرور الممارس ويُنشئ حساب مريض مرتبطاً بملفه."""
    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (identity.hash_password(SECRET), seed.practitioner_a),
        )
        cursor.execute(
            "INSERT INTO users (tenant_id, role, email, password_hash)"
            " VALUES (%s, 'PATIENT', %s, %s) RETURNING id",
            (seed.tenant_a, PATIENT_EMAIL, identity.hash_password(SECRET)),
        )
        patient_user = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE patients SET user_id = %s WHERE id = %s", (patient_user, seed.patient_a)
        )
    _PRACTITIONER_A[:] = [seed.practitioner_a, seed.tenant_a]
    return seed


#: (معرّف الممارس، معرّف مستأجره) — يملؤه `accounts`، ويستعمله `_create_plan`.
_PRACTITIONER_A: list = [None, None]


@pytest.fixture
def client(accounts):
    with TestClient(create_app()) as test_client:
        yield test_client


def _login(client, gate: str, email: str) -> str:
    response = client.post(f"/{gate}/login", json={"email": email, "password": SECRET})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── المصادقة المستقلة لكل بوابة ─────────────────────────────────────────
def test_health_needs_no_authentication(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_queue_requires_authentication(client):
    assert client.get("/practitioner/queue").status_code == 401


def test_patient_content_requires_authentication(client):
    assert client.get("/patient/plan").status_code == 401


def test_practitioner_token_does_not_open_the_patient_gate(client):
    token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    assert client.get("/patient/plan", headers=_auth(token)).status_code == 401


def test_patient_token_does_not_open_the_practitioner_gate(client):
    token = _login(client, "patient", PATIENT_EMAIL)
    assert client.get("/practitioner/queue", headers=_auth(token)).status_code == 401


def test_practitioner_cannot_log_in_through_the_patient_gate(client):
    response = client.post(
        "/patient/login", json={"email": PRACTITIONER_EMAIL, "password": SECRET}
    )
    assert response.status_code == 401


def test_wrong_password_is_rejected(client):
    response = client.post(
        "/practitioner/login", json={"email": PRACTITIONER_EMAIL, "password": "خطأ"}
    )
    assert response.status_code == 401


def test_logout_revokes_the_session(client):
    token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    assert client.post("/practitioner/logout", headers=_auth(token)).status_code == 204
    assert client.get("/practitioner/queue", headers=_auth(token)).status_code == 401


def test_login_is_rate_limited(client):
    """المصادقة نقطة نهاية مكلفة ومكشوفة — الحد مفروض عليها."""
    payloads = {"email": PRACTITIONER_EMAIL, "password": "خطأ"}
    statuses = [client.post("/practitioner/login", json=payloads).status_code for _ in range(12)]
    assert 429 in statuses, statuses
    assert statuses.index(429) >= 10, "الحد ضاق أكثر مما ينبغي"


# ── المسار الكامل ───────────────────────────────────────────────────────
def _create_plan(client, token, patient_id, *, tenant_id=None, author=None) -> str:
    """
    خطة جاهزة للتقديم: تُنشأ ويُستشهَد لها بمصدر مسترجَع.

    منذ القسم 3 لا تدخل خطة الطابور بلا استشهاد، فخطة بلا مصدر في الاختبار
    حالةٌ لا توجد في الإنتاج.
    """
    response = client.post(
        "/practitioner/proposals",
        headers=_auth(token),
        json={
            "patient_id": str(patient_id),
            "kind": "PLAN",
            "payload": {"home_program": "تمارين يومية"},
        },
    )
    assert response.status_code == 201, response.text
    proposal_id = response.json()["id"]

    from core.types import Actor
    from tests.conftest import cite_evidence_as

    cite_evidence_as(
        Actor(
            id=author or _PRACTITIONER_A[0],
            role="PRACTITIONER",
            tenant_id=tenant_id or _PRACTITIONER_A[1],
        ),
        proposal_id,
    )
    return proposal_id


def test_full_flow_from_draft_to_patient(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    proposal_id = _create_plan(client, practitioner_token, accounts.patient_a)

    # مسوّدة: لا شيء للمريض ولا شيء في الطابور
    assert client.get("/patient/plan", headers=_auth(patient_token)).json() is None
    assert client.get("/practitioner/queue", headers=_auth(practitioner_token)).json() == []

    # الطابور
    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token))
    queue = client.get("/practitioner/queue", headers=_auth(practitioner_token)).json()
    assert [item["id"] for item in queue] == [proposal_id]
    assert client.get("/patient/plan", headers=_auth(patient_token)).json() is None, (
        "محتوى في الطابور وصل المريض"
    )

    # الاعتماد
    approved = client.post(
        f"/practitioner/proposals/{proposal_id}/approve", headers=_auth(practitioner_token)
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    delivered = client.get("/patient/plan", headers=_auth(patient_token)).json()
    assert delivered["id"] == proposal_id
    assert delivered["content"]["home_program"] == "تمارين يومية"


def test_rejected_plan_never_reaches_the_patient(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    proposal_id = _create_plan(client, practitioner_token, accounts.patient_a)

    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token))
    rejected = client.post(
        f"/practitioner/proposals/{proposal_id}/reject",
        headers=_auth(practitioner_token),
        json={"reason": "الجرعة غير مناسبة للحالة"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["rejection_reason"] == "الجرعة غير مناسبة للحالة"
    assert client.get("/patient/plan", headers=_auth(patient_token)).json() is None


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "   "}])
def test_rejection_without_reason_is_refused_by_the_contract(client, accounts, body):
    token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    proposal_id = _create_plan(client, token, accounts.patient_a)
    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(token))

    response = client.post(
        f"/practitioner/proposals/{proposal_id}/reject", headers=_auth(token), json=body
    )
    assert response.status_code == 422


def test_edit_and_approve_delivers_the_edited_version(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    proposal_id = _create_plan(client, practitioner_token, accounts.patient_a)
    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token))

    response = client.post(
        f"/practitioner/proposals/{proposal_id}/edit-and-approve",
        headers=_auth(practitioner_token),
        json={"payload": {"home_program": "نسخة المراجِع"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "EDITED_APPROVED"
    assert response.json()["version"] == 2

    delivered = client.get("/patient/plan", headers=_auth(patient_token)).json()
    assert delivered["content"]["home_program"] == "نسخة المراجِع"


def test_approving_twice_conflicts(client, accounts):
    token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    proposal_id = _create_plan(client, token, accounts.patient_a)
    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(token))
    client.post(f"/practitioner/proposals/{proposal_id}/approve", headers=_auth(token))

    again = client.post(f"/practitioner/proposals/{proposal_id}/approve", headers=_auth(token))
    assert again.status_code == 409


def test_illustration_without_side_is_refused(client, accounts):
    """القاعدة 4 عبر الـAPI: لا محتوى مصوَّر بلا جانب مصاب."""
    token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    response = client.post(
        "/practitioner/proposals",
        headers=_auth(token),
        json={
            "patient_id": str(accounts.patient_a),
            "kind": "ILLUSTRATION_SET",
            "payload": {"svg": "<svg/>"},
        },
    )
    assert response.status_code >= 400


def test_patient_response_hides_review_state(client, accounts):
    """المريض لا يرى الحالة ولا المراجِع ولا سبب الرفض — لا شيء من ذلك يخصه."""
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    proposal_id = _create_plan(client, practitioner_token, accounts.patient_a)
    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token))
    client.post(f"/practitioner/proposals/{proposal_id}/approve", headers=_auth(practitioner_token))

    delivered = client.get("/patient/plan", headers=_auth(patient_token)).json()
    for leaked in ("status", "reviewer_id", "rejection_reason", "priority", "queued_at"):
        assert leaked not in delivered, f"تسرّب حقل مراجعة إلى المريض: {leaked}"


# ── أداء المريض والتصعيد عبر البوابتين ──────────────────────────────────
def _approved_plan(client, practitioner_token, patient_id) -> str:
    proposal_id = _create_plan(client, practitioner_token, patient_id)
    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token))
    client.post(f"/practitioner/proposals/{proposal_id}/approve", headers=_auth(practitioner_token))
    return proposal_id


def test_patient_records_a_session_and_sees_it_in_progress(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    plan_id = _approved_plan(client, practitioner_token, accounts.patient_a)

    before = client.get("/patient/progress", headers=_auth(patient_token)).json()
    assert before["done_today"] is False and before["adherent_days"] == 0

    response = client.post(
        "/patient/sessions",
        headers=_auth(patient_token),
        json={"plan_id": plan_id, "outcome": "DONE", "client_uuid": str(uuid4()),
              "difficulty": 4, "pain": 2},
    )
    assert response.status_code == 201, response.text

    after = client.get("/patient/progress", headers=_auth(patient_token)).json()
    assert after["done_today"] is True
    assert after["adherent_days"] == 1
    assert len(after["days"]) == after["total_days"], "الأيام الخالية غائبة عن المقام"


def test_resending_a_session_is_idempotent_over_http(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    plan_id = _approved_plan(client, practitioner_token, accounts.patient_a)

    body = {"plan_id": plan_id, "outcome": "PARTIAL", "client_uuid": str(uuid4())}
    first = client.post("/patient/sessions", headers=_auth(patient_token), json=body)
    second = client.post("/patient/sessions", headers=_auth(patient_token), json=body)

    assert first.json()["id"] == second.json()["id"]
    progress = client.get("/patient/progress?days=2", headers=_auth(patient_token)).json()
    assert sum(day["sessions"] for day in progress["days"]) == 1


def test_a_session_on_an_unapproved_plan_is_refused_over_http(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    draft_id = _create_plan(client, practitioner_token, accounts.patient_a)

    response = client.post(
        "/patient/sessions",
        headers=_auth(patient_token),
        json={"plan_id": draft_id, "outcome": "DONE", "client_uuid": str(uuid4())},
    )
    assert response.status_code == 409


def test_red_flag_reaches_the_practitioner_and_returns_only_an_acknowledgement(
    client, accounts
):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)

    response = client.post(
        "/patient/red-flag",
        headers=_auth(patient_token),
        json={"body": "هل هذا الألم في صدري طبيعي؟"},
    )
    assert response.status_code == 201
    payload = response.json()

    # تأكيد استلام فقط: لا تقييم ولا طمأنة ولا حقل سريري
    assert payload["acknowledgement"] == escalation.ACKNOWLEDGEMENT
    assert set(payload) == {"id", "reported_at", "acknowledgement"}
    assert "طبيعي" not in payload["acknowledgement"]

    queue = client.get("/practitioner/red-flags", headers=_auth(practitioner_token)).json()
    assert [item["id"] for item in queue] == [payload["id"]]
    assert queue[0]["reported_at"] is not None


def test_acknowledging_a_red_flag_records_escalation_time(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    flag_id = client.post(
        "/patient/red-flag", headers=_auth(patient_token), json={"body": "دوخة"}
    ).json()["id"]

    acknowledged = client.post(
        f"/practitioner/red-flags/{flag_id}/acknowledge",
        headers=_auth(practitioner_token), json={"note": "اتُّصل بالمريض"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["escalation_seconds"] is not None

    again = client.post(
        f"/practitioner/red-flags/{flag_id}/acknowledge",
        headers=_auth(practitioner_token), json={},
    )
    assert again.status_code == 409


@pytest.mark.parametrize("body", [{}, {"body": ""}, {"body": "   "}])
def test_an_empty_red_flag_is_refused_by_the_contract(client, accounts, body):
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    response = client.post("/patient/red-flag", headers=_auth(patient_token), json=body)
    assert response.status_code == 422


def test_the_patient_gate_exposes_no_review_state_for_red_flags(client, accounts):
    """المريض لا يعرف من استلم بلاغه ولا متى — يعرف أنه وصل."""
    patient_token = _login(client, "patient", PATIENT_EMAIL)
    payload = client.post(
        "/patient/red-flag", headers=_auth(patient_token), json={"body": "ألم"}
    ).json()
    for leaked in ("acknowledged_at", "acknowledged_by", "escalation_seconds", "patient_id"):
        assert leaked not in payload


# ── المرافق عبر HTTP ────────────────────────────────────────────────────
CAREGIVER_EMAIL = "caregiver.http@example.test"
CONSENT = "أوافق على أن يطّلع مرافقي على خطتي وأن يسجّل أدائي نيابةً عني."


@pytest.fixture
def caregiver_user(owner, accounts):
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (tenant_id, role, email, password_hash)"
            " VALUES (%s, 'CAREGIVER', %s, %s) RETURNING id",
            (accounts.tenant_a, CAREGIVER_EMAIL, identity.hash_password(SECRET)),
        )
        return cursor.fetchone()[0]


def _grant(client, token, patient_id, caregiver_user_id, **overrides):
    body = {
        "caregiver_user_id": str(caregiver_user_id),
        "relationship": "زوجة المريض",
        "consent_text": CONSENT,
        "consent_given_by": "PATIENT",
    }
    body.update(overrides)
    return client.post(
        f"/practitioner/patients/{patient_id}/caregivers", headers=_auth(token), json=body
    )


def test_a_caregiver_without_consent_is_refused_by_the_patient_gate(
    client, accounts, caregiver_user
):
    """يدخل البوابة ولا يجد مريضاً: لا محتوى، ولا تسريب لوجود مريض أصلاً."""
    token = _login(client, "patient", CAREGIVER_EMAIL)
    assert client.get("/patient/plan", headers=_auth(token)).status_code == 403
    assert client.get("/patient/session", headers=_auth(token)).status_code == 403


def test_consent_opens_the_patient_gate_for_the_caregiver(
    client, accounts, caregiver_user
):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    granted = _grant(client, practitioner_token, accounts.patient_a, caregiver_user)
    assert granted.status_code == 201, granted.text
    assert granted.json()["consent_text"] == CONSENT

    caregiver_token = _login(client, "patient", CAREGIVER_EMAIL)
    session = client.get("/patient/session", headers=_auth(caregiver_token))
    assert session.status_code == 200
    assert session.json() == {"acting_as": "CAREGIVER"}


def test_the_patient_sees_their_own_capacity(client, accounts):
    token = _login(client, "patient", PATIENT_EMAIL)
    assert client.get("/patient/session", headers=_auth(token)).json() == {
        "acting_as": "PATIENT"
    }


def test_a_grant_without_consent_text_is_refused_by_the_contract(
    client, accounts, caregiver_user
):
    """لا منح بلا نصّ موافقة — يُرفض في العقد قبل أن يبلغ قاعدة البيانات."""
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    for bad in ({"consent_text": ""}, {"consent_text": "   "}, {"relationship": " "}):
        response = _grant(
            client, practitioner_token, accounts.patient_a, caregiver_user, **bad
        )
        assert response.status_code == 422, response.text


def test_revoking_consent_closes_the_caregivers_open_session(
    client, accounts, caregiver_user
):
    """الرمز الذي كان يعمل قبل السحب يتوقف بعده — لا ينتظر انتهاء صلاحيته."""
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    link_id = _grant(
        client, practitioner_token, accounts.patient_a, caregiver_user
    ).json()["id"]

    caregiver_token = _login(client, "patient", CAREGIVER_EMAIL)
    assert client.get("/patient/plan", headers=_auth(caregiver_token)).status_code == 200

    revoked = client.post(
        f"/practitioner/caregivers/{link_id}/revoke", headers=_auth(practitioner_token)
    )
    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False

    assert client.get("/patient/plan", headers=_auth(caregiver_token)).status_code == 401


def test_a_practitioner_of_another_tenant_sees_no_consent_rows(
    client, accounts, caregiver_user, owner
):
    """عزل المستأجر يشمل سجل الموافقات: لا قراءة عبر الحدود."""
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    _grant(client, practitioner_token, accounts.patient_a, caregiver_user)

    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (identity.hash_password(SECRET), accounts.practitioner_b),
        )
    other_token = _login(client, "practitioner", "practitioner.B@example.test")
    listed = client.get(
        f"/practitioner/patients/{accounts.patient_a}/caregivers",
        headers=_auth(other_token),
    )
    assert listed.status_code == 200
    assert listed.json() == []


def test_no_bulk_caregiver_endpoint(client):
    """لا منح ولا سحب بالجملة: كل موافقة قرار مستقل بمعرّف في المسار."""
    from api.app import create_app as _create_app

    for path, methods in _create_app().openapi()["paths"].items():
        if "caregiver" not in path:
            continue
        for method, operation in methods.items():
            if method not in {"post", "patch", "put"}:
                continue
            schema = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            assert schema.get("type") != "array", (path, method)


# ── مهام النشاط اليومي عبر البوابتين ────────────────────────────────────
def _authorize(client, token, patient_id, tier, basis="تقييم موثَّق"):
    return client.post(
        "/practitioner/kitchen/authorizations",
        headers=_auth(token),
        json={"patient_id": str(patient_id), "tier": tier, "basis": basis},
    )


def _cite(client, token, proposal_id) -> None:
    """استشهاد بمصدر مسترجَع — نفس ما يفعله `_create_plan` بعد الإنشاء."""
    from core.types import Actor
    from tests.conftest import cite_evidence_as

    cite_evidence_as(
        Actor(id=_PRACTITIONER_A[0], role="PRACTITIONER", tenant_id=_PRACTITIONER_A[1]),
        proposal_id,
    )


def _task_tiers(client, patient_token) -> set[int]:
    response = client.get("/patient/adl/tasks", headers=_auth(patient_token))
    assert response.status_code == 200, response.text
    return {task["tier"] for task in response.json() if task["module"] == "KITCHEN"}


def test_the_patient_endpoint_returns_no_unauthorized_tier(client, accounts):
    """معيار القبول 5 عبر HTTP: نقطة النهاية لا تُرجع ما لم يُفوَّض."""
    patient_token = _login(client, "patient", PATIENT_EMAIL)

    tasks = client.get("/patient/adl/tasks", headers=_auth(patient_token)).json()
    assert tasks, "شاشة فارغة تماماً تجعل الفحص بلا معنى"
    assert all(task["module"] == "DRESSING" for task in tasks), "مهمة مطبخ بلا تفويض"


def test_authorizing_opens_exactly_one_tier_over_http(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)

    created = _authorize(client, practitioner_token, accounts.patient_a, 2)
    assert created.status_code == 201, created.text
    assert created.json()["tier"] == 2

    assert _task_tiers(client, patient_token) == {2}


def test_revoking_closes_the_tier_over_http(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)

    grant = _authorize(client, practitioner_token, accounts.patient_a, 3).json()
    assert _task_tiers(client, patient_token) == {3}

    revoked = client.delete(
        f"/practitioner/kitchen/authorizations/{grant['id']}",
        headers=_auth(practitioner_token),
    )
    assert revoked.status_code == 200, revoked.text
    assert _task_tiers(client, patient_token) == set()


def test_a_red_flag_suspends_the_heat_tier_over_http(client, accounts):
    """
    المسار الكامل كما يعيشه المريض: يفتح المستوى، يبلّغ، فيختفي.

    ولا كتابة في الطريق: التفويض يبقى في السرد، والاستلام يعيد المهمة.
    """
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)

    _authorize(client, practitioner_token, accounts.patient_a, 1)
    _authorize(client, practitioner_token, accounts.patient_a, 3)
    assert _task_tiers(client, patient_token) == {1, 3}

    flag = client.post(
        "/patient/red-flag", headers=_auth(patient_token), json={"body": "دوار عند الوقوف"}
    ).json()
    assert _task_tiers(client, patient_token) == {1}, "الحرارة لم تُعلَّق بعد البلاغ"

    listed = client.get(
        f"/practitioner/patients/{accounts.patient_a}/kitchen/authorizations",
        headers=_auth(practitioner_token),
    ).json()
    assert {grant["tier"] for grant in listed} == {1, 3}, "التعليق سحب تفويضاً"

    client.post(
        f"/practitioner/red-flags/{flag['id']}/acknowledge", headers=_auth(practitioner_token)
    )
    assert _task_tiers(client, patient_token) == {1, 3}, "الاستلام لم يرفع التعليق"


def test_an_authorization_without_a_basis_is_refused_by_the_contract(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    response = _authorize(client, practitioner_token, accounts.patient_a, 1, basis="   ")
    assert response.status_code == 422, response.text


def test_no_bulk_authorization_endpoint(client):
    """مستوىً واحد لكل طلب، كقرارات المراجعة: لا مصفوفة مستويات."""
    paths = create_app().openapi()["paths"]
    assert "/practitioner/kitchen/authorizations" in paths
    assert not [path for path in paths if path.endswith("/authorizations:bulk")]


def test_a_dressing_program_is_verified_then_delivered_over_http(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)

    created = client.post(
        "/practitioner/proposals",
        headers=_auth(practitioner_token),
        json={
            "patient_id": str(accounts.patient_a),
            "kind": "PLAN",
            "payload": {
                "module": "DRESSING",
                "steps": [
                    {"action": "DON", "side": "AFFECTED", "garment": "قميص"},
                    {"action": "DON", "side": "SOUND", "garment": "قميص"},
                ],
            },
        },
    )
    assert created.status_code == 201, created.text
    proposal_id = created.json()["id"]
    _cite(client, practitioner_token, proposal_id)

    # بلا فحص: لا يدخل الطابور
    blocked = client.post(
        f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token)
    )
    assert blocked.status_code == 409, blocked.text

    verified = client.post(
        f"/practitioner/proposals/{proposal_id}/verify-dressing",
        headers=_auth(practitioner_token),
    )
    assert verified.status_code == 200, verified.text
    assert [step["side"] for step in verified.json()] == ["AFFECTED", "SOUND"]

    client.post(f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token))
    client.post(f"/practitioner/proposals/{proposal_id}/approve", headers=_auth(practitioner_token))

    delivered = client.get("/patient/plan", headers=_auth(patient_token)).json()
    assert delivered["content"]["module"] == "DRESSING"


def test_a_wrong_order_program_is_refused_over_http(client, accounts):
    practitioner_token = _login(client, "practitioner", PRACTITIONER_EMAIL)
    patient_token = _login(client, "patient", PATIENT_EMAIL)

    created = client.post(
        "/practitioner/proposals",
        headers=_auth(practitioner_token),
        json={
            "patient_id": str(accounts.patient_a),
            "kind": "PLAN",
            "payload": {
                "module": "DRESSING",
                "steps": [
                    {"action": "DON", "side": "SOUND", "garment": "قميص"},
                    {"action": "DON", "side": "AFFECTED", "garment": "قميص"},
                ],
            },
        },
    )
    proposal_id = created.json()["id"]
    _cite(client, practitioner_token, proposal_id)

    verdict = client.post(
        f"/practitioner/proposals/{proposal_id}/verify-dressing",
        headers=_auth(practitioner_token),
    )
    assert verdict.status_code == 409, verdict.text
    assert "المصاب" in verdict.json()["detail"]

    assert client.post(
        f"/practitioner/proposals/{proposal_id}/submit", headers=_auth(practitioner_token)
    ).status_code == 409
    assert client.get("/patient/plan", headers=_auth(patient_token)).json() is None
