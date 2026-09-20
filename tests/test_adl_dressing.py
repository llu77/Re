"""
قاعدة ترتيب اللبس — الاختبارات النقية
=======================================
لا قاعدة بيانات هنا: القاعدة دالةٌ على قائمة خطوات، فتُختبر مباشرة. فرضُها
في المخطط (ومنعُ دخول الطابور) في `tests/test_adl_gate.py`.

معيارا القبول 7 و8 من خطة القسم 5.
"""

import pytest

from core.adl.dressing import DressingStep, check_order, parse_steps, verify_program
from core.adl.types import DressingOrderViolation, DressingRejected


def program(*steps: tuple[str, str, str]) -> dict:
    """`(فعل، جانب، قطعة)` — ثلاثيات تُقرأ في سطر، فلا يختبئ الترتيب في ضجيج."""
    return {
        "module": "DRESSING",
        "steps": [
            {"action": action, "side": side, "garment": garment}
            for action, side, garment in steps
        ],
    }


# ── معيار القبول 7: اللبس يبدأ بالجانب المصاب ────────────────────────
def test_dressing_must_start_with_the_affected_side():
    with pytest.raises(DressingOrderViolation) as raised:
        verify_program(
            program(
                ("DON", "SOUND", "قميص"),
                ("DON", "AFFECTED", "قميص"),
            )
        )

    violation = raised.value
    assert violation.step_number == 1, "المخالفة تُسمّي الخطوة المخالفة برقمها"
    assert violation.step.garment == "قميص"
    assert "قميص" in str(violation)


def test_the_affected_side_first_is_accepted():
    steps = verify_program(
        program(
            ("DON", "AFFECTED", "قميص"),
            ("DON", "SOUND", "قميص"),
        )
    )
    assert steps == (
        DressingStep("DON", "AFFECTED", "قميص"),
        DressingStep("DON", "SOUND", "قميص"),
    )


# ── معيار القبول 8: الخلع ينتهي بالجانب المصاب ───────────────────────
def test_dressing_must_end_doffing_with_the_affected_side():
    with pytest.raises(DressingOrderViolation) as raised:
        verify_program(
            program(
                ("DOFF", "AFFECTED", "قميص"),
                ("DOFF", "SOUND", "قميص"),
            )
        )

    assert raised.value.step_number == 2, "آخر خطوة ذات جانب هي المخالِفة"
    assert "الخلع" in str(raised.value)


def test_the_sound_side_first_is_accepted_when_doffing():
    verify_program(
        program(
            ("DOFF", "SOUND", "قميص"),
            ("DOFF", "AFFECTED", "قميص"),
        )
    )


# ── وحدة الفحص هي القطعة لا البرنامج ─────────────────────────────────
def test_each_garment_is_checked_on_its_own():
    """
    قطعةٌ أولى صحيحة الترتيب لا تمرّر ما بعدها.

    لو كان الفحص على أول خطوة في البرنامج كلّه لكفى تصديرُ قطعةٍ سليمة
    ليمرّ كل ما يليها — وهذا أسهل التفافٍ ممكن على القاعدة.
    """
    with pytest.raises(DressingOrderViolation) as raised:
        verify_program(
            program(
                ("DON", "AFFECTED", "قميص"),
                ("DON", "SOUND", "قميص"),
                ("DON", "SOUND", "بنطال"),
                ("DON", "AFFECTED", "بنطال"),
            )
        )
    assert raised.value.step_number == 3
    assert raised.value.step.garment == "بنطال"


def test_interleaving_two_garments_is_not_a_violation():
    """
    برنامج ينتقل بين قطعتين صحيحٌ ما دامت كلٌّ منهما تبدأ بالمصاب.

    القسمة بالتجاور كانت ترفض هذا: كل خطوة تصير تسلسلاً وحدها، فتفشل ثالثة
    الخطوات لأنها «أول خطوة ذات جانب في تسلسلها». ورفضُ الصحيح في بوابة
    سلامة يدفع الممارس إلى إعادة ترتيبٍ تُرضي الآلة لا المريض.
    """
    verify_program(
        program(
            ("DON", "AFFECTED", "قميص"),
            ("DON", "AFFECTED", "بنطال"),
            ("DON", "SOUND", "قميص"),
            ("DON", "SOUND", "بنطال"),
        )
    )


def test_interleaving_does_not_hide_a_wrong_garment():
    """والتجميع بالقطعة لا يُخفي قطعةً مخالفة بين قطعتين سليمتين."""
    with pytest.raises(DressingOrderViolation) as raised:
        verify_program(
            program(
                ("DON", "AFFECTED", "قميص"),
                ("DON", "SOUND", "بنطال"),
                ("DON", "SOUND", "قميص"),
                ("DON", "AFFECTED", "بنطال"),
            )
        )
    assert raised.value.step.garment == "بنطال"
    assert raised.value.step_number == 2


