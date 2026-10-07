"""
أداة الفحص الذاتي
=================
أداةٌ يستدعيها النموذج قبل جوابه النهائي: يرسل العنوان والوصف وكلمته
للمستخدم كما ينوي إرسالها، فتُفحص بقواعد `copy_rules` نفسها التي يُفحص بها
الجواب بعد وصوله، ويعود إليه ما خالف بجملةٍ عربية فيها الرقم المطلوب.

لماذا أداة لا تعليمات وحدها: النماذج لا تعدّ الحروف بدقة، والعربية أصعب
عدّاً؛ وكل جوابٍ يُرفض بعد وصوله استدعاءٌ مدفوع ذهب سدى. الأداة تعدّ عنه.

حدودها: لا تكتب شيئاً، ولا تقرأ شيئاً غير ما أُرسل إليها، ولا تعرف المستخدم.
والفحص بعد الجواب باقٍ كما هو؛ الأداة تقلّل الرفض ولا تحلّ محلّه.
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

#: جولات الأداة قبل الجواب. جولةٌ تكفي عادةً، والثانية لإصلاحٍ بعد مخالفة؛
#: ما زاد يعني نموذجاً يدور، فيُوقف ويُحسب جوابه غير صالح.
MAX_ROUNDS = 3

TOOL = {
    "name": TOOL_NAME,
    "description": (
        "تفحص العنوان والوصف وكلمتك للمستخدم بالقواعد نفسها التي يُفحص بها جوابك بعد وصوله، "
        "وتُرجع عدد الحروف وما يخالف القواعد بجملٍ تقول ما يجب تغييره. استدعِها بالنصّ الذي تنوي "
        "إرساله كما هو، قبل جوابك النهائي، وأعد استدعاءها بعد أيّ تعديل. "
        "الحقل ok يعني أن النصّ سيُقبل؛ وcautions تنبيهاتٌ لا تمنع القبول لكنها تُعرض للمستخدم، "
        "فأزل سببها إلا إن ذكره البائع بنفسه."
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

_PROBLEMS = {
    "TITLE_LENGTH": "العنوان {title} حرفاً، والمقبول من %d إلى %d." % (TITLE_MIN, TITLE_MAX),
    "DESCRIPTION_LENGTH": "الوصف {description} حرفاً، والمقبول من %d إلى %d." % (DESCRIPTION_MIN, DESCRIPTION_MAX),
    "SURROUNDING_SPACE": "احذف المسافات في أول النصّ أو آخره.",
    "TITLE_CONTROL": "العنوان سطرٌ واحد: احذف فواصل الأسطر ومحارف التحكّم منه.",
    "DESCRIPTION_CONTROL": "احذف محارف التحكّم من الوصف.",
    "DESCRIPTION_LINES": "الوصف أربعة أسطر على الأكثر.",
    "BIDI_CONTROL": "احذف محارف الاتجاه الخفية.",
    "CONTACT_LINK": "احذف الروابط وعناوين البريد والحسابات التي تبدأ بـ@.",
    "CONTACT_PHONE": "احذف أرقام الهواتف وأيّ سلسلةٍ من سبعة أرقام فأكثر.",
    "MARKUP": "احذف الرموز # و< و>.",
    "SYMBOLS": "احذف الرموز التعبيرية والرموز مثل ° و® و™، واكتب معناها كلماتٍ (مثل «درجة»).",
    "NOT_ARABIC": "اكتب بالعربية: الحروف اللاتينية أكثر من المسموح. أسماء العلامات اللاتينية القصيرة مقبولة.",
    "NOTE_LENGTH": "كلمتك للمستخدم %d حرفاً على الأكثر، بلا مسافاتٍ في طرفيها." % NOTE_TO_USER_MAX,
    "NOTE_CONTROL": "كلمتك للمستخدم سطرٌ واحد بلا محارف تحكّم.",
    "NOTE_CONTACT": "لا روابط ولا أرقام في كلمتك للمستخدم.",
    "NOTE_SYMBOLS": "لا رموز تعبيرية ولا # أو < أو > في كلمتك للمستخدم.",
    "NOTE_NOT_ARABIC": "اكتب كلمتك للمستخدم بالعربية.",
}

_CAUTIONS = {
    CopyWarning.PRICE: "يذكر سعراً أو خصماً أو عملة: احذفه إلا إن ذكره البائع في ملاحظته.",
    CopyWarning.HEALTH_CLAIM: "يحمل ما يُقرأ ادّعاءً صحياً أو علاجياً: احذفه أو صِف المنتج دونه.",
    CopyWarning.SUPERLATIVE: "فيه صيغة مبالغة («الأفضل»، «مضمون»...): استبدلها بوصفٍ محدّد مما يظهر.",
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
