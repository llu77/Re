"""The redaction patterns the spec proposes (eyework/redact.py), run on the cases its tests name."""

import re
import unicodedata

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
EMAIL = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+")
URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
IBAN = re.compile(r"\bSA\s?\d{2}(?:\s?[0-9A-Z]{4}){5}\b", re.IGNORECASE)
# Nine or more digits, with at most one space or hyphen between any two: phones (05xxxxxxxx,
# +9665xxxxxxxx), national and iqama numbers (10 digits), card numbers, account numbers.
LONG_NUMBER = re.compile(r"\+?\d(?:[ -]?\d){8,}")


def redact(text: str, names: tuple[str, ...] = ()) -> tuple[str, int]:
    """(text with third-party contact data masked, number of masks). Digits are compared after
    mapping Arabic-Indic digits to ASCII, and replaced in the original text by position."""
    text = unicodedata.normalize("NFC", text)
    probe = text.translate(_DIGITS)
    spans: list[tuple[int, int, str]] = []
    for pattern, mask in ((EMAIL, "[بريد]"), (URL, "[رابط]"), (IBAN, "[حساب]"), (LONG_NUMBER, "[رقم]")):
        for m in pattern.finditer(probe):
            if not any(s < m.end() and m.start() < e for s, e, _ in spans):
                spans.append((m.start(), m.end(), mask))
    for name in names:
        for m in re.finditer(re.escape(name), text):
            if not any(s < m.end() and m.start() < e for s, e, _ in spans):
                spans.append((m.start(), m.end(), "العميل"))
    out = text
    for s, e, mask in sorted(spans, reverse=True):
        out = out[:s] + mask + out[e:]
    return out, len(spans)


CASES = [
    ("جوالي 0551234567 والبديل ٠٥٥١٢٣٤٥٦٧", 2),
    ("اتصل على +966 55 123 4567", 1),
    ("رقم الهوية 1012345678", 1),
    ("الآيبان SA03 8000 0000 6080 1016 7519", 1),
    ("البطاقة 4111-1111-1111-1111", 1),
    ("راسلني a.b@example.com", 1),
    ("الرابط https://x.example/reset?token=abc", 1),
    ("السعر 1250.50 ريال والكمية 400 والطلب 1234567", 0),
    ("التاريخ 2026-10-09 الساعة 10:30", 0),
    ("أنا أحمد العتيبي ولم يصلني الطلب", 1),
]
ok = True
for text, expected in CASES:
    out, n = redact(text, names=("أحمد العتيبي",))
    good = n == expected
    ok &= good
    print(("PASS " if good else "FAIL ") + f"{n} mask(s): {text!r} -> {out!r}")
print("all redaction cases pass" if ok else "REDACTION FAILURES")
