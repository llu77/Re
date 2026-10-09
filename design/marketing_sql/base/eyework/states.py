"""
آلة حالات الحملة
================
نظيرُ جدول `campaign_transition` في القاعدة. المحفّز يقرأ الجدول ويرمي
استثناءً على أيّ انتقالٍ غيره؛ وهذه النسخة للعرض وللواجهة وحدهما، واختبارٌ
يقارن الاثنين فلا يفترقان.

    DRAFT ──نسخة أولى──▶ COPY_PROPOSED ──موافقة──▶ COPY_APPROVED ──تأكيد──▶ READY
                           ▲   │ (نسخة جديدة تبقى فيها)  │
                           └───┴──────تراجع عن الموافقة──┘
    وكلّها ──إلغاء──▶ CANCELLED (نهائية)

READY لا تتغيّر إلا إلى CANCELLED، وCANCELLED لا تتغيّر أبداً.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ALLOWED_TRANSITIONS", "FINAL", "OPEN", "Status"]


class Status(str, Enum):
    DRAFT = "DRAFT"
    COPY_PROPOSED = "COPY_PROPOSED"
    COPY_APPROVED = "COPY_APPROVED"
    READY = "READY"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: frozenset[tuple[Status, Status]] = frozenset({
    (Status.DRAFT, Status.COPY_PROPOSED),
    (Status.COPY_PROPOSED, Status.COPY_APPROVED),
    (Status.COPY_APPROVED, Status.COPY_PROPOSED),
    (Status.COPY_APPROVED, Status.READY),
    (Status.DRAFT, Status.CANCELLED),
    (Status.COPY_PROPOSED, Status.CANCELLED),
    (Status.COPY_APPROVED, Status.CANCELLED),
    (Status.READY, Status.CANCELLED),
})

#: حملةٌ لم تنتهِ — تُحسب في سقف الحملات المفتوحة.
OPEN = frozenset({Status.DRAFT, Status.COPY_PROPOSED, Status.COPY_APPROVED})
FINAL = frozenset({Status.READY, Status.CANCELLED})
