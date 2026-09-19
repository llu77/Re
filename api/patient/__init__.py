"""
بوابة المريض.

تقرأ المحتوى السريري عبر `core.delivery` حصراً. لا تستورد `core.db` ولا
`core.proposals` — اختبار معماري يفشل إن فعلت.
"""

from api.patient.routes import router

__all__ = ["router"]
