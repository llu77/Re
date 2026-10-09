"""
فحص ما يكتبه النموذج
====================
رمزٌ لكل قاعدة، ولا اقتطاع: النصّ يُقبل كاملاً بعد التطبيع أو يُرفض كاملاً.
"""

from __future__ import annotations

import pytest

from eyework.ai_text import check

REASON = "سعر الوحدة في السطر 3 (45 ريالاً) أعلى بعشرة أضعاف من آخر شراءٍ للصنف (4.50 ريال)."


def test_a_clean_sentence_is_normalized_and_kept():
    text, codes = check("  سعر  الوحدة في السطر 3 أعلى من المعتاد. ", 12, 160)
    assert codes == () and text == "سعر الوحدة في السطر 3 أعلى من المعتاد."


@pytest.mark.parametrize(("text", "code"), [
    ("قصير", "LENGTH"),
    ("طويل " * 40, "LENGTH"),
    ("سطرٌ أول طويل بما يكفي.\nسطرٌ ثانٍ.", "LINES"),
    ("فيه محرف تحكّم\x07 داخل الجملة.", "CONTROL"),
    ("فيه محرف اتجاه ‮ خفي داخل الجملة.", "BIDI"),
    ("زر الموقع https://x.example قبل الاعتماد.", "CONTACT"),
    ("راسل البريد a.b@example.com قبل الاعتماد.", "CONTACT"),
    ("تواصل مع @supplier قبل الاعتماد الآن.", "CONTACT"),
    ("رقم الحساب 1234 5678 9012 لا يخصّ المورّد.", "DIGITS"),
    ("رقم الهوية ١٠١٢٣٤٥٦٧٨ لا يخصّ المورّد.", "DIGITS"),
    ("فيه وسم <b> في منتصف الجملة.", "MARKUP"),
    ("فيه رمزٌ تعبيري 😀 في الجملة.", "SYMBOLS"),
    ("Unit price on line 3 looks ten times too high.", "NOT_ARABIC"),
    ("يا سارة، سعر الوحدة أعلى من المعتاد.", "VOCATIVE"),
    ("أيها الموظف، سعر الوحدة أعلى من المعتاد.", "VOCATIVE"),
    ("عزيزتي، سعر الوحدة أعلى من المعتاد.", "VOCATIVE"),
    ("أهلاً، سعر الوحدة أعلى من المعتاد.", "VOCATIVE"),
])
def test_each_rule_has_its_code(text, code):
    normalized, codes = check(text, 12, 160)
    assert normalized is None and code in codes


def test_an_order_number_of_eight_digits_and_a_price_are_not_contact_data():
    assert check("الطلب 12345678 بسعر 1250.50 ريال سُجّل مرتين.", 12, 160)[1] == ()


def test_a_word_that_merely_starts_with_ya_is_not_a_vocative():
    assert check("ياقوت في السطر 3 بسعرٍ أعلى من المعتاد.", 12, 160)[1] == ()


def test_the_answer_may_span_up_to_six_lines_without_a_vocative_check_off():
    answer = "\n".join(f"{i}. خطوةٌ قصيرة" for i in range(1, 7))
    text, codes = check(answer, 1, 320, lines=6)
    assert codes == () and text.count("\n") == 5
    assert "LINES" in check(answer + "\n7. زيادة", 1, 320, lines=6)[1]


def test_the_vocative_check_can_be_switched_off():
    assert check("يا سارة، سعر الوحدة أعلى من المعتاد.", 12, 160, vocative=False)[1] == ()