def test_the_earliest_violation_is_the_one_reported():
    """مخالفتان ⇒ تُسمّى الأبكر: الممارس يقرأ من أول السطر لا من آخره."""
    with pytest.raises(DressingOrderViolation) as raised:
        verify_program(
            program(
                ("DON", "SOUND", "قميص"),
                ("DON", "AFFECTED", "قميص"),
                ("DON", "SOUND", "بنطال"),
                ("DON", "AFFECTED", "بنطال"),
            )
        )
    assert raised.value.step_number == 1


def test_a_garment_donned_twice_is_two_sequences():
    """لبسٌ فخلعٌ فلبسٌ ثلاثةُ تسلسلات، والثالث يُفحص كما يُفحص الأول."""
    with pytest.raises(DressingOrderViolation) as raised:
        verify_program(
            program(
                ("DON", "AFFECTED", "سترة"),
                ("DON", "SOUND", "سترة"),
                ("DOFF", "SOUND", "سترة"),
                ("DOFF", "AFFECTED", "سترة"),
                ("DON", "SOUND", "سترة"),
                ("DON", "AFFECTED", "سترة"),
            )
        )
    assert raised.value.step_number == 5


def test_don_and_doff_in_one_program_are_each_checked():
    verify_program(
        program(
            ("DON", "AFFECTED", "قميص"),
            ("DON", "SOUND", "قميص"),
            ("DOFF", "SOUND", "قميص"),
            ("DOFF", "AFFECTED", "قميص"),
        )
    )


# ── الخطوات الثنائية لا ترتيب لها ────────────────────────────────────
def test_a_bilateral_step_does_not_decide_the_order():
    """سحب البنطال لأعلى بالطرفين لا يسبق أحد الجانبين ولا يتأخّر عنه."""
    verify_program(
        program(
            ("DON", "BOTH", "بنطال"),
            ("DON", "AFFECTED", "بنطال"),
            ("DON", "SOUND", "بنطال"),
            ("DON", "BOTH", "بنطال"),
        )
    )


def test_a_garment_with_no_sided_step_is_not_judged():
    """قبّعة لا جانب لها. القاعدة تصمت حيث لا معنى لها."""
    verify_program(program(("DON", "BOTH", "قبّعة")))


def test_a_bilateral_step_cannot_hide_a_wrong_order():
    with pytest.raises(DressingOrderViolation):
        verify_program(
            program(
                ("DON", "BOTH", "بنطال"),
                ("DON", "SOUND", "بنطال"),
                ("DON", "AFFECTED", "بنطال"),
            )
        )


# ── حمولة لا تُقرأ لا تُفحص ──────────────────────────────────────────
@pytest.mark.parametrize(
    ("payload", "because"),
    [
        ({"module": "DRESSING"}, "بلا خطوات"),
        ({"module": "DRESSING", "steps": []}, "قائمة فارغة"),
        ({"module": "DRESSING", "steps": "قميص"}, "الخطوات نصّ لا قائمة"),
        ({"module": "DRESSING", "steps": ["قميص"]}, "خطوة ليست كائناً"),
        (
            {"module": "DRESSING", "steps": [{"action": "WEAR", "side": "AFFECTED", "garment": "قميص"}]},
            "فعل خارج المفردات",
        ),
        (
            {"module": "DRESSING", "steps": [{"action": "DON", "side": "RIGHT", "garment": "قميص"}]},
            "جانب اتجاهي لا رمزي",
        ),
        (
            {"module": "DRESSING", "steps": [{"action": "DON", "side": "AFFECTED", "garment": "  "}]},
            "قطعة بلا اسم",
        ),
    ],
)
def test_an_unreadable_program_is_rejected_not_passed(payload, because):
    with pytest.raises(DressingRejected):
        verify_program(payload)


def test_a_directional_side_is_refused_by_name():
    """
    `RIGHT` مرفوضة لا مترجَمة.

    قبولها يُدخل الاتجاه في البرنامج، فيصير البرنامج مرتبطاً بمريض بعينه
    ويصير الفحص مطابقةَ اتجاه — وكلاهما ما بُني الرمز لتفاديه.
    """
    with pytest.raises(DressingRejected, match="جانب غير معروف"):
        parse_steps(
            {"steps": [{"action": "DON", "side": "RIGHT", "garment": "قميص"}]}
        )


def test_check_order_is_silent_on_success():
    """النجاح صمت لا قيمة تُرجَع: لا يوجد حكم يُنسى فحصه."""
    assert check_order([DressingStep("DON", "AFFECTED", "قميص")]) is None
