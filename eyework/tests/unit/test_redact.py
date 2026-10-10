"""
إخفاء بيانات الغير
==================
الحالات العشر من شواهد المواصفة (§13) كما هي، ثم ما يزيد عليها: أرقامٌ مختلطة،
وهاتفٌ داخل كلمة، وآيبان بلا مسافات، واسمٌ يتكرّر، ورابطٌ تحيط به العربية.
"""

from __future__ import annotations

import pytest

from eyework.redact import redact

EVIDENCE = [
    ("جوالي 0551234567 والبديل ٠٥٥١٢٣٤٥٦٧", "جوالي [رقم] والبديل [رقم]", 2),
    ("اتصل على +966 55 123 4567", "اتصل على [رقم]", 1),
    ("رقم الهوية 1012345678", "رقم الهوية [رقم]", 1),
    ("الآيبان SA03 8000 0000 6080 1016 7519", "الآيبان [حساب]", 1),
    ("البطاقة 4111-1111-1111-1111", "البطاقة [رقم]", 1),
    ("راسلني a.b@example.com", "راسلني [بريد]", 1),
    ("الرابط https://x.example/reset?token=abc", "الرابط [رابط]", 1),
    ("السعر 1250.50 ريال والكمية 400 والطلب 1234567", "السعر 1250.50 ريال والكمية 400 والطلب 1234567", 0),
    ("التاريخ 2026-10-09 الساعة 10:30", "التاريخ 2026-10-09 الساعة 10:30", 0),
    ("أنا أحمد العتيبي ولم يصلني الطلب", "أنا العميل ولم يصلني الطلب", 1),
]


@pytest.mark.parametrize(("text", "expected", "masks"), EVIDENCE)
def test_the_ten_evidence_cases(text, expected, masks):
    assert redact(text, names=("أحمد العتيبي",)) == (expected, masks)


def test_mixed_digits_a_phone_inside_a_word_and_an_iban_without_spaces():
    assert redact("رقمي٠٥٥1234567فاتصل") == ("رقمي[رقم]فاتصل", 1)
    assert redact("الحساب SA0380000000608010167519 نشط") == ("الحساب [حساب] نشط", 1)


def test_a_name_occurring_twice_is_masked_twice_and_a_url_among_arabic_is_cut_at_the_space():
    text, masks = redact("كتب أحمد العتيبي ثم وقّع أحمد العتيبي", names=("أحمد العتيبي",))
    assert (text, masks) == ("كتب العميل ثم وقّع العميل", 2)
    assert redact("افتح www.example.com/x ثم أعد المحاولة") == ("افتح [رابط] ثم أعد المحاولة", 1)


def test_an_eight_digit_number_and_an_empty_name_are_left_alone():
    assert redact("الطلب 12345678 وصل", names=("",)) == ("الطلب 12345678 وصل", 0)


def test_a_date_before_a_time_or_a_number_is_not_one_long_number():
    assert redact("2026-10-09 12:34") == ("2026-10-09 12:34", 0)
    assert redact("التاريخ 2026-10-09 0551234567") == ("التاريخ 2026-10-09 [رقم]", 1)
    assert redact("الرقم 20261009123 كتبه") == ("الرقم [رقم] كتبه", 1)   # أحد عشر رقماً متّصلة ليست تاريخاً
