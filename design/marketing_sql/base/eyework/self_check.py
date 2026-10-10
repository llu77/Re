"""
أداة الفحص الذاتي
=================
أداةٌ يستدعيها النموذج قبل جوابه النهائي: يرسل العنوان والوصف وكلمته
للمستخدم كما ينوي إرسالها، فتُفحص بقواعد `copy_rules` نفسها التي يُفحص بها
الجواب بعد وصوله، ويعود إليه ما خالف بجملةٍ عربية فيها الرقم المطلوب.

لماذا أداة لا تعليمات وحدها: لا يُعتمد على أن يعدّ النموذج حروف نصّه بدقة —
ولم يُقَس ذلك هنا — وكل جوابٍ يُرفض بعد وصوله استدعاءٌ مدفوع ذهب سدى. الأداة
تعدّ عنه. وأثرها في نسبة الرفض لم يُقَس بعد (انظر README).

حدودها: لا تكتب شيئاً، ولا تقرأ شيئاً غير ما أُرسل إليها، ولا تعرف المستخدم.
والفحص بعد الجواب باقٍ كما هو؛ الأداة يُراد بها تقليل الرفض، ولا تحلّ محلّه.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from eyework.copy_rules import (
    DESCRIPTION_MAX,
    DESCRIPTION_MIN,
    NOTE_TO_USER_MAX,
    TITLE_MAX,
    TITLE_MIN,
    CopyWarning,
    EditPreset,
    check_copy,
    check_note_to_user,
)

if TYPE_CHECKING:
    from eyework.prompt import CopyRequest

__all__ = ["MAX_ROUNDS", "TOOL", "TOOL_NAME", "keep_unchanged", "run"]

TOOL_NAME = "check_copy"

#: جولات الأداة قبل الجواب. جولةٌ تكفي عادةً، والثانية لإصلاحٍ بعد مخالفة،
#: والثالثة احتياط؛ بعدها يُطلب الجواب بلا أدوات.
MAX_ROUNDS = 3

TOOL = {
    "name": TOOL_NAME,
    "description": (
        "تفحص العنوان والوصف وكلمتك للبائع بالقواعد الآلية نفسها التي يُفحص بها جوابك بعد وصوله: "
        "الطول بعدد الحروف، والروابط وأرقام الهواتف، والرموز، ونسبة العربية، وتنبيهاتٌ ليّنة للسعر "
        "والادّعاء الصحي والمبالغة. استدعِها بالنصّ الذي تنوي إرساله حرفاً بحرف، قبل جوابك النهائي، "
        "ومرةً أخرى بعد أيّ تعديل. لا تستدعها حين تُرجع UNUSABLE_PHOTO. "
        "تُرجع ok (هل يُقبل النصّ)، وعدد حروف العنوان والوصف، وproblems (مخالفاتٌ تمنع القبول)، "
        "وcautions (تنبيهاتٌ تُعرض للبائع ولا تمنع القبول). "
        "لا تحكم على صدق النصّ أمام الصورة ولا على الخصوصية ولا على الأسلوب: ok حدٌّ أدنى لا الغاية."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "العنوان كما ستُرسله، سطرٌ واحد."},
            "description": {"type": "string", "description": "الوصف كما ستُرسله."},
            "message_to_user": {
                "type": "string",
                "description": "كلمتك للبائع كما ستُرسلها، أو نصٌّ فارغ إن لم تكن لك كلمة.",
            },
        },
        "required": ["title", "description", "message_to_user"],
        "additionalProperties": False,
    },
}

#: وقائع لا أوامر: ما في النصّ، والحدّ المقبول. القرار في التعديل للنموذج.
_PROBLEMS = {
    "TITLE_LENGTH": "طول العنوان {title} حرفاً، والمقبول من %d إلى %d." % (TITLE_MIN, TITLE_MAX),
    "DESCRIPTION_LENGTH": "طول الوصف {description} حرفاً، والمقبول من %d إلى %d." % (DESCRIPTION_MIN, DESCRIPTION_MAX),
    "SURROUNDING_SPACE": "في أول النصّ أو آخره مسافة.",
    "TITLE_CONTROL": "في العنوان فاصل سطرٍ أو محرف تحكّم، والعنوان سطرٌ واحد.",
    "DESCRIPTION_CONTROL": "في الوصف محرف تحكّم.",
    "DESCRIPTION_LINES": "الوصف أكثر من أربعة أسطر.",
    "BIDI_CONTROL": "في النصّ محارف اتجاهٍ خفية.",
    "CONTACT_LINK": "في النصّ رابطٌ أو بريد أو حسابٌ يبدأ بـ@، وهذه غير مقبولة.",
    "CONTACT_PHONE": "في النصّ رقم هاتف أو سلسلةٌ من سبعة أرقام فأكثر، وهذه غير مقبولة.",
    "MARKUP": "في النصّ أحد الرموز # أو < أو >، وهي غير مقبولة.",
    "SYMBOLS": "في النصّ رمزٌ تعبيري أو رمزٌ خاص، وهذه غير مقبولة. الرموز ° و® و™ و© مقبولة.",
    "NOT_ARABIC": "نسبة الحروف اللاتينية أعلى من المسموح؛ أسماء العلامات القصيرة مقبولة.",
    "NOTE_LENGTH": "الكلمة للبائع أطول من %d حرفاً، أو في طرفيها مسافة." % NOTE_TO_USER_MAX,
    "NOTE_CONTROL": "في الكلمة للبائع فاصل سطرٍ أو محرف تحكّم.",
    "NOTE_CONTACT": "في الكلمة للبائع رابطٌ أو رقم.",
    "NOTE_SYMBOLS": "في الكلمة للبائع رمزٌ تعبيري أو # أو < أو >.",
    "NOTE_NOT_ARABIC": "الكلمة للبائع ليست بالعربية.",
}

_CAUTIONS = {
    CopyWarning.PRICE: "في النصّ ما يُقرأ سعراً أو خصماً أو عملة. يُقبل، ويظهر للبائع تنبيهاً؛ ولا يُكتب إلا إن ذكره البائع.",
    CopyWarning.HEALTH_CLAIM: "في النصّ ما يُقرأ ادّعاءً صحياً أو علاجياً. يُقبل، ويظهر للبائع تنبيهاً.",
    CopyWarning.SUPERLATIVE: "في النصّ صيغة مبالغة مثل «الأفضل» أو «مضمون». يُقبل، ويظهر للبائع تنبيهاً.",
}


def keep_unchanged(request: CopyRequest, title: str, description: str) -> tuple[str, str]:
    """
    «عنوانٌ آخر فقط» يعني أن الوصف لا يتغيّر — حرفاً بحرف.

    لا يُطلب ذلك من النموذج ويُصدَّق: يُعاد الحقل الثابت من النسخة السابقة
    هنا، في الفحص الذاتي وفي الجواب معاً، والقاعدة تتحقّق من تطابقه.
    """
    if request.previous is not None:
        if EditPreset.NEW_TITLE in request.presets:
            description = request.previous.description
        if EditPreset.NEW_DESCRIPTION in request.presets:
            title = request.previous.title
    return title, description


def run(arguments: object, request: CopyRequest) -> tuple[str, bool]:
    """
    ينفّذ استدعاءً واحداً. يُرجع (محتوى نتيجة الأداة، هل هي خطأ).

    المدخلات من النموذج فتُفحص أنواعها هنا وإن كانت الأداة `strict`: ما لا
    يطابق يعود خطأً مفهوماً ولا يُنفَّذ شيء.
    """
    if (
        not isinstance(arguments, dict)
        or set(arguments) != {"title", "description", "message_to_user"}
        or not all(isinstance(value, str) for value in arguments.values())
    ):
        return "أرسل title وdescription وmessage_to_user نصوصاً، ولا شيء غيرها.", True

    title, description = keep_unchanged(request, arguments["title"], arguments["description"])
    copy = check_copy(title, description)
    _, note_errors = check_note_to_user(arguments["message_to_user"])
    counts = {"title": len(copy.title), "description": len(copy.description)}

    result = {
        "ok": copy.ok and not note_errors,
        "title_chars": counts["title"],
        "description_chars": counts["description"],
        "problems": [_PROBLEMS[code].format(**counts) for code in (*copy.errors, *note_errors)],
        "cautions": [_CAUTIONS[warning] for warning in copy.warnings],
    }
    return json.dumps(result, ensure_ascii=False), False
