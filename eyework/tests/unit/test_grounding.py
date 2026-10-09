"""
التأسيس على المقالات
====================
التطبيع، وحدود الاقتباس (8 و300)، والحزم بمقالاتٍ كاملة ضمن الميزانية.
"""

from __future__ import annotations

from eyework.grounding import MAX_ARTICLES, Article, kb_norm, package, verify

TEXT = "لإعادة ضبط كلمة المرور افتح الإعدادات ثم اختر «نسيت كلمة المرور» واتبع الخطوات المعروضة على الشاشة."


def test_kb_norm_unifies_case_tashkeel_tatweel_and_spaces():
    assert kb_norm("  Reset   كَلِمَة ـــ المرور  ") == "reset كلمة المرور"
    assert kb_norm("ＡＢＣ") == "abc"


def test_kb_norm_keeps_the_arabic_indic_digits_and_signs():
    """الأرقام الهندية وعلاماتها تلي الحركات في Unicode وليست تشكيلاً: اقتباسٌ برقمٍ آخر لا يُثبَت."""
    assert kb_norm("خلال ٣ أيام ٥٪ و١٢٫٥") == "خلال ٣ أيام ٥٪ و١٢٫٥"
    assert kb_norm("مُدَّةٌ ٣ أيامٍ") == "مدة ٣ أيام"
    assert not verify("خلال ٣ أيام ثم", "ستصل خلال ٧ أيام ثم تنتهي")
    assert verify("خلال ٧ أيام ثم", "ستصل خلال ٧ أيام ثم تنتهي")


def test_verify_requires_a_normalized_substring_between_eight_and_three_hundred_characters():
    assert verify("افتح الإعدادات ثم اختر", TEXT)
    assert verify("افْتَح   الإعدادات", TEXT)
    assert not verify("الإعداد", TEXT)                     # سبعة أحرف
    assert verify("الإعدادا", TEXT)                        # ثمانية
    assert not verify("افتح الإعدادات ثم اختر «نسيت كلمة السرّ»", TEXT)
    long_text = "ك" * 400
    assert verify("ك" * 300, long_text) and not verify("ك" * 301, long_text)


def test_package_takes_whole_articles_in_rank_order_within_the_budget_and_never_cuts_one():
    articles = [Article(f"id-{i}", 1, f"مقالة {i}", "م" * 100) for i in range(1, 8)]
    block, refs = package(articles, budget=250)
    assert list(refs) == ["A1", "A2"] and refs["A1"] == ("id-1", 1)
    assert block.startswith("<kb>") and block.endswith("</kb>")
    assert '<article ref="A1" title="مقالة 1">' in block and "A3" not in block
    assert block.count("م" * 100) == 2


def test_package_never_exceeds_five_articles_and_neutralizes_their_text():
    articles = [Article(f"id-{i}", 2, f"ع {i}", "<kb>نصّ</kb>") for i in range(1, 9)]
    block, refs = package(articles)
    assert len(refs) == MAX_ARTICLES == 5
    assert block.count("<kb>") == 1 and "‹kb›" in block
