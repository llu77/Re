"""
تفويض مستويات المطبخ — جانب الممارس
=====================================
المستوى يُفتح بقرار ممارس مرخَّص مسمّى، وبأساسٍ سريري مكتوب. لا شيء في هذه
الوحدة يفوّض تلقائياً، ولا دالةَ «فوّض المستوى التالي عند إتقان السابق»: تلك
قرارٌ، والنظام يقترح ولا يقرر.

**ما يراه المريض ليس هنا.** المهام المفتوحة تُقرأ من
`core.delivery.list_adl_tasks` وحدها، كما يُقرأ المحتوى المعتمد: عرضٌ واحد
في قاعدة البيانات يقرّر ما يُفتح. ولا مسار يقرأ به دورُ المريض جدولَ
التفويض — لا يملك عليه صلاحية أصلاً.

**لا تسلسل مفروض** بين المستويات، وهذا قرار معلَن: تفويض المستوى 4 بلا 1-3
ممكن. التسلسل حكمٌ سريري يسجّله الممارس في `basis`، لا قيدٌ تقني يلتفّ عليه
بتفويضات صورية.
"""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from psycopg import errors as pg_errors

from core import db
from core.adl.types import KITCHEN_TIERS, KitchenAuthorization
from core.types import Actor

__all__ = [
    "AuthorizationNotFound",
    "AuthorizationRefused",
    "authorize",
    "for_patient",
    "revoke",
]

#: المستويات المعروفة. الفحص هنا يسبق قيد المفتاح الخارجي ليعطي رسالة
#: تقول «من 1 إلى 4» بدل خطأ مفتاح خارجي لا يقول شيئاً.
_KNOWN_TIERS: frozenset[int] = frozenset(tier.tier for tier in KITCHEN_TIERS)

_COLUMNS = (
    "id, tenant_id, patient_id, tier, basis, granted_by, granted_at,"
    " revoked_at, revoked_by"
)

_INSERT = (
    "INSERT INTO kitchen_authorization (tenant_id, patient_id, tier, basis, granted_by)"
    " VALUES (%s, %s, %s, %s, %s) RETURNING " + _COLUMNS
)

_REVOKE = (
    "UPDATE kitchen_authorization SET revoked_at = now(), revoked_by = %s"
    " WHERE id = %s AND revoked_at IS NULL RETURNING " + _COLUMNS
)

_BY_PATIENT_ACTIVE = (
    "SELECT " + _COLUMNS + " FROM kitchen_authorization"
    " WHERE patient_id = %s AND revoked_at IS NULL ORDER BY tier"
)

_BY_PATIENT_ALL = (
    "SELECT " + _COLUMNS + " FROM kitchen_authorization"
    " WHERE patient_id = %s ORDER BY tier, granted_at"
)


class AuthorizationNotFound(LookupError):
    """لا تفويض بهذا المعرّف في نطاقك، أو هو مسحوب — لا نميّز بينهما."""


class AuthorizationRefused(Exception):
    """
    المخطط رفض التفويض: مستأجر مختلف، أو مانح غير ممارس، أو تفويض فاعل قائم.

    الترجمة هنا لا في طبقة الـAPI، على نسق `citations.CitationRefused`:
    فتبقى الواجهة بلا أنواع أخطاء قاعدة البيانات، ولا تُمسَك الأخطاء غير
    المتوقَّعة بـ`except Exception` واسعة تُخفي عيباً حقيقياً خلف 409.

    السبب الأصلي محفوظ في `__cause__` — فالقاعدة تبقى هي الحَكَم المرئي.
    """


def authorize(
    actor: Actor, *, patient_id: UUID, tier: int, basis: str
) -> KitchenAuthorization:
    """
    يفوّض مستوىً واحداً لمريض واحد بأساسه.

    الفحوص هنا تسبق قاعدة البيانات لتعطي رسالة مفهومة، ولا تحلّ محلّها:
    القيود والمحفّزات هي الحَكَم — دورُ المانح، ووحدة المستأجر، ومنعُ تفويض
    ثانٍ فاعل للمستوى نفسه.
    """
    if tier not in _KNOWN_TIERS:
        raise ValueError(f"مستوى غير معروف: {tier} — المسموح {sorted(_KNOWN_TIERS)}")
    if not basis or not basis.strip():
        raise ValueError("التفويض يتطلب أساساً سريرياً مكتوباً")

    try:
        with db.session(
            "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
        ) as cursor:
            cursor.execute(
                _INSERT, (actor.tenant_id, patient_id, tier, basis.strip(), actor.id)
            )
            return _to_authorization(cursor.fetchone())
    except (
        pg_errors.CheckViolation,
        pg_errors.ForeignKeyViolation,
        pg_errors.UniqueViolation,
        pg_errors.InsufficientPrivilege,
    ) as exc:
        raise AuthorizationRefused(str(exc).strip()) from exc


def revoke(actor: Actor, authorization_id: UUID) -> KitchenAuthorization:
    """
    يسحب تفويضاً. السحب نهائي: صفٌّ مسحوب لا يُعاد تفعيله.

    الأثر فوري بلا حاجة إلى شيء آخر — العرض يقرأ `revoked_at IS NULL` عند كل
    طلب، فالمهمة تختفي في الطلب التالي.
    """
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_REVOKE, (actor.id, authorization_id))
        row = cursor.fetchone()
    if row is None:
        raise AuthorizationNotFound(str(authorization_id))
    return _to_authorization(row)


def for_patient(
    actor: Actor, patient_id: UUID, *, include_revoked: bool = False
) -> Sequence[KitchenAuthorization]:
    """تفويضات المريض كما يراها الممارس. المسحوبة تُطلب صراحةً لا تُخفى صمتاً."""
    query = _BY_PATIENT_ALL if include_revoked else _BY_PATIENT_ACTIVE
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(query, (patient_id,))
        rows = cursor.fetchall()
    return [_to_authorization(row) for row in rows]


def _to_authorization(row) -> KitchenAuthorization:
    return KitchenAuthorization(
        id=row["id"],
        tenant_id=row["tenant_id"],
        patient_id=row["patient_id"],
        tier=row["tier"],
        basis=row["basis"],
        granted_by=row["granted_by"],
        granted_at=row["granted_at"],
        revoked_at=row["revoked_at"],
        revoked_by=row["revoked_by"],
    )
