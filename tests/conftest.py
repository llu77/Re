"""
تجهيزات اختبارات قاعدة البيانات
================================
بيئة التطوير هنا بلا Docker، فلا testcontainers. الاختبارات تعمل مقابل عنقود
محلي (`scripts/dev_db.sh start`) أو مقابل خدمة `postgres` في CI — كلاهما عبر
`SYMBOL_DATABASE_URL`.

الاختبارات التي لا تلمس القاعدة (اختبارات القسم 0 والاختبارات المعمارية) لا
تعتمد على أي مما هنا وتعمل بلا قاعدة بيانات.
"""

from __future__ import annotations

import os
from uuid import UUID

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg غير مثبّت")

DATABASE_URL = os.environ.get("SYMBOL_DATABASE_URL")

#: كلمات مرور التطوير كما ينشئها الترحيل 0001. في الإنتاج تُدار خارجه.
ROLE_PASSWORDS = {
    "app_practitioner": os.environ.get("SYMBOL_PRACTITIONER_PASSWORD", "dev_practitioner"),
    "app_patient": os.environ.get("SYMBOL_PATIENT_PASSWORD", "dev_patient"),
}

requires_db = pytest.mark.skipif(
    not DATABASE_URL, reason="SYMBOL_DATABASE_URL غير مضبوط"
)


def _url_for_role(role: str) -> str:
    """نفس القاعدة بدور مختلف — هكذا نختبر الصلاحيات كما تعمل في الإنتاج."""
    parsed = psycopg.conninfo.conninfo_to_dict(DATABASE_URL)
    parsed.update(user=role, password=ROLE_PASSWORDS[role])
    return psycopg.conninfo.make_conninfo(**parsed)


@pytest.fixture(scope="session")
def database_url() -> str:
    if not DATABASE_URL:
        pytest.skip("SYMBOL_DATABASE_URL غير مضبوط")
    return DATABASE_URL


@pytest.fixture(scope="session", autouse=True)
def _role_passwords_in_env():
    """
    `core.db` يقرأ كلمات مرور الأدوار من البيئة ولا يحمل قيماً افتراضية —
    قيمة افتراضية صامتة في الإنتاج خطر. تُزوَّد هنا للاختبار فقط.
    """
    os.environ.setdefault("SYMBOL_PRACTITIONER_PASSWORD", ROLE_PASSWORDS["app_practitioner"])
    os.environ.setdefault("SYMBOL_PATIENT_PASSWORD", ROLE_PASSWORDS["app_patient"])


@pytest.fixture(scope="session", autouse=True)
def _schema_is_migrated():
    """
    يفشل بوضوح بدل أن تتساقط الاختبارات بأخطاء غامضة.

    يتجاوز بلا قاعدة بيانات بدل أن يُسقط الجلسة: الاختبارات المعمارية تقرأ
    الشيفرة ولا تحتاج قاعدة، ويجب أن تعمل في أي بيئة.
    """
    if not DATABASE_URL:
        return
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.proposals')")
        if cursor.fetchone()[0] is None:
            pytest.fail(
                "المخطط غير مُرحَّل. شغّل: python -m migrations.run up",
                pytrace=False,
            )


@pytest.fixture
def owner(database_url):
    """اتصال المالك — يُستخدم للتهيئة ولاختبار أن FORCE RLS يشمله."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


@pytest.fixture(autouse=True)
def _clean_tables():
    """
    قاعدة نظيفة قبل كل اختبار.

    يفتح اتصاله بنفسه بدل الاعتماد على تجهيزة `owner`: الاعتماد عليها كان
    يجرّ كل اختبار — حتى ما لا يلمس القاعدة — إلى التخطّي عند غيابها.
    """
    if not DATABASE_URL:
        yield
        return
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE proposals, proposal_versions, patients, sessions, users, tenants,"
                " audit_log RESTART IDENTITY CASCADE"
            )
    yield


@pytest.fixture
def practitioner_conn(database_url):
    with psycopg.connect(_url_for_role("app_practitioner"), autocommit=True) as connection:
        yield connection


@pytest.fixture
def patient_conn(database_url):
    with psycopg.connect(_url_for_role("app_patient"), autocommit=True) as connection:
        yield connection


class Seed:
    """بيانات أساسية: مستأجران، ممارس لكل منهما، ومريض لكل منهما."""

    def __init__(self, tenant_a, tenant_b, practitioner_a, practitioner_b, patient_a, patient_b):
        self.tenant_a: UUID = tenant_a
        self.tenant_b: UUID = tenant_b
        self.practitioner_a: UUID = practitioner_a
        self.practitioner_b: UUID = practitioner_b
        self.patient_a: UUID = patient_a
        self.patient_b: UUID = patient_b


@pytest.fixture
def seed(owner) -> Seed:
    with owner.cursor() as cursor:
        ids = []
        for label, file_number in (("A", 1), ("B", 2)):
            cursor.execute("INSERT INTO tenants (name) VALUES (%s) RETURNING id", (f"عيادة {label}",))
            tenant = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO users (tenant_id, role, email, password_hash, license_number)"
                " VALUES (%s, 'PRACTITIONER', %s, 'x', %s) RETURNING id",
                (tenant, f"practitioner.{label}@example.test", f"LIC-{label}"),
            )
            practitioner = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO patients (tenant_id, file_number, display_name)"
                " VALUES (%s, %s, %s) RETURNING id",
                (tenant, file_number, f"مريض {label}"),
            )
            ids.append((tenant, practitioner, cursor.fetchone()[0]))

    (tenant_a, prac_a, pat_a), (tenant_b, prac_b, pat_b) = ids
    return Seed(tenant_a, tenant_b, prac_a, prac_b, pat_a, pat_b)


def set_actor(connection, *, tenant_id=None, actor_id=None, patient_id=None) -> None:
    """
    يضبط سياق الجلسة الذي تقرؤه سياسات RLS ونقطة العبور.

    في الإنتاج تضبطه الـAPI من الجلسة الموثَّقة، لا العميل.
    """
    with connection.cursor() as cursor:
        for key, value in (
            ("app.tenant_id", tenant_id),
            ("app.actor_id", actor_id),
            ("app.patient_id", patient_id),
        ):
            if value is not None:
                cursor.execute("SELECT set_config(%s, %s, false)", (key, str(value)))
