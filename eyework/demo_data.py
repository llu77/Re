"""
بياناتٌ تجريبية لحسابٍ قائم
===========================
طلب المالك (2026-10-11): «اضف تذاكر مفتوحة متنوعة لكي استخدمها. اضف في أمين المخزون، الوحدات والمنتجات… الخ».
يضعها المشغّل بأمرٍ واحد في حسابٍ واحد، بحسب مهنته (`python -m eyework.admin seed-demo --login …`):

  • الدعم الفني: ستّ مقالاتٍ منشورة في قاعدة المعرفة، واثنتا عشرة تذكرةً مفتوحة بقنواتٍ وتصنيفاتٍ وأولوياتٍ
    مختلفة: خمسٌ جديدة، واثنتان مفتوحتان بإفادة «نعمل عليها»، وثلاثٌ بانتظار العميل بعد سؤاله، واثنتان مُصعَّدتان؛
    بعضها برسالتين وبملاحظةٍ داخلية، وواحدةٌ بالإنجليزية.
  • أمين المخزون: ستّ فئات، وخمسة مورّدين بمندوبيهم، وأربعة وعشرون منتجاً بالوحدات التسع كلّها (قطعة، علبة،
    كرتون، عبوة، طبلية، كيلوغرام، لتر، متر، خدمة) وبالفئتين الأساسية والصفرية للضريبة وبباركودٍ صحيح، ورصيدٌ
    افتتاحي (بعضه تحت حدّ الطلب)، وفاتورتا شراءٍ مسجّلتان وثالثةٌ مسودة.

كل شيءٍ يمرّ بدوالّ التطبيق نفسها وبهوية صاحب الحساب (دور الويب وسياسات العزل)، فلا يُكتب ما لا يقبله التطبيق، ولا
يُستدعى النموذج. التذاكر دفعةٌ جديدة في كل تشغيل (تُستهلك بالتجربة)؛ وما سواها يُضاف مرةً: ما وُجد باسمه يُترك.
والدعم يحتاج موافقة صاحب الحساب على إشعار المكتب أولاً: القاعدة لا تخزّن كلام عميلٍ قبلها. والمخزون يحتاج إجابته عن
سؤال الإعداد أولاً: أساس التكلفة يُقفل بعد أوّل فاتورة، فلا يُجاب عنه نيابةً عنه.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from uuid import UUID

from eyework import inventory, support
from eyework import support_rules as rules
from eyework.db import Database
from eyework.professions import Profession

__all__ = ["DemoError", "seed", "seed_inventory", "seed_support"]


class DemoError(Exception):
    """ما يمنع وضع البيانات، بجملةٍ يقرؤها المشغّل."""


# ── الدعم الفني ─────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class DemoArticle:
    title: str
    issue: str
    resolution: str
    environment: str | None = None
    cause: str | None = None


@dataclass(frozen=True, slots=True)
class DemoTicket:
    channel: str
    customer: str
    subject: str
    priority: str
    category: str
    messages: tuple[str, ...]
    #: ملاحظةٌ داخلية بعد رسائل العميل.
    note: str | None = None
    #: ما بعد الرسائل: لا شيء (جديدة)، أو «WORKING» (إفادة «نعمل عليها» فتصير مفتوحة)، أو أسئلةٌ جاهزة (بانتظار
    #: العميل)، أو جهة تصعيد.
    then: str | tuple[str, ...] | None = None
    escalation_note: str | None = None


ARTICLES: tuple[DemoArticle, ...] = (
    DemoArticle(
        "الطابعة تطبع صفحاتٍ فارغة",
        "الطابعة تُخرج صفحاتٍ بيضاء بعد تركيب خرطوشة حبرٍ جديدة.",
        "1. افتح غطاء الطابعة وأخرج الخرطوشة.\n2. انزع الشريط اللاصق الواقي عن فوهة الحبر إن كان موجوداً.\n"
        "3. أعد تركيب الخرطوشة حتى تسمع صوت تثبيتها.\n4. شغّل «تنظيف رأس الطباعة» من إعدادات الطابعة، ثم اطبع صفحة اختبار.",
        environment="طابعات الحبر في المكاتب",
        cause="الشريط الواقي على الخرطوشة الجديدة يمنع خروج الحبر.",
    ),
    DemoArticle(
        "تعذّر الدخول إلى البريد بعد تغيير كلمة المرور",
        "تظهر رسالة «الحساب مقفل» عند الدخول إلى البريد بعد تغيير كلمة المرور.",
        "1. أغلق تطبيق البريد في الهاتف والحاسوب.\n2. احذف الحساب من تطبيق البريد في الهاتف، ثم أضفه من جديد بكلمة "
        "المرور الجديدة.\n3. انتظر خمس عشرة دقيقة، ثم ادخل مرةً واحدة من الحاسوب.",
        cause="الأجهزة الأخرى تحاول الدخول بكلمة المرور القديمة فيُقفل الحساب مؤقتاً.",
    ),
    DemoArticle(
        "انقطاع الإنترنت عن جهازٍ واحد",
        "جهازٌ واحد بلا إنترنت، وبقية أجهزة المكتب تعمل.",
        "1. تأكّد أن كابل الشبكة مثبّتٌ في الجهاز وفي المقبس الجداري.\n2. أعد تشغيل الجهاز.\n3. إن كان الاتصال "
        "لاسلكياً فاحذف الشبكة من الإعدادات، ثم اتصل بها من جديد.\n4. إن بقي الانقطاع فجرّب كابلاً آخر.",
    ),
    DemoArticle(
        "الرسائل تصل إلى مجلد غير المرغوب فيه",
        "رسائل مرسلٍ معروف تصل إلى مجلد الرسائل غير المرغوب فيها.",
        "1. افتح الرسالة من مجلد غير المرغوب فيه، واختر «ليست بريداً عشوائياً».\n2. أضف عنوان المرسل إلى المرسلين "
        "الآمنين.\n3. إن تكرّر ذلك مع رسائل الجهة نفسها فأبلغ مسؤول البريد ليضيف نطاقها إلى القائمة الآمنة.",
    ),
    DemoArticle(
        "إضافة توقيعٍ إلى البريد",
        "يريد الموظف أن يظهر اسمه ووظيفته في آخر كل رسالة.",
        "1. افتح إعدادات البريد واختر «التوقيع».\n2. اكتب الاسم والوظيفة واسم الإدارة.\n3. فعّل «إضافة التوقيع إلى "
        "الرسائل الجديدة والردود»، ثم احفظ.",
    ),
    DemoArticle(
        "برنامج المحاسبة يتوقّف عند فتح تقرير الشهر",
        "يتجمّد برنامج المحاسبة ثم يُغلق عند فتح تقرير المبيعات الشهري.",
        "1. أغلق البرنامج كلياً من مدير المهام.\n2. افتح البرنامج واختر للتقرير مدةً أقصر (أسبوعاً بدل شهر).\n3. إن "
        "نجح التقرير الأقصر فحدّث البرنامج إلى آخر إصدار، ثم افتح تقرير الشهر.",
        cause="التقارير الكبيرة تستهلك ذاكرة الجهاز في الإصدارات القديمة.",
    ),
)

TICKETS: tuple[DemoTicket, ...] = (
    DemoTicket(
        "PHONE", "سارة القحطاني", "الإنترنت مقطوع عن قسم المحاسبة كله", "URGENT", "NETWORK",
        ("السلام عليكم، الإنترنت مقطوع عن كل أجهزة قسم المحاسبة منذ الثامنة صباحاً، والأقسام الأخرى تعمل. لا نستطيع "
         "إرسال الفواتير اليوم.",),
    ),
    DemoTicket(
        "EMAIL", "فهد العتيبي", "لا أستطيع الدخول إلى بريدي بعد تغيير كلمة المرور", "HIGH", "ACCOUNT",
        ("غيّرت كلمة مرور البريد أمس بطلبٍ من النظام، ومن اليوم تظهر لي رسالة أن الحساب مقفل.",
         "جرّبت من الحاسوب ومن الجوال والنتيجة نفسها."),
        then=("WHEN_STARTED", "DEVICE"),
    ),
    DemoTicket(
        "IN_PERSON", "نورة الشهري", "الطابعة تطبع صفحاتٍ فارغة", "NORMAL", "PRINTING",
        ("ركّبنا خرطوشة حبرٍ جديدة في طابعة الطابق الثاني، ومن بعدها تخرج الصفحات بيضاء.",),
        note="زرت المكتب: الطابعة في الطابق الثاني، والخرطوشة جديدة وما زال عليها الشريط الواقي.",
        then="WORKING",
    ),
    DemoTicket(
        "MESSAGING", "ماجد المطيري", "برنامج المحاسبة يتوقّف عند فتح تقرير الشهر", "NORMAL", "SOFTWARE",
        ("كل ما أفتح تقرير المبيعات الشهري يتجمّد البرنامج ثم يُغلق. التقارير الأسبوعية تعمل.",),
        then=("ERROR_TEXT", "WHEN_STARTED"),
    ),
    DemoTicket(
        "WEB_FORM", "هيا العنزي", "كيف أضيف توقيعاً إلى بريدي؟", "LOW", "HOW_TO",
        ("أريد أن يظهر اسمي ووظيفتي في آخر كل رسالة أرسلها. كيف أفعل ذلك؟",),
    ),
    DemoTicket(
        "IN_PERSON", "د. خالد الزهراني", "شاشة الحاسوب لا تعمل بعد انقطاع الكهرباء", "HIGH", "HARDWARE",
        ("بعد انقطاع الكهرباء أمس لم تعد شاشة جهازي تعرض شيئاً، والجهاز نفسه يعمل وأسمع صوت المروحة.",),
        then="FIELD_TECH",
        escalation_note="جُرّبت الشاشة بكابلٍ آخر فلم تستجب: تحتاج فحصاً في الموقع، واستبدالها إن تعطّلت.",
    ),
    DemoTicket(
        "EMAIL", "منى الدوسري", "رسائل أحد العملاء تذهب إلى مجلد غير المرغوب فيه", "NORMAL", "EMAIL",
        ("منذ أسبوع تصل رسائل أحد عملائنا المهمّين إلى مجلد الرسائل غير المرغوب فيها، ولا ننتبه لها إلا متأخرين.",),
        note="الرسائل كلها من نطاقٍ واحد: يُقترح إضافته إلى القائمة الآمنة على مستوى المنشأة.",
        then="WORKING",
    ),
    DemoTicket(
        "PHONE", "عبدالله السبيعي", "نقاط البيع لا تقبل الدفع بالبطاقة", "URGENT", "SOFTWARE",
        ("أجهزة نقاط البيع في الفرع الرئيسي ترفض كل عمليات الدفع بالبطاقة منذ الظهر، والعملاء ينتظرون.",),
        then="VENDOR",
        escalation_note="المشكلة في كل الأجهزة معاً بعد تحديث النظام صباحاً، وأُبلغ مزوّد نقاط البيع.",
    ),
    DemoTicket(
        "MESSAGING", "ريم الحربي", "تثبيت برنامج العروض لموظفٍ جديد", "NORMAL", "INSTALL",
        ("انضمّ إلينا موظفٌ جديد في التسويق، ويحتاج برنامج العروض التقديمية على جهازه.",),
    ),
    DemoTicket(
        "WEB_FORM", "ياسر الغامدي", "طلب لوحة مفاتيح بحروفٍ عربية", "LOW", "OTHER",
        ("لوحة المفاتيح في مكتبي بحروفٍ إنجليزية فقط، وأحتاج لوحةً بحروفٍ عربية.",),
    ),
    DemoTicket(
        "MESSAGING", "Lina Al-Saleh", "VPN keeps disconnecting", "HIGH", "NETWORK",
        ("Hello, the VPN disconnects every few minutes when I work from home, so I lose my session in the finance "
         "system.",),
    ),
    DemoTicket(
        "PHONE", "تركي العمري", "صلاحية الوصول إلى مجلد المشاريع المشترك", "NORMAL", "ACCOUNT",
        ("أحتاج صلاحية فتح مجلد المشاريع المشترك على الخادم، فمديري طلب مني مراجعة ملفات المشروع الجديد.",),
        then=("SCOPE",),
    ),
)

_KB_TITLES = """
SELECT v.title FROM kb_articles a JOIN kb_versions v ON v.article_id = a.id AND v.version = a.latest_version
"""


def _ticket_version(db: Database, user_id: UUID, ticket_id: UUID) -> int:
    return support.get_ticket(db, user_id, ticket_id)["row_version"]


def _send(db: Database, user_id: UUID, ticket_id: UUID, kind: str, **fields) -> None:
    """ردٌّ جاهز يُجهَّز ثم يُنسخ ثم يؤكَّد إرساله، كما يفعل الموظف."""
    reply = support.prepare_reply(db, user_id, ticket_id, {
        "kind": kind, "expected_row_version": _ticket_version(db, user_id, ticket_id), "client_token": uuid.uuid4(),
        **fields}, template=True)
    support.release_reply(db, user_id, UUID(reply["id"]), "COPY", reply["body_sha256"])
    support.confirm_reply(db, user_id, UUID(reply["id"]), True)


def seed_support(db: Database, user_id: UUID) -> dict[str, int]:
    """المقالات مرةً، ودفعة تذاكر جديدة في كل تشغيل."""
    if support.notice_version(db, user_id) is None:
        raise DemoError("افتح مكتب الدعم في التطبيق، واقرأ إشعاره ووافق عليه أولاً؛ ثم أعد الأمر.")
    with db.session(user_id) as cursor:
        cursor.execute(_KB_TITLES)
        titles = {row["title"] for row in cursor.fetchall()}
    articles = 0
    for item in ARTICLES:
        if item.title in titles:
            continue
        article = support.create_article(db, user_id, {
            "client_token": uuid.uuid4(), "title": item.title, "issue": item.issue, "environment": item.environment,
            "resolution": item.resolution, "cause": item.cause})
        support.publish(db, user_id, UUID(article["id"]), article["row_version"], article["latest_version"])
        articles += 1

    for item in TICKETS:
        ticket, _ = support.create_ticket(db, user_id, {
            "client_token": uuid.uuid4(), "channel": item.channel, "priority": item.priority, "category": item.category,
            "customer_label": item.customer, "subject": item.subject, "text": item.messages[0]})
        ticket_id = UUID(ticket["id"])
        for text in item.messages[1:]:
            support.add_message(db, user_id, ticket_id, {
                "expected_row_version": _ticket_version(db, user_id, ticket_id), "author": "CUSTOMER", "text": text,
                "client_token": uuid.uuid4()})
        if item.note:
            support.add_message(db, user_id, ticket_id, {
                "expected_row_version": _ticket_version(db, user_id, ticket_id), "author": "NOTE", "text": item.note,
                "client_token": uuid.uuid4()})
        if item.then == "WORKING":
            language = "EN" if item.messages[0].isascii() else "AR"
            _send(db, user_id, ticket_id, "UPDATE", core=rules.UPDATE_TEMPLATES["WORKING"][0 if language == "AR" else 1])
        elif isinstance(item.then, tuple):
            _send(db, user_id, ticket_id, "ASK_INFO", template_questions=list(item.then))
        elif item.then in rules.ESCALATION_TARGETS:
            support.escalate(db, user_id, ticket_id, {
                "expected_row_version": _ticket_version(db, user_id, ticket_id), "target": item.then,
                "note": item.escalation_note, "notify_customer": False})
    return {"articles": articles, "tickets": len(TICKETS)}


# ── أمين المخزون ────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class DemoSupplier:
    name: str
    vat_number: str
    cr_number: str
    phone: str
    #: (الاسم، الجوال) والأول هو المندوب المعتاد.
    reps: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class DemoItem:
    name: str
    unit: str
    category: str
    #: التكلفة والبيع بالهللة للوحدة، والكميات بالألف من الوحدة.
    price: int
    selling: int | None
    supplier: int
    opening: int = 0
    reorder: int | None = None
    vat: str = "S"
    kind: str = "STOCK"
    code: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class DemoPurchase:
    supplier: int
    number: str
    days_ago: int
    #: (رقم المنتج في ITEMS، الكمية بالألف، سعر الوحدة بالهللة).
    lines: tuple[tuple[int, int, int], ...]
    post: bool = True


CATEGORIES: tuple[str, ...] = ("مواد غذائية", "مشروبات", "منظفات", "أدوات مكتبية", "مستلزمات طبية", "تغليف وشحن")
SUPPLIERS: tuple[DemoSupplier, ...] = (
    DemoSupplier("شركة الواحة للمواد الغذائية", "300123456700003", "1010234567", "0551234501",
                 (("سلمان الشمري", "0551234501"), ("تركي العنزي", "0551234502"))),
    DemoSupplier("مؤسسة النقاء للمنظفات", "301987654300003", "4030345678", "0561234503", (("وليد الحربي", "0561234503"),)),
    DemoSupplier("مكتبة الرواد للأدوات المكتبية", "310555123400003", "2050456789", "0571234504",
                 (("هاني القرشي", "0571234504"),)),
    DemoSupplier("مستودعات الصحة للمستلزمات الطبية", "302468013500003", "1010567890", "0581234505",
                 (("بندر الزهراني", "0581234505"), ("فيصل العمري", "0591234506"))),
    DemoSupplier("شركة السريع للشحن", "300777888900003", "1010678901", "0501234507", (("عمر الجهني", "0501234507"),)),
)
ITEMS: tuple[DemoItem, ...] = (
    DemoItem("أرز بسمتي", "KG", "مواد غذائية", 900, 1200, 0, opening=250_000, reorder=100_000, code="1001"),
    DemoItem("سكر أبيض", "KG", "مواد غذائية", 450, 650, 0, opening=60_000, reorder=80_000, code="1002"),
    DemoItem("زيت طبخ", "LITRE", "مواد غذائية", 750, 1050, 0, opening=120_000, reorder=40_000, code="1003"),
    DemoItem("حليب طويل الأجل 1 لتر (12 علبة)", "CARTON", "مشروبات", 4800, 6200, 0, opening=35_000, reorder=20_000),
    DemoItem("ماء معبأ 330 مل (40 عبوة)", "CARTON", "مشروبات", 1300, 1900, 0, opening=30_000, reorder=50_000),
    DemoItem("عصير برتقال 200 مل (6 عبوات)", "PACK", "مشروبات", 1150, 1600, 0, opening=60_000, reorder=24_000),
    DemoItem("قهوة عربية 500 غ", "PIECE", "مواد غذائية", 3500, 4800, 0, opening=40_000, reorder=15_000),
    DemoItem("شاي أسود (100 كيس)", "BOX", "مشروبات", 1450, 1950, 0, opening=25_000, reorder=20_000),
    DemoItem("سائل غسيل الصحون 1 لتر", "PIECE", "منظفات", 650, 950, 1, opening=70_000, reorder=30_000, code="2001"),
    DemoItem("منظف أرضيات 4 لتر", "PIECE", "منظفات", 1800, 2600, 1, opening=18_000, reorder=20_000, code="2002"),
    DemoItem("مناديل ورقية (30 علبة)", "CARTON", "منظفات", 5200, 6900, 1, opening=12_000, reorder=8_000),
    DemoItem("أكياس قمامة كبيرة", "PACK", "منظفات", 900, 1400, 1, opening=80_000, reorder=30_000),
    DemoItem("ورق طباعة A4 (5 رزم)", "CARTON", "أدوات مكتبية", 9500, 12900, 2, opening=40_000, reorder=15_000),
    DemoItem("أقلام حبر جاف زرقاء (50 قلماً)", "BOX", "أدوات مكتبية", 2500, 3900, 2, opening=20_000, reorder=10_000),
    DemoItem("دبّاسة مكتبية", "PIECE", "أدوات مكتبية", 1200, 1900, 2, opening=15_000, reorder=5_000),
    DemoItem("ملفات بلاستيكية (10 ملفات)", "PACK", "أدوات مكتبية", 800, 1300, 2, opening=9_000, reorder=10_000),
    DemoItem("كمامات طبية (50 كمامة)", "BOX", "مستلزمات طبية", 1200, 1800, 3, opening=45_000, reorder=20_000),
    DemoItem("قفازات طبية (100 قفاز)", "BOX", "مستلزمات طبية", 1500, 2200, 3, opening=30_000, reorder=15_000),
    DemoItem("معقّم يدين 500 مل", "PIECE", "مستلزمات طبية", 700, 1100, 3, opening=55_000, reorder=25_000),
    DemoItem("باراسيتامول 500 ملغ (24 قرصاً)", "BOX", "مستلزمات طبية", 450, 650, 3, opening=100_000, reorder=40_000,
             vat="Z", note="دواءٌ مؤهَّل للنسبة الصفرية"),
    DemoItem("شريط لاصق للتغليف", "PIECE", "تغليف وشحن", 350, 600, 4, opening=150_000, reorder=50_000),
    DemoItem("صناديق شحن (طبلية من 100 صندوق)", "PALLET", "تغليف وشحن", 42000, None, 4, opening=3_000, reorder=2_000),
    DemoItem("حبل تغليف", "METRE", "تغليف وشحن", 50, 90, 4, opening=500_000, reorder=200_000),
    DemoItem("توصيلٌ داخل المدينة", "SERVICE", "تغليف وشحن", 2500, 3500, 4, kind="SERVICE"),
)
PURCHASES: tuple[DemoPurchase, ...] = (
    DemoPurchase(0, "20451", 6, ((0, 200_000, 880), (1, 150_000, 440), (3, 20_000, 4700))),
    DemoPurchase(1, "8812", 2, ((8, 48_000, 640), (9, 24_000, 1750), (11, 60_000, 880))),
    DemoPurchase(2, "5530", 0, ((12, 20_000, 9400), (13, 10_000, 2450)), post=False),
)

_CATEGORIES = "SELECT id, name FROM inv_categories"
_SUPPLIERS = "SELECT id, name FROM inv_suppliers"
_ITEMS = "SELECT id, name FROM inv_items"
_SETTINGS = "SELECT row_version FROM inv_settings"
_TODAY = "SELECT ew_riyadh_today() AS today"


def ean13(body: str) -> str:
    """باركود EAN-13 من اثني عشر رقماً ورقم تحقّقها."""
    total = sum(int(digit) * (3 if index % 2 else 1) for index, digit in enumerate(body))
    return body + str((10 - total % 10) % 10)


def _barcode(index: int) -> str:
    # 628 بادئة المملكة في GS1، ثم رقم الشركة التجريبي ورقم المنتج.
    return ean13(f"6281000{index + 1:05d}")


def _names(db: Database, user_id: UUID, statement: str) -> dict[str, UUID]:
    with db.session(user_id) as cursor:
        cursor.execute(statement)
        return {row["name"]: row["id"] for row in cursor.fetchall()}


def seed_inventory(db: Database, user_id: UUID) -> dict[str, int]:
    """ما لم يوجد باسمه يُضاف، ومعه رصيده الافتتاحي؛ والفواتير لحسابٍ لم يكن فيه منتجٌ قبلها."""
    with db.session(user_id) as cursor:
        cursor.execute(_SETTINGS)
        has_settings = cursor.fetchone() is not None
        cursor.execute(_TODAY)
        today = cursor.fetchone()["today"]
    if not has_settings:
        raise DemoError("افتح المخزون في التطبيق وأجب عن سؤال الإعداد أولاً؛ ثم أعد الأمر.")

    categories = _names(db, user_id, _CATEGORIES)
    added_categories = 0
    for name in CATEGORIES:
        if name not in categories:
            categories[name] = UUID(inventory.create_category(db, user_id, name)["id"])
            added_categories += 1

    suppliers = _names(db, user_id, _SUPPLIERS)
    supplier_ids: list[UUID] = []
    reps: list[UUID | None] = []
    added_suppliers = 0
    for item in SUPPLIERS:
        if item.name in suppliers:
            supplier_ids.append(suppliers[item.name])
            reps.append(None)
            continue
        created = inventory.create_supplier(db, user_id, item.name, item.vat_number, item.cr_number, item.phone, None)
        supplier_id = UUID(created["id"])
        first = None
        for position, (name, mobile) in enumerate(item.reps):
            rep = inventory.create_rep(db, user_id, supplier_id, name, mobile, position == 0)
            first = first or UUID(rep["id"])
        supplier_ids.append(supplier_id)
        reps.append(first)
        added_suppliers += 1

    existing = _names(db, user_id, _ITEMS)
    fresh_account = not existing
    opening_day = (today - datetime.timedelta(days=20)).isoformat()
    item_ids: list[UUID] = []
    added_items = 0
    for index, item in enumerate(ITEMS):
        if item.name in existing:
            item_ids.append(existing[item.name])
            continue
        created = inventory.create_item(db, user_id, {
            "name": item.name, "kind": item.kind, "unit": item.unit, "category_id": categories[item.category],
            "vat_category": item.vat, "price_halalas": item.price, "selling_price_halalas": item.selling,
            "selling_price_includes_vat": True, "barcode": None if item.kind == "SERVICE" else _barcode(index),
            "supplier_code": item.code, "reorder_level_milli": item.reorder,
            "target_level_milli": None if item.reorder is None else item.reorder * 2,
            "preferred_supplier_id": supplier_ids[item.supplier], "note": item.note})
        item_id = UUID(created["id"])
        item_ids.append(item_id)
        added_items += 1
        if item.opening:
            inventory.stock_voucher(db, user_id, "OPENING", {
                "client_token": uuid.uuid4(), "item_id": item_id, "quantity_milli": item.opening,
                "unit_cost_halalas": item.price, "occurred_on": opening_day})

    purchases = 0
    if fresh_account:
        for purchase in PURCHASES:
            day = (today - datetime.timedelta(days=purchase.days_ago)).isoformat()
            view = inventory.create_purchase(db, user_id, {
                "supplier_id": supplier_ids[purchase.supplier], "supplier_invoice_no": purchase.number,
                "invoice_date": day, "received_on": day, "prices_include_vat": False, "rep_id": reps[purchase.supplier]})
            purchase_id = UUID(view["id"])
            for index, quantity, price in purchase.lines:
                view = inventory.add_line(db, user_id, purchase_id, view["row_version"], {
                    "item_id": item_ids[index], "quantity_milli": quantity, "unit_price_halalas": price})
            if purchase.post:
                # الإجمالي المطبوع على فاتورة المورّد كما حسبه التطبيق؛ والمسودة تبقى بلا إجماليٍّ يُدخله صاحبها.
                view = inventory.patch_purchase(db, user_id, purchase_id, view["row_version"], {
                    "printed_total_halalas": view["totals"]["gross"], "printed_vat_halalas": view["totals"]["vat"]})
                flags = inventory.purchase_flags(db, user_id, purchase_id)
                inventory.post_purchase(db, user_id, purchase_id, flags["row_version"],
                                        [flag["key"] for flag in flags["flags"]])
            purchases += 1
    return {"categories": added_categories, "suppliers": added_suppliers, "items": added_items, "purchases": purchases}


def seed(db: Database, user_id: UUID, profession: Profession) -> dict[str, int]:
    if profession is Profession.SUPPORT:
        return seed_support(db, user_id)
    if profession is Profession.STOREKEEPER:
        return seed_inventory(db, user_id)
    raise DemoError("البيانات التجريبية للدعم الفني ولأمين المخزون؛ هذا الحساب في بوابة "
                    f"{profession.value}. انقله بـset-profession أولاً إن أردت.")
