"""
المهن وبواباتها
===============
كل حسابٍ لمهنةٍ واحدة يختارها صاحبه عند التسجيل، وتُفتح له بوابتها وحدها:
أداتها إن كانت لها أداة، ومهامّها، ومهاراتها. والقائمة هنا نظير الجدول
`professions` في الترحيل 0005؛ اختبارٌ يقارن الاثنين فلا ينحرفان.

**المحتوى من مصدرٍ رسمي، مترجماً.** المهامّ والمهارات من O*NET OnLine (وزارة
العمل الأمريكية) أو من التصنيف الدولي الموحد للمهن ISCO-08 (منظمة العمل
الدولية) للمهنة الأقرب، بأهميّتها حين تذكرها الصفحة ونصّها الإنجليزي حرفاً
بحرف، والعربية ترجمةٌ أمينة راجعها مدقّقٌ مستقلّ مقابل المصدر نفسه. O*NET
بترخيص CC BY 4.0، فيُذكر المصدر وأن النصّ مترجمٌ معدّل في كل شاشة.

**«كيف تُؤدّى» حكمٌ على هذا التطبيق لا على المهنة.** `IN_APP` لا يُوضع إلا حين
تؤدّي أداة البوابة المهمّة أو جزءاً منها فعلاً، وملاحظة البند تسمّي ذلك الجزء —
والأداة الوحيدة اليوم حملة التسويق؛ وما سواها عملٌ مكتبي في أنظمة صاحب العمل، أو
ميداني، أو بالهاتف. لا يُقال إن مهارةً
«يمارسها التطبيق»: لا مصدر يربط خطوةً في أداةٍ بمهارة.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["NAMES", "PORTALS", "Mode", "Portal", "Profession", "Skill", "Source", "Task", "TAGLINES", "view"]


class Profession(str, Enum):
    MARKETING = "MARKETING"
    STOREKEEPER = "STOREKEEPER"
    SUPPORT = "SUPPORT"


#: الاسم كما يظهر للمستخدم، ونظيره `professions.name_ar` في القاعدة.
NAMES: dict[Profession, str] = {
    Profession.MARKETING: "التسويق",
    Profession.STOREKEEPER: "أمين المخزون",
    Profession.SUPPORT: "الدعم الفني",
}


class Mode(str, Enum):
    #: تؤدّيه أداة البوابة بالنظر.
    IN_APP = "IN_APP"
    #: عملٌ مكتبي يحتاج أنظمة صاحب العمل وبياناته.
    EMPLOYER_SYSTEM = "EMPLOYER_SYSTEM"
    #: حضورٌ في الموقع أو مناولةٌ باليد.
    ON_SITE = "ON_SITE"
    #: بالهاتف أو الكلام.
    VOICE = "VOICE"


#: حدود ما يتّسع له عرض بندٍ واحد في شاشةٍ بلا تمرير (375×635).
TASK_MAX, NOTE_MAX, SKILL_MAX = 110, 100, 40


@dataclass(frozen=True, slots=True)
class Source:
    #: كما يُعرض: «O*NET OnLine 43-5071.00» أو «ISCO-08 2431».
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class Task:
    ar: str
    mode: Mode
    #: الأهمية كما في صفحة O*NET (0–100)، أو None حين لا يذكرها المصدر (ISCO-08).
    importance: int | None
    #: النصّ الإنجليزي حرفاً بحرف، للمراجعة لا للعرض.
    source_text: str
    #: ما تؤدّيه الأداة من المهمّة إن كانت IN_APP، أو حدٌّ لازم للفهم.
    note: str = ""


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    note: str
    importance: int
    source_text: str


@dataclass(frozen=True, slots=True)
class Portal:
    profession: Profession
    #: سطرٌ يصف البوابة في خطوة اختيار المهنة.
    tagline: str
    #: التعريف من المصدر، مختصراً.
    summary: str
    #: تعريف المصدر بالإنجليزية حرفاً بحرف، للمراجعة لا للعرض.
    summary_source_text: str
    tasks_source: Source
    skills_source: Source
    #: رموز المهنة في التصنيفين الدولي والسعودي حين وُجد مصدرٌ رسمي يسمّيها.
    related: tuple[str, ...]
    tasks: tuple[Task, ...]
    skills: tuple[Skill, ...]
    #: أدوات البوابة في التطبيق. CAMPAIGN: حملة منتج.
    tools: tuple[str, ...] = ()


def _ONET(code: str) -> Source:  # noqa: N802 — اسمٌ يُقرأ كالمصدر نفسه في التعريفات أدناه
    return Source(f"O*NET OnLine {code}", f"https://www.onetonline.org/link/details/{code}")


_ISCO_URL = ("https://www.ilo.org/ilostat-files/ISCO/newdocs-08-2021/ISCO-08/"
             "ISCO-08%20EN%20Structure%20and%20definitions.xlsx")


#: المهارة الواحدة في O*NET بنصٍّ واحد، فتُترجم مرةً واحدة في كل البوابات: (الشرح، المصدر).
_SPEAKING = ("التحدث إلى الآخرين لنقل المعلومات بفعالية.",
             "Speaking — Talking to others to convey information effectively.")
_ACTIVE_LISTENING = (
    "الانتباه الكامل لكلام الآخرين وفهمه بتأنٍّ والسؤال عند الحاجة وعدم المقاطعة في غير وقتها.",
    "Active Listening — Giving full attention to what other people are saying, taking time to understand the points "
    "being made, asking questions as appropriate, and not interrupting at inappropriate times.")
_READING = ("فهم الجمل والفقرات المكتوبة في مستندات العمل.",
            "Reading Comprehension — Understanding written sentences and paragraphs in work-related documents.")
_CRITICAL_THINKING = (
    "استخدام المنطق والاستدلال لتحديد قوة وضعف البدائل من حلول أو استنتاجات أو طرق حل للمشكلات.",
    "Critical Thinking — Using logic and reasoning to identify the strengths and weaknesses of alternative solutions, "
    "conclusions, or approaches to problems.")
_COMPLEX_PROBLEMS = (
    "تحديد المشكلات المعقدة ومراجعة معلوماتها لوضع الخيارات وتقييمها وتنفيذ الحلول.",
    "Complex Problem Solving — Identifying complex problems and reviewing related information to develop and "
    "evaluate options and implement solutions.")
_WRITING = ("التواصل كتابةً بفعالية بما يناسب احتياجات الجمهور.",
            "Writing — Communicating effectively in writing as appropriate for the needs of the audience.")
_ACTIVE_LEARNING = (
    "فهم أثر المعلومات الجديدة في حل المشكلات واتخاذ القرارات حاضرًا ومستقبلًا.",
    "Active Learning — Understanding the implications of new information for both current and future "
    "problem-solving and decision-making.")
_JUDGMENT = (
    "الموازنة بين تكاليف الإجراءات الممكنة وفوائدها لاختيار أنسبها.",
    "Judgment and Decision Making — Considering the relative costs and benefits of potential actions to choose the "
    "most appropriate one.")


_STOREKEEPER = Portal(
    profession=Profession.STOREKEEPER,
    tagline="مهامّ أمين المخزون ومهاراته من المصادر الرسمية",
    summary=("تُعنى المهنة بالتحقق من سجلات الشحنات الواردة والصادرة المتعلقة بالمخزون وحفظها، "
             "ومن مهامّها التحقق من البضائع والمواد الواردة وتسجيلها وترتيب نقل المنتجات."),
    summary_source_text=(
        "Verify and maintain records on incoming and outgoing shipments involving inventory. Duties include "
        "verifying and recording incoming merchandise or material and arranging for the transportation of products. "
        "May prepare items for shipment."),
    tasks_source=_ONET("43-5071.00"),
    skills_source=_ONET("43-5071.00"),
    related=("ISCO-08 4321 موظفو المخزون", "أمين مستودع 313907 (التصنيف السعودي الموحد للمهن)"),
    tasks=(
        Task("فحص محتويات الشحنة ومقارنتها بالسجلات، مثل بيانات الحمولة أو الفواتير أو الطلبات، للتحقق من دقتها",
             Mode.ON_SITE, 81,
             "Examine shipment contents and compare with records, such as manifests, invoices, or orders, "
             "to verify accuracy."),
        Task("طلب مواد الشحن ولوازمه وتخزينها للمحافظة على رصيدها في المخزون",
             Mode.ON_SITE, 76,
             "Requisition and store shipping materials and supplies to maintain inventory of stock."),
        Task("إعداد المستندات، مثل أوامر العمل أو بوالص الشحن أو أوامر الشحن، لتوجيه المواد",
             Mode.EMPLOYER_SYSTEM, 76,
             "Prepare documents, such as work orders, bills of lading, or shipping orders, to route materials."),
        Task("تعبئة المواد أو إغلاقها أو وضع الملصقات أو طوابع البريد عليها للشحن، بأدوات يدوية أو كهربائية أو آلة ختم بريدي",
             Mode.ON_SITE, 75,
             "Pack, seal, label, or affix postage to prepare materials for shipping, using hand tools, power tools, "
             "or postage meter."),
        Task("تسجيل بيانات الشحنات، كالوزن والرسوم والمساحة المتاحة والتلف أو الفروقات، للتقارير أو المحاسبة أو حفظ السجلات",
             Mode.EMPLOYER_SYSTEM, 74,
             "Record shipment data, such as weight, charges, space availability, damages, or discrepancies, "
             "for reporting, accounting, or recordkeeping purposes."),
        Task("التشاور أو المراسلة مع ممثلي المنشآت لمعالجة المشكلات، مثل التلف أو النقص أو عدم المطابقة للمواصفات",
             Mode.EMPLOYER_SYSTEM, 74,
             "Confer or correspond with establishment representatives to rectify problems, such as damages, "
             "shortages, or nonconformance to specifications."),
        Task("إيصال المواد أو توجيهها إلى الأقسام باستخدام عربة يدوية أو سير ناقل أو صناديق فرز",
             Mode.ON_SITE, 72,
             "Deliver or route materials to departments using handtruck, conveyor, or sorting bins."),
        Task("التواصل مع ممثلي شركات النقل لإجراء الترتيبات أو إصدار التعليمات الخاصة بشحن المواد وتسليمها",
             Mode.EMPLOYER_SYSTEM, 70,
             "Contact carrier representatives to make arrangements or to issue instructions for shipping and "
             "delivery of materials."),
        Task("تحديد طرق الشحن أو مساراته أو أسعاره للمواد المراد شحنها",
             Mode.EMPLOYER_SYSTEM, 70,
             "Determine shipping methods, routes, or rates for materials to be shipped."),
        Task("حساب القيم، مثل المساحة المتاحة أو رسوم الشحن أو التخزين أو التأخير، بالحاسوب أو بقائمة الأسعار",
             Mode.EMPLOYER_SYSTEM, 68,
             "Compute amounts, such as space available, shipping, storage, or demurrage charges, using computer "
             "or price list."),
        Task("مقارنة مسارات الشحن أو طرقه لتحديد أقلها أثرًا على البيئة",
             Mode.EMPLOYER_SYSTEM, 67,
             "Compare shipping routes or methods to determine which have the least environmental impact."),
    ),
    skills=(
        Skill("التحدث", _SPEAKING[0], 56, _SPEAKING[1]),
        Skill("الإصغاء الفعّال", _ACTIVE_LISTENING[0], 53, _ACTIVE_LISTENING[1]),
        Skill("فهم المقروء", _READING[0], 53, _READING[1]),
        Skill("التفكير الناقد", _CRITICAL_THINKING[0], 50, _CRITICAL_THINKING[1]),
        Skill("المراقبة والتقييم",
              "متابعة أداء الذات أو الآخرين أو الجهات وتقييمه لإجراء تحسينات أو اتخاذ إجراء تصحيحي.", 50,
              "Monitoring — Monitoring/Assessing performance of yourself, other individuals, or organizations to "
              "make improvements or take corrective action."),
        Skill("إدارة الوقت", "إدارة الوقت الشخصي ووقت الآخرين.", 50,
              "Time Management — Managing one's own time and the time of others."),
        Skill("حل المشكلات المعقدة", _COMPLEX_PROBLEMS[0], 47, _COMPLEX_PROBLEMS[1]),
        Skill("التنسيق", "مواءمة الإجراءات مع ما يقوم به الآخرون.", 47,
              "Coordination — Adjusting actions in relation to others' actions."),
    ),
)

_MARKETING = Portal(
    profession=Profession.MARKETING,
    tagline="أداة حملة المنتج، ومهامّ التسويق ومهاراته من المصادر الرسمية",
    summary=("تُعنى المهنة بتطوير استراتيجيات الإعلان وحملاته وتنسيقها، وتحديد السوق للسلع والخدمات الجديدة، "
             "وتحديد فرص السوق للسلع والخدمات الجديدة والقائمة وتطويرها."),
    summary_source_text=(
        "Advertising and marketing professionals develop and coordinate advertising strategies and campaigns, "
        "determine the market for new goods and services, and identify and develop market opportunities for new "
        "and existing goods and services."),
    # ISCO-08 لا يرتّب المهامّ بأهمية ولا يذكر مهارات؛ فالمهارات من O*NET للمهنة التي
    # يسمّيها جدول التقابل الرسمي بين O*NET وESCO للرمز 2431.
    tasks_source=Source("ISCO-08 2431", _ISCO_URL),
    skills_source=_ONET("13-1161.00"),
    related=("أخصائي تسويق 243110 (التصنيف السعودي الموحد للمهن)",
             "أخصائي دعاية وإعلان 243101 (التصنيف السعودي الموحد للمهن)"),
    tasks=(
        Task("تخطيط سياسات الإعلان وحملاته وتطويرها وتنظيمها لدعم أهداف المبيعات",
             Mode.IN_APP, None,
             "planning, developing and organizing advertising policies and campaigns to support sales objectives;",
             "في التطبيق: حملةٌ لمنتجٍ واحد بعنوانها ووصفها وميزانيتها ومدّتها، وملخّصٌ يُسلَّم دون نشرٍ أو دفع."),
        Task("نصح المديرين والعملاء باستراتيجيات وحملات للسوق المستهدفة توعّي المستهلك وتروّج بفاعلية لخصائص السلع والخدمات",
             Mode.EMPLOYER_SYSTEM, None,
             "advising managers and clients on strategies and campaigns to reach target markets, creating consumer "
             "awareness and effectively promoting the attributes of goods and services;"),
        Task("كتابة النصوص الإعلانية والإعلامية، وترتيب الإنتاج التلفزيوني والسينمائي وحجز مساحات الإعلان في وسائل الإعلام",
             Mode.IN_APP, None,
             "writing advertising copy and media scripts, and arranging television and film production and media "
             "placement;",
             "في التطبيق: عنوان الإعلان ووصفه فقط؛ يكتبهما المساعد، ثم يُعتمدان أو يُطلب تعديلهما."),
        Task("جمع البيانات عن أنماط المستهلكين وتفضيلاتهم وتحليلها",
             Mode.EMPLOYER_SYSTEM, None,
             "collecting and analysing data regarding consumer patterns and preferences;"),
        Task("تفسير اتجاهات المستهلكين الحالية والمستقبلية والتنبؤ بها",
             Mode.EMPLOYER_SYSTEM, None,
             "interpreting and predicting current and future consumer trends;"),
        Task("دراسة الطلب المحتمل وخصائص السوق للسلع والخدمات الجديدة",
             Mode.EMPLOYER_SYSTEM, None,
             "researching potential demand and market characteristics for new goods and services;"),
        Task("دعم نمو الأعمال وتطويرها بإعداد الأهداف والسياسات والبرامج التسويقية وتنفيذها",
             Mode.EMPLOYER_SYSTEM, None,
             "supporting business growth and development through the preparation and execution of marketing "
             "objectives, policies and programmes;"),
        Task("التكليف بأبحاث السوق وإجراؤها لتحديد فرص السوق للسلع والخدمات الجديدة والقائمة",
             Mode.EMPLOYER_SYSTEM, None,
             "commissioning and undertaking market research to identify market opportunities for new and existing "
             "goods and services;"),
        Task("تقديم المشورة بشأن كل عناصر التسويق، مثل مزيج المنتجات والتسعير والإعلان وترويج المبيعات وقنوات البيع والتوزيع",
             Mode.EMPLOYER_SYSTEM, None,
             "advising on all elements of marketing such as product mix, pricing, advertising and sales promotion, "
             "selling and distribution channels."),
    ),
    skills=(
        Skill("الإصغاء الفعّال", _ACTIVE_LISTENING[0], 75, _ACTIVE_LISTENING[1]),
        Skill("التفكير الناقد", _CRITICAL_THINKING[0], 75, _CRITICAL_THINKING[1]),
        Skill("فهم المقروء", _READING[0], 75, _READING[1]),
        Skill("الكتابة", _WRITING[0], 75, _WRITING[1]),
        Skill("التحدث", _SPEAKING[0], 72, _SPEAKING[1]),
        Skill("التعلّم النشط", _ACTIVE_LEARNING[0], 69, _ACTIVE_LEARNING[1]),
        Skill("حل المشكلات المعقدة", _COMPLEX_PROBLEMS[0], 69, _COMPLEX_PROBLEMS[1]),
        Skill("التقدير واتخاذ القرار", _JUDGMENT[0], 69, _JUDGMENT[1]),
    ),
    tools=("CAMPAIGN",),
)

_SUPPORT = Portal(
    profession=Profession.SUPPORT,
    tagline="مهامّ الدعم الفني ومهاراته من المصادر الرسمية",
    summary=("تُعنى المهنة بتقديم المساعدة التقنية لمستخدمي الحاسب، والإجابة عن أسئلة العملاء أو حل مشكلاتهم "
             "في الحاسب حضوريًا أو بالهاتف أو إلكترونيًا."),
    summary_source_text=(
        "Provide technical assistance to computer users. Answer questions or resolve computer problems for clients "
        "in person, via telephone, or electronically. May provide assistance concerning the use of computer hardware "
        "and software, including printing, installation, word processing, electronic mail, and operating systems."),
    tasks_source=_ONET("15-1232.00"),
    skills_source=_ONET("15-1232.00"),
    # لم يُعثر على رمزٍ سعودي من ستة أرقام تحت 3512 في مصدرٍ رسمي متاح، فلا يُذكر.
    related=("ISCO-08 3512 فنيو دعم مستخدمي تقنية المعلومات والاتصالات",),
    tasks=(
        Task("الإشراف على الأداء اليومي لأنظمة الحاسب",
             Mode.EMPLOYER_SYSTEM, 75,
             "Oversee the daily performance of computer systems."),
        Task("تجهيز المعدات لاستخدام الموظفين بالتركيب السليم للكابلات أو أنظمة التشغيل أو البرامج المناسبة أو ضمانه",
             Mode.ON_SITE, 74,
             "Set up equipment for employee use, performing or ensuring proper installation of cables, operating "
             "systems, or appropriate software."),
        Task("قراءة الأدلة التقنية أو التشاور مع المستخدمين أو تشخيص الحاسب لبحث المشكلات وحلها أو للمساعدة والدعم الفنيين",
             Mode.EMPLOYER_SYSTEM, 74,
             "Read technical manuals, confer with users, or conduct computer diagnostics to investigate and resolve "
             "problems or to provide technical assistance and support."),
        Task("الإجابة عن استفسارات المستخدمين بشأن تشغيل برامج الحاسب أو أجهزته لحل المشكلات",
             Mode.EMPLOYER_SYSTEM, 70,
             "Answer user inquiries regarding computer software or hardware operation to resolve problems."),
        Task("تركيب الأجهزة أو البرامج أو الأجهزة الملحقة وإجراء إصلاحات بسيطة لها وفق مواصفات التصميم أو التركيب",
             Mode.ON_SITE, 69,
             "Install and perform minor repairs to hardware, software, or peripheral equipment, following design "
             "or installation specifications."),
        Task("التشاور مع الموظفين والمستخدمين والإدارة لتحديد متطلبات الأنظمة الجديدة أو التعديلات عليها",
             Mode.VOICE, 68,
             "Confer with staff, users, and management to establish requirements for new systems or modifications."),
        Task("إدخال الأوامر ومراقبة عمل النظام للتحقق من سلامة التشغيل واكتشاف الأخطاء",
             Mode.EMPLOYER_SYSTEM, 64,
             "Enter commands and observe system functioning to verify correct operations and detect errors."),
        Task("الاحتفاظ بسجلات معاملات اتصال البيانات اليومية والمشكلات والإجراءات التصحيحية المتخذة أو أعمال التركيب",
             Mode.EMPLOYER_SYSTEM, 62,
             "Maintain records of daily data communication transactions, problems and remedial actions taken, or "
             "installation activities."),
        Task("إحالة المشكلات الكبيرة في الأجهزة أو البرامج أو المنتجات المعيبة إلى الموردين أو الفنيين لصيانتها",
             Mode.EMPLOYER_SYSTEM, 60,
             "Refer major hardware or software problems or defective products to vendors or technicians for "
             "service."),
        Task("إعداد تقييمات للبرامج أو الأجهزة والتوصية بتحسينات أو ترقيات",
             Mode.EMPLOYER_SYSTEM, 60,
             "Prepare evaluations of software or hardware, and recommend improvements or upgrades."),
        Task("إعداد مواد وإجراءات تدريبية أو تدريب المستخدمين على الاستخدام الصحيح للأجهزة أو البرامج",
             Mode.EMPLOYER_SYSTEM, 58,
             "Develop training materials and procedures, or train users in the proper use of hardware or "
             "software."),
        Task("فحص المعدات وقراءة نماذج الطلبات تمهيدًا لتسليم المعدات إلى المستخدمين",
             Mode.ON_SITE, 55,
             "Inspect equipment and read order sheets to prepare for delivery to users."),
    ),
    skills=(
        Skill("الإصغاء الفعّال", _ACTIVE_LISTENING[0], 75, _ACTIVE_LISTENING[1]),
        Skill("فهم المقروء", _READING[0], 75, _READING[1]),
        Skill("التحدث", _SPEAKING[0], 75, _SPEAKING[1]),
        Skill("التفكير الناقد", _CRITICAL_THINKING[0], 69, _CRITICAL_THINKING[1]),
        Skill("حل المشكلات المعقدة", _COMPLEX_PROBLEMS[0], 66, _COMPLEX_PROBLEMS[1]),
        Skill("الكتابة", _WRITING[0], 63, _WRITING[1]),
        Skill("التقدير واتخاذ القرار", _JUDGMENT[0], 56, _JUDGMENT[1]),
        Skill("التعلّم النشط", _ACTIVE_LEARNING[0], 53, _ACTIVE_LEARNING[1]),
    ),
)

PORTALS: dict[Profession, Portal] = {
    Profession.MARKETING: _MARKETING,
    Profession.STOREKEEPER: _STOREKEEPER,
    Profession.SUPPORT: _SUPPORT,
}

TAGLINES: dict[Profession, str] = {p: portal.tagline for p, portal in PORTALS.items()}

_MODE_ORDER = (Mode.IN_APP, Mode.EMPLOYER_SYSTEM, Mode.VOICE, Mode.ON_SITE)


#: نسبة O*NET كاملةً كما يطلبها ترخيصه (onetonline.org/help/license): الجهة، والعلامة
#: التجارية، ورابط الترخيص، وأن المحتوى معدّلٌ لم تعتمده الجهة. تُعرض في شاشة الحساب.
ATTRIBUTION = (
    "تتضمّن البوابة معلوماتٍ من O*NET® OnLine لإدارة التوظيف والتدريب بوزارة العمل الأمريكية (USDOL/ETA)، "
    "بترخيص CC BY 4.0 (creativecommons.org/licenses/by/4.0). O*NET® علامةٌ تجارية لـUSDOL/ETA. "
    "ترجم هذا التطبيق هذه المعلومات وعدّلها، ولم تعتمد USDOL/ETA هذه التعديلات ولم تؤيّدها ولم تختبرها.")


def source_line(portal: Portal, kind: str) -> str:
    """سطر المصدر تحت كل بند وتحت التعريف: من أين، وأنه مترجمٌ معدّل، وترخيص O*NET حين يكون منه."""
    source = portal.skills_source if kind == "skills" else portal.tasks_source
    if source.label.startswith("O*NET"):
        label = source.label.replace("O*NET", "O*NET®", 1)
        return f"المصدر: {label}، USDOL/ETA بوزارة العمل الأمريكية — ترجمةٌ معدّلة، بترخيص CC BY 4.0."
    return f"المصدر: {source.label}، منظمة العمل الدولية — ترجمةٌ معدّلة."


def view(profession: Profession) -> dict:
    """
    البوابة كما تعرضها الواجهة. في بوابةٍ لها أداة يتقدّم ما تؤدّي الأداة جزءاً منه،
    ثم كل نوعٍ بترتيب المصدر؛ وفي بوابةٍ بلا أداة ترتيب المصدر نفسه (أهمية O*NET).
    النصّ الإنجليزي لا يُرسل: للمراجعة في الشيفرة، لا للعرض بالنظر.
    """
    portal = PORTALS[profession]
    if portal.tools:
        tasks = sorted(portal.tasks, key=lambda t: (_MODE_ORDER.index(t.mode), -(t.importance or 0)))
    else:
        tasks = sorted(portal.tasks, key=lambda t: -(t.importance or 0))
    return {
        "profession": profession.value,
        "name": NAMES[profession],
        "summary": portal.summary,
        "tools": list(portal.tools),
        "tasks": [{"text": t.ar, "note": t.note, "mode": t.mode.value} for t in tasks],
        "skills": [{"text": s.name, "note": s.note} for s in portal.skills],
        "sources": {"tasks": source_line(portal, "tasks"), "skills": source_line(portal, "skills"),
                    "summary": source_line(portal, "summary")},
        "attribution": ATTRIBUTION,
        "related": list(portal.related),
    }
