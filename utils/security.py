"""
Security & Privacy Layer — طبقة الأمان والخصوصية
===================================================
Input Validation + Prompt Injection Protection + HIPAA Considerations
"""

import re
import logging
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("rehab_security")


# ═══════════════════════════════════════════════════════════════
# أنماط Prompt Injection المعروفة
# ═══════════════════════════════════════════════════════════════

INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"ignore\s+all\s+(above|prior|previous)",
    r"disregard\s+(all|previous|prior)",
    r"you\s+are\s+now\s+(a|an|the)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+if\s+you",
    r"new\s+system\s+prompt",
    r"<\s*system\s*>",
    r"\[system\]",
    r"###\s*system",
    r"\/\/\s*system",
    r"override\s+(safety|guidelines|restrictions)",
    r"jailbreak",
    r"DAN\s*mode",
    r"developer\s+mode",
]

# أنماط البيانات الحساسة
SENSITIVE_DATA_PATTERNS = [
    (r'\b\d{9,12}\b', '[REDACTED_ID]'),           # أرقام هوية
    (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED_CARD]'),  # بطاقات ائتمان
    (r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]'),  # SSN أمريكي
]


# ═══════════════════════════════════════════════════════════════
# تنظيف المدخلات
# ═══════════════════════════════════════════════════════════════

def sanitize_patient_input(text: str) -> str:
    """
    تنظيف وفحص مدخلات المستخدم

    1. الكشف عن Prompt Injection
    2. إخفاء البيانات الحساسة غير الضرورية
    3. تنظيف النص

    Returns:
        النص المُنظَّف
    """
    if not text or not isinstance(text, str):
        return ""

    original_length = len(text)

    # فحص Prompt Injection
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            logger.warning(
                f"[SECURITY] محاولة Prompt Injection مكتشفة: '{pattern[:50]}'"
            )
            text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE)

    # إخفاء البيانات الشديدة الحساسية
    for pattern, replacement in SENSITIVE_DATA_PATTERNS:
        text = re.sub(pattern, replacement, text)

    # تنظيف أساسي
    # إزالة الأصفار والمسافات الزائدة
    text = text.strip()

    # تسجيل إذا تغير النص
    if len(text) != original_length:
        logger.info(f"[SECURITY] تم تنظيف المدخل: {original_length} → {len(text)} حرف")

    return text


# ═══════════════════════════════════════════════════════════════
# التحقق من مخرجات النظام
# ═══════════════════════════════════════════════════════════════

DISCLAIMER_TEXT = "\n\n---\n⚠️ **تنبيه مهم:** هذا تحليل مساعد من الذكاء الاصطناعي وليس بديلاً عن الرأي الطبي المباشر. يجب مراجعة متخصص مؤهل قبل اتخاذ أي قرار علاجي."

DISCLAIMER_KEYWORDS = [
    "ليس بديلاً",
    "تنبيه",
    "مراجعة طبيب",
    "متخصص",
    "disclaimer",
    "not a substitute",
]


def validate_medical_output(response: str) -> str:
    """
    التحقق من أن الاستجابة الطبية تحتوي على تنبيهات السلامة

    Args:
        response: نص استجابة النظام

    Returns:
        الاستجابة مع إضافة التنبيه إن لم يكن موجوداً
    """
    if not response:
        return response

    # فحص وجود تنبيه
    has_disclaimer = any(
        keyword.lower() in response.lower()
        for keyword in DISCLAIMER_KEYWORDS
    )

    if not has_disclaimer:
        response += DISCLAIMER_TEXT

    return response


# ═══════════════════════════════════════════════════════════════
# Audit Logging
# ═══════════════════════════════════════════════════════════════

def log_interaction(
    session_id: str,
    user_input_length: int,
    tools_used: list,
    response_length: int,
    error: str = None
):
    """
    تسجيل التفاعل للمراجعة (بدون بيانات حساسة)

    لا نسجل محتوى المدخلات/المخرجات — فقط المعلومات التقنية
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "input_length_chars": user_input_length,
        "tools_invoked": tools_used,
        "response_length_chars": response_length,
        "error": error
    }

    if error:
        logger.error(f"[AUDIT] {log_entry}")
    else:
        logger.info(f"[AUDIT] session={session_id}, tools={tools_used}, input_len={user_input_length}")


# ═══════════════════════════════════════════════════════════════
# فحص بيانات المريض
# ═══════════════════════════════════════════════════════════════

def validate_patient_data(data: dict) -> tuple:
    """
    التحقق من صحة بيانات المريض قبل المعالجة

    Returns:
        (is_valid: bool, errors: list)
    """
    errors = []

    # الحقول الاختيارية فقط (لا نفرض حقولاً إلزامية)
    # نتحقق من منطقية القيم الموجودة

    if "age" in data:
        try:
            age = int(data["age"])
            if age < 0 or age > 150:
                errors.append("العمر يجب أن يكون بين 0 و 150")
        except (ValueError, TypeError):
            errors.append("العمر يجب أن يكون رقماً صحيحاً")

    if "visual_acuity" in data:
        va = str(data["visual_acuity"])
        # قبول صيغ متنوعة: 6/60، 0.1، 1.0
        if not re.match(r'^(\d+/\d+|\d+\.?\d*|CF|HM|LP|NLP)$', va.strip()):
            errors.append(f"صيغة حدة الإبصار غير صالحة: {va}")

    return len(errors) == 0, errors


# ═══════════════════════════════════════════════════════════════
# إعدادات HIPAA
# ═══════════════════════════════════════════════════════════════

HIPAA_COMPLIANT_HEADERS = {
    "X-Privacy-Policy": "medical-ai-assistant",
    "X-Data-Retention": "session-only",
}

HIPAA_NOTES = """
ملاحظات HIPAA للاستخدام في البيئات الطبية:
- لا يُخزَّن محتوى المحادثات على خوادم خارجية (Zero Data Retention mode)
- جميع البيانات المنقولة مشفرة عبر TLS 1.2+
- لا يُشارَك أي محتوى مع أطراف ثالثة
- يجب الحصول على موافقة المريض قبل استخدام النظام
- البيانات تُستخدم فقط للجلسة الحالية
- يُنصح بعدم إدخال بيانات تعريفية كاملة (الاسم الكامل + رقم الهوية)
"""
