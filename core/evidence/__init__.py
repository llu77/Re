"""
طبقة الأدلة — استرجاع موثَّق واستشهاد قابل للتحقق.

الوحدة الوحيدة في المستودع التي تتصل بالشبكة هي `core.evidence.transport`،
واختبار معماري يفشل إن استورد أي ملف آخر `requests` أو `urllib` أو `httpx`.
"""

from core.evidence.types import (
    EvidenceQuery,
    EvidenceSourceKind,
    NoEvidence,
    RetrievedSource,
    UnknownTerm,
)

__all__ = [
    "EvidenceQuery",
    "EvidenceSourceKind",
    "NoEvidence",
    "RetrievedSource",
    "UnknownTerm",
]
