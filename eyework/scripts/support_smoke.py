"""
قياس مسوّدات الدعم قبل الإطلاق — على النموذج الحقيقي، بمفتاح المالك
====================================================================
أربع عشرة رسالة عميلٍ ثابتة على قاعدة معرفةٍ صغيرة من أربع مقالات، كلٌّ بما يُنتظر منها: مسودةٌ
تجيب وتقتبس من المقالة الصحيحة، أو «لم أجد في القاعدة ما يجيب» بطلب معلومات، أو «ليست طلب دعم»؛
وبلغة العميل. كل رسالةٍ تمرّ بمسار الإنتاج نفسه (`support_prompt.draft_call` ثم البوّابة الحقيقية ثم
`parse_draft` بكل فحوصه: الاقتباس الحرفي، ولا رقمٌ ولا رابطٌ ليس في المقالة، ولا طلب سرّ). لا يعمل في
CI ولا يلمس القاعدة، ويكلّف أربعة عشر استدعاءً.

    EYEWORK_ANTHROPIC_API_KEY=… python -m eyework.scripts.support_smoke

يطبع سطراً لكل حالة وما خالف المنتظر، ويخرج بـ1 إن خالفت حالةٌ واحدة: جودة المسودات تُقاس بهذا قبل
أن يقرأها موظف، لا بعده.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from eyework import support_prompt as prompt
from eyework import support_rules as rules
from eyework.grounding import Article


@dataclass(frozen=True, slots=True)
class KbArticle:
    id: str
    title: str
    issue: str
    resolution: str
    environment: str | None = None
    cause: str | None = None


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    message: str
    #: DRAFT أو CANNOT_ANSWER أو NOT_SUPPORT.
    status: str
    #: نوع الردّ المنتظر، أو None حين يصحّ أكثر من نوع.
    kind: str | None = None
    #: المقالة التي يجب أن يقتبس منها، أو None حين لا اقتباس.
    article: str | None = None


KB = (
    KbArticle("printer", "الطابعة تطبع صفحاتٍ فارغة", "الطابعة تطبع صفحاتٍ فارغة بعد تغيير الحبر.",
              "1. افتح غطاء الطابعة وأخرج خرطوشة الحبر.\n2. انزع الشريط اللاصق الواقي إن كان موجوداً.\n"
              "3. أعد الخرطوشة وأغلق الغطاء.\n4. اطبع صفحة اختبار.", cause="شريطٌ واقٍ لم يُنزع من خرطوشةٍ جديدة."),
    KbArticle("vpn", "الشبكة الخاصة لا تتصل من المنزل", "يظهر «تعذّر الاتصال» عند فتح برنامج الشبكة الخاصة من خارج المكتب.",
              "1. تأكّد أن الإنترنت يعمل بفتح أيّ موقع.\n2. أغلق البرنامج تماماً ثم افتحه.\n"
              "3. اختر الخادم «الرياض 2» من القائمة.\n4. إن بقي الخطأ فأعد تشغيل الجهاز.",
              environment="ويندوز 11، برنامج الشبكة الخاصة للمنشأة."),
    KbArticle("password", "نسيت كلمة مرور البريد", "لا يستطيع الموظف الدخول إلى بريد العمل لأنه نسي كلمة المرور.",
              "1. افتح صفحة الدخول إلى البريد واضغط «نسيت كلمة المرور».\n2. اتبع الخطوات المرسلة إلى الجوال المسجّل.\n"
              "3. اختر كلمة مرورٍ جديدة من اثني عشر حرفاً على الأقل."),
    KbArticle("wifi", "شبكة الضيوف بطيئة", "الإنترنت على شبكة الضيوف بطيءٌ جداً في قاعة الاجتماعات.",
              "1. اتصل بشبكة الموظفين بدل شبكة الضيوف إن كان الجهاز للعمل.\n2. أغلق التنزيلات الكبيرة.\n"
              "3. اقترب من نقطة الاتصال في سقف القاعة."),
)

CASES = (
    Case("طابعة فارغة", "السلام عليكم، ركّبت حبراً جديداً والطابعة الآن تطلع أوراقاً بيضاء فاضية.", "DRAFT", "ANSWER", "printer"),
    Case("طابعة بلا تفاصيل", "الطابعة خربانة", "CANNOT_ANSWER", "ASK_INFO"),
    Case("شبكة خاصة", "من البيت ما يتصل برنامج الـVPN، يقول تعذّر الاتصال.", "DRAFT", "ANSWER", "vpn"),
    Case("VPN بالإنجليزية", "The VPN app says it cannot connect when I work from home. What should I do?", "DRAFT", "ANSWER", "vpn"),
    Case("كلمة مرور منسية", "نسيت الباسوورد حق الإيميل وما أقدر أدخل.", "DRAFT", "ANSWER", "password"),
    Case("طلب كلمة المرور", "أرسلوا لي كلمة مروري القديمة على الواتساب لو سمحتم.", "DRAFT", None, "password"),
    Case("شبكة الضيوف", "النت في قاعة الاجتماعات مرة بطيء على شبكة الضيوف.", "DRAFT", "ANSWER", "wifi"),
    Case("شاشة سوداء", "شاشة جهاز الاستقبال سوداء من أمس ولا تستجيب لأي زر.", "CANNOT_ANSWER", "ASK_INFO"),
    Case("برنامج المحاسبة", "برنامج المحاسبة يقفل لحاله كل ما أفتح تقرير المبيعات.", "CANNOT_ANSWER", "ASK_INFO"),
    Case("شكرٌ فقط", "شكراً جزيلاً، اشتغلت الطابعة الحمد لله.", "NOT_SUPPORT"),
    Case("سؤال عن الدوام", "متى يبدأ دوام رمضان هذه السنة؟", "NOT_SUPPORT"),
    Case("وعدٌ لا تذكره المقالة", "متى بالضبط تصلحون الطابعة؟ أبي موعد اليوم قبل الساعة ٣.", "DRAFT", None, "printer"),
    Case("رسالة طويلة مختلطة", "صباح الخير. أمس جرّبت أطبع ملف العقد وطلعت الصفحات بيضاء، مع إن الحبر جديد ركّبته الأسبوع "
         "الماضي. جرّبت أطفي الطابعة وأشغلها وما تغيّر شي. الطابعة في الدور الثاني جنب غرفة المدير.", "DRAFT", "ANSWER", "printer"),
    Case("شكوى بلا مشكلة تقنية", "الموظف اللي رد علي أمس كان أسلوبه سيئ.", "NOT_SUPPORT"),
)


def _articles() -> tuple[tuple[Article, ...], dict[str, str]]:
    articles = tuple(Article(a.id, 1, f"KB-{n} · {a.title}", prompt.article_text(a.title, a.issue, a.environment, a.resolution, a.cause))
                     for n, a in enumerate(KB, start=1))
    sources = {a.id: prompt.article_source(a.title, a.issue, a.environment, a.resolution, a.cause) for a in KB}
    return articles, sources


def check(case: Case, gateway) -> tuple[str, list[str]]:
    """(ملخّص الجواب، ما خالف المنتظر). القاعدة الكاملة كما في الإنتاج: النموذج يرى المقالات الأربع."""
    articles, sources = _articles()
    language = rules.language_of(case.message)
    call, refs = prompt.draft_call(prompt.DraftInput((prompt.ThreadMessage("customer", case.message),), language, articles))
    reply = gateway.call(call)
    if reply.outcome != "OK":
        return reply.outcome, [f"الاستدعاء: {reply.outcome}"]
    try:
        draft = prompt.parse_draft(reply.data, refs, sources, language, ())
    except prompt.DraftInvalid as invalid:
        return "مرفوضة", [f"رفضها الخادم: {invalid.code}"]
    problems = []
    if draft["result"] != case.status:
        problems.append(f"النتيجة {draft['result']} والمنتظر {case.status}")
    if case.kind and draft["reply_kind"] != case.kind:
        problems.append(f"النوع {draft['reply_kind']} والمنتظر {case.kind}")
    cited = {c["article_id"] for c in draft["citations"]}
    if case.article and case.article not in cited:
        problems.append(f"لم يقتبس من «{case.article}»")
    if not case.article and cited:
        problems.append(f"اقتبس ممّا لا يجيب: {sorted(cited)}")
    if draft["body"] and rules.language_of(draft["body"]) != language:
        problems.append("الردّ بغير لغة العميل")
    if draft["body"] and rules.rule_flags(draft["body"], draft["reply_kind"] or "ANSWER", language,
                                          [sources[a] for a in cited]):
        problems.append("في الردّ ما تنبّه عليه القواعد")
    return f"{draft['result']}/{draft['reply_kind'] or '-'}", problems


def run(gateway) -> int:
    failed = 0
    for case in CASES:
        summary, problems = check(case, gateway)
        failed += bool(problems)
        print(f"{'✗' if problems else '✓'} {case.name}: {summary}" + (f" — {'؛ '.join(problems)}" if problems else ""))
    print(f"\n{len(CASES) - failed} من {len(CASES)} كما يُنتظر.")
    return 1 if failed else 0


def main() -> int:
    key = os.environ.get("EYEWORK_ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("EYEWORK_ANTHROPIC_API_KEY غير مضبوط", file=sys.stderr)
        return 2
    from eyework.model_gateway import AnthropicGateway

    return run(AnthropicGateway(key))


if __name__ == "__main__":
    sys.exit(main())
