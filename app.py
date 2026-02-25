"""
مستشار التأهيل الطبي — واجهة المستخدم (Patient-Centric)
Medical Rehabilitation AI Consultant — Streamlit UI
=============================================
"""

import os
import json
import html
import re
import base64
import anthropic
import streamlit as st
from datetime import datetime
from utils.security import sanitize_patient_input, validate_medical_output
from rehab_consultant import SYSTEM_PROMPT, TOOLS, execute_tool, extract_text_response
from orchestrator import RehabOrchestrator
from cdss import run_cdss_evaluation
from assessments import run_assessment
from interventions import run_intervention

# ═══════════════════════════════════════════════════════════════
# Page Config
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="مستشار التأهيل الطبي الذكي",
    page_icon="Re",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

PATIENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "patients")

ICD10_OPTIONS = {
    # Vision
    "H35.30": "AMD — تنكس بقعي مرتبط بالعمر",
    "H35.32": "AMD رطبة — Exudative AMD",
    "H53.46": "Hemianopia — عمى شقي",
    "H35.50": "RP — رتينيتيس بيغمنتوزا",
    "H35.81": "Retinal dystrophy",
    "H40.10": "Glaucoma — جلوكوما",
    "H54.0": "Blindness bilateral — عمى ثنائي",
    "H54.1": "Blindness unilateral",
    "H47.01": "Optic atrophy",
    "H81.3": "CVI — إعاقة بصرية قشرية",
    "H26.9": "Cataract — كتاراكت",
    "H33.0": "Retinal detachment",
    "E11.3": "Diabetic retinopathy",
    # Orthopedic
    "M17.1": "Knee OA — خشونة الركبة",
    "S72.0": "Femoral neck fracture — كسر عنق الفخذ",
    "M54.5": "Low back pain — ألم أسفل الظهر",
    "S83.5": "ACL tear — قطع الرباط الصليبي",
    "M75.1": "Rotator cuff syndrome — متلازمة الكفة المدورة",
    "M16.1": "Hip OA — خشونة مفصل الورك",
    "S42.0": "Clavicle fracture — كسر الترقوة",
    # Neurological
    "I63.9": "Stroke — السكتة الدماغية",
    "S06.9": "TBI — إصابة دماغية رضية",
    "G35": "Multiple Sclerosis — التصلب المتعدد",
    "G20": "Parkinson's — باركنسون",
    "G82.2": "Paraplegia — شلل سفلي",
    "G81.9": "Hemiplegia — شلل نصفي",
    "G51.0": "Bell's palsy — شلل الوجه",
    # Cardiac
    "I25.1": "CAD — مرض الشرايين التاجية",
    "I50.9": "Heart failure — فشل القلب",
    "I21.9": "MI — احتشاء عضلة القلب",
    # Pulmonary
    "J44.1": "COPD — انسداد رئوي مزمن",
    "U07.1": "COVID-19 — كوفيد-19",
    # Pediatric
    "G80.9": "Cerebral palsy — شلل دماغي",
    "Q66.0": "Clubfoot — حنف القدم",
    # Pain
    "G89.4": "Chronic pain — ألم مزمن",
    "M79.7": "Fibromyalgia — فيبروميالجيا",
}

VISION_PATTERNS = [
    "central_scotoma", "hemianopia", "tunnel_vision",
    "total_blindness", "peripheral_loss", "general_blur",
]

FUNCTIONAL_GOALS = [
    # General / ADL
    "ADL", "mobility", "transfers", "stair_climbing",
    "self_care", "dressing", "feeding", "toileting",
    # Upper extremity
    "reaching", "gripping", "fine_motor", "writing",
    # Communication
    "reading", "computer_use", "communication",
    # Social / community
    "face_recognition", "driving", "community_access",
    "return_to_work", "leisure_activities",
    # Vision-specific
    "tv_watching",
    # Cardiopulmonary
    "exercise_tolerance", "endurance",
    # Neuro
    "balance", "coordination", "cognitive_function",
    # Pain
    "pain_management", "sleep_quality",
]

FUNCTIONAL_GOALS_AR = {
    "ADL": "الأنشطة اليومية", "mobility": "التنقل", "transfers": "الانتقالات",
    "stair_climbing": "صعود الدرج", "self_care": "العناية الشخصية",
    "dressing": "ارتداء الملابس", "feeding": "تناول الطعام", "toileting": "استخدام الحمام",
    "reaching": "مد اليد", "gripping": "القبض", "fine_motor": "المهارات الدقيقة",
    "writing": "الكتابة", "reading": "القراءة", "computer_use": "استخدام الحاسوب",
    "communication": "التواصل", "face_recognition": "التعرف على الوجوه",
    "driving": "القيادة", "community_access": "المشاركة المجتمعية",
    "return_to_work": "العودة للعمل", "leisure_activities": "الأنشطة الترفيهية",
    "tv_watching": "مشاهدة التلفاز", "exercise_tolerance": "تحمل التمارين",
    "endurance": "التحمل", "balance": "التوازن", "coordination": "التنسيق",
    "cognitive_function": "الوظائف الإدراكية", "pain_management": "إدارة الألم",
    "sleep_quality": "جودة النوم",
}

TOOLS_MANIFEST = [
    ("VE", "تمارين بصرية SVG", "visual_exercise"),
    ("DB", "قاعدة بيانات المرضى", "patient_database"),
    ("PM", "بحث PubMed", "pubmed"),
    ("CA", "حسابات بصرية", "calculator"),
    ("KB", "قاعدة المعرفة", "knowledge_base"),
    ("DC", "توليد التقارير", "documents"),
    ("FA", "التقييم الوظيفي", "functional_assessment"),
    ("DV", "توصية الأجهزة", "device_recommender"),
    ("AR", "قراءة عربية", "arabic_reading"),
    ("PS", "فحص نفسي", "depression_screening"),
    ("OT", "تتبع النتائج", "outcome_tracker"),
    ("RF", "الإحالة", "referral"),
    ("TR", "توصية التقنيات", "technique_recommender"),
    ("PL", "التعلم الإدراكي", "perceptual_learning"),
    ("EN", "تقييم البيئة", "environmental_assessment"),
    ("TL", "جلسة عن بعد", "telerehab"),
    ("FT", "جلب مقال", "pubmed_fetch"),
    ("RP", "خطة تأهيل", "outcome_plan"),
    ("CD", "تقييم CDSS", "cdss_evaluate"),
    ("CL", "تقييمات سريرية", "clinical_assessment"),
    ("IN", "تدخلات علاجية", "clinical_intervention"),
    ("TP", "خطة علاجية", "treatment_plan"),
]


# ═══════════════════════════════════════════════════════════════
# Patient Storage + Unique File Number System
# ═══════════════════════════════════════════════════════════════

COUNTER_FILE = os.path.join(PATIENTS_DIR, ".counter")


def _read_counter() -> int:
    """قراءة العداد التسلسلي من الملف"""
    os.makedirs(PATIENTS_DIR, exist_ok=True)
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                return int(f.read().strip())
        except (ValueError, OSError):
            pass
    # إذا لم يوجد عداد، نبحث عن أعلى رقم موجود
    max_num = 0
    if os.path.exists(PATIENTS_DIR):
        for fname in os.listdir(PATIENTS_DIR):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(PATIENTS_DIR, fname), "r", encoding="utf-8") as f:
                        p = json.load(f)
                        fnum = p.get("file_number", 0)
                        if isinstance(fnum, int) and fnum > max_num:
                            max_num = fnum
                except (json.JSONDecodeError, KeyError, OSError):
                    pass
    return max_num


def _write_counter(val: int):
    """كتابة العداد التسلسلي"""
    os.makedirs(PATIENTS_DIR, exist_ok=True)
    with open(COUNTER_FILE, "w") as f:
        f.write(str(val))


def generate_patient_id() -> tuple:
    """
    توليد معرف فريد + رقم ملف تسلسلي

    Returns:
        (patient_id: str, file_number: int)
        مثال: ("VR-2026-0001", 1)
    """
    counter = _read_counter() + 1
    _write_counter(counter)
    year = datetime.now().strftime("%Y")
    pid = f"MR-{year}-{counter:04d}"
    return pid, counter


def _sanitize_filename(patient_id: str) -> str:
    return re.sub(r'[^A-Za-z0-9_\-]', '', patient_id)


def save_patient(patient: dict):
    """حفظ ملف المريض كـ JSON"""
    os.makedirs(PATIENTS_DIR, exist_ok=True)
    safe_id = _sanitize_filename(patient["id"])
    path = os.path.join(PATIENTS_DIR, f"{safe_id}.json")
    patient["updated_at"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(patient, f, ensure_ascii=False, indent=2)


def load_all_patients() -> dict:
    """تحميل جميع ملفات المرضى"""
    patients = {}
    if os.path.exists(PATIENTS_DIR):
        for fname in sorted(os.listdir(PATIENTS_DIR)):
            if fname.endswith(".json"):
                path = os.path.join(PATIENTS_DIR, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        p = json.load(f)
                        patients[p["id"]] = p
                except (json.JSONDecodeError, KeyError):
                    pass
    return patients


def load_patient_by_file_number(file_number: int) -> dict:
    """تحميل مريض بناءً على رقم الملف"""
    if os.path.exists(PATIENTS_DIR):
        for fname in os.listdir(PATIENTS_DIR):
            if fname.endswith(".json"):
                path = os.path.join(PATIENTS_DIR, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        p = json.load(f)
                        if p.get("file_number") == file_number:
                            return p
                except (json.JSONDecodeError, KeyError, OSError):
                    pass
    return None


def search_patients(query: str) -> list:
    """بحث في سجلات المرضى بالاسم أو التشخيص أو رقم الملف"""
    results = []
    query_lower = query.lower().strip()
    patients = load_all_patients()
    for pid, p in patients.items():
        # بحث برقم الملف
        if query_lower.isdigit() and p.get("file_number") == int(query_lower):
            results.append(p)
            continue
        # بحث بمعرف المريض
        if query_lower in pid.lower():
            results.append(p)
            continue
        # بحث بالاسم
        if query_lower in p.get("name", "").lower() or query_lower in p.get("name_en", "").lower():
            results.append(p)
            continue
        # بحث بالتشخيص
        if query_lower in p.get("diagnosis_text", "").lower():
            results.append(p)
            continue
        # بحث بـ ICD-10
        for icd in p.get("diagnosis_icd10", []):
            if query_lower in icd.lower():
                results.append(p)
                break
    return results


def get_patient_summary(patient: dict) -> dict:
    """استخراج ملخص المريض بدون بيانات ضخمة (محادثات/تفاصيل)"""
    summary = {
        "id": patient.get("id"),
        "file_number": patient.get("file_number"),
        "name": patient.get("name"),
        "name_en": patient.get("name_en"),
        "age": patient.get("age"),
        "gender": patient.get("gender"),
        "rehabilitation_type": patient.get("rehabilitation_type", ""),
        "diagnosis_text": patient.get("diagnosis_text"),
        "diagnosis_icd10": patient.get("diagnosis_icd10", []),
        "cognitive_status": patient.get("cognitive_status"),
        "functional_goals": patient.get("functional_goals", []),
        "phq9_score": patient.get("phq9_score"),
        "num_assessments": len(patient.get("assessment_results", [])),
        "num_interventions": len(patient.get("intervention_sessions", [])),
        "num_notes": len(patient.get("notes", [])),
        "num_cdss": len(patient.get("cdss_evaluations", [])),
        "num_documents": len(patient.get("documents", [])),
        "num_treatment_plans": len(patient.get("treatment_plans", [])),
        "created_at": patient.get("created_at"),
        "updated_at": patient.get("updated_at"),
    }
    # Include specialty-specific fields
    rehab_type = patient.get("rehabilitation_type", "")
    if rehab_type == "vision":
        summary["va_logmar"] = patient.get("va_logmar")
        summary["va_snellen"] = patient.get("va_snellen")
        summary["visual_field_degrees"] = patient.get("visual_field_degrees")
        summary["vision_pattern"] = patient.get("vision_pattern")
    if rehab_type in ("orthopedic", "neuro", "pain"):
        pain_scores = patient.get("pain_scores", [])
        summary["last_pain_score"] = pain_scores[-1]["value"] if pain_scores else None
    if rehab_type == "neuro":
        summary["affected_side"] = patient.get("affected_side", "")
    if rehab_type == "cardiac":
        summary["nyha_class"] = patient.get("nyha_class", "")
    return summary


def delete_patient(patient_id: str):
    """حذف ملف مريض"""
    safe_id = _sanitize_filename(patient_id)
    path = os.path.join(PATIENTS_DIR, f"{safe_id}.json")
    if os.path.exists(path):
        os.remove(path)


def new_patient_template(pid: str, file_number: int) -> dict:
    """إنشاء قالب مريض جديد مع رقم ملف فريد"""
    now = datetime.now().isoformat()
    return {
        "id": pid, "file_number": file_number,
        "name": "", "name_en": "", "age": 0, "gender": "male",
        "diagnosis_icd10": [], "diagnosis_text": "", "va_logmar": None,
        "va_snellen": "", "visual_field_degrees": None, "phq9_score": None,
        "vision_pattern": "", "cognitive_status": "normal",
        "functional_goals": [], "notes": [], "assessment_results": [],
        "intervention_sessions": [], "cdss_evaluations": [], "documents": [],
        "chat_history": [], "created_at": now, "updated_at": now,
        "rehabilitation_type": "",
        "treatment_plans": [],
        "pain_scores": [],
        "rom_measurements": [],
        "strength_measurements": [],
        "balance_scores": [],
        "functional_scores": [],
        "affected_side": "",
        "nyha_class": "",
    }


# ═══════════════════════════════════════════════════════════════
# Session State
# ═══════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "current_page": "registry",
        "current_patient_id": None,
        "patients": {},
        "thinking_budget": 8000,
        "use_thinking": True,
        "pending_query": None,
        "show_new_patient_form": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Load patients from disk on first run
    if not st.session_state.patients:
        st.session_state.patients = load_all_patients()


init_session()


# ═══════════════════════════════════════════════════════════════
# Custom CSS
# ═══════════════════════════════════════════════════════════════

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&family=Tajawal:wght@300;400;500;700;800&display=swap');
:root {
    --primary: #1E3A5F; --primary-light: #2E5B8C;
    --secondary: #2E8BC0; --secondary-light: #4FA8D8;
    --accent: #0B8457; --accent-light: #10A567;
    --bg: #EEF2F7; --card: #FFFFFF;
    --text: #1A2744; --text-sub: #4A5568; --text-muted: #718096;
    --border: #E2E8F0; --border-focus: #2E8BC0;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
    --shadow: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.04);
    --shadow-md: 0 10px 25px -5px rgba(0,0,0,0.08), 0 4px 10px -5px rgba(0,0,0,0.04);
    --shadow-lg: 0 20px 40px -10px rgba(0,0,0,0.1);
    --radius-sm: 8px; --radius: 12px; --radius-lg: 20px; --radius-xl: 28px;
}
*, *::before, *::after { box-sizing: border-box; }
html, body, .stApp, [class*="css"] {
    font-family: 'Cairo', 'Tajawal', -apple-system, sans-serif !important; direction: rtl;
}
.stApp {
    background: var(--bg) !important;
    position: relative;
    overflow-x: hidden;
}

/* ── Animated Background ── */
.stApp::before {
    content: '';
    position: fixed;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background:
        radial-gradient(ellipse at 20% 50%, rgba(46,139,192,0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(11,132,87,0.05) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 80%, rgba(30,58,95,0.04) 0%, transparent 50%);
    animation: bgDrift 20s ease-in-out infinite alternate;
    z-index: 0;
    pointer-events: none;
}
@keyframes bgDrift {
    0%   { transform: translate(0, 0) rotate(0deg); }
    33%  { transform: translate(2%, -1%) rotate(1deg); }
    66%  { transform: translate(-1%, 2%) rotate(-0.5deg); }
    100% { transform: translate(1%, -2%) rotate(0.5deg); }
}

/* ── Floating Particles ── */
.stApp::after {
    content: '';
    position: fixed;
    width: 100%; height: 100%;
    top: 0; left: 0;
    background-image:
        radial-gradient(2px 2px at 10% 20%, rgba(46,139,192,0.15) 50%, transparent 50%),
        radial-gradient(2px 2px at 30% 70%, rgba(11,132,87,0.12) 50%, transparent 50%),
        radial-gradient(3px 3px at 60% 30%, rgba(30,58,95,0.1) 50%, transparent 50%),
        radial-gradient(2px 2px at 80% 60%, rgba(46,139,192,0.12) 50%, transparent 50%),
        radial-gradient(2px 2px at 50% 90%, rgba(11,132,87,0.1) 50%, transparent 50%),
        radial-gradient(3px 3px at 90% 10%, rgba(30,58,95,0.08) 50%, transparent 50%);
    animation: particleFloat 30s linear infinite;
    z-index: 0;
    pointer-events: none;
}
@keyframes particleFloat {
    0%   { transform: translateY(0); }
    100% { transform: translateY(-100vh); }
}

#MainMenu, footer, header, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }

/* SIDEBAR */
[data-testid="stSidebar"] {
    background: linear-gradient(170deg, #142540 0%, #1E3A5F 60%, #1A3252 100%) !important;
    border-left: 1px solid rgba(255,255,255,0.06) !important; min-width: 280px !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebar"] .block-container { padding: 0 !important; }
.sb-header {
    background: linear-gradient(135deg, rgba(46,139,192,0.25) 0%, rgba(11,132,87,0.15) 100%);
    border-bottom: 1px solid rgba(255,255,255,0.08); padding: 28px 20px 22px; text-align: center;
}
.sb-logo-wrap { display: flex; justify-content: center; margin-bottom: 10px;
    filter: drop-shadow(0 4px 20px rgba(46,139,192,0.55)); }
.ai-loading { display: flex; gap: 6px; justify-content: center; align-items: center; padding: 20px 0; }
.ai-loading-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--secondary); opacity: 0.3; }
.ai-loading-dot:nth-child(1) { animation: aiDot 1.2s ease-in-out 0s infinite; }
.ai-loading-dot:nth-child(2) { animation: aiDot 1.2s ease-in-out 0.2s infinite; }
.ai-loading-dot:nth-child(3) { animation: aiDot 1.2s ease-in-out 0.4s infinite; }
@keyframes aiDot { 0%,80%,100% { transform: scale(1); opacity:0.3; } 40% { transform: scale(1.6); opacity:1; } }
.visual-exercise-card {
    background: linear-gradient(135deg, rgba(30,58,95,0.9) 0%, rgba(11,50,40,0.9) 100%);
    border: 2px solid rgba(46,139,192,0.5); border-radius: var(--radius-lg);
    padding: 18px; margin: 14px 0 6px; box-shadow: var(--shadow-md);
}
.ve-header { font-weight: 800; font-size: 15px; color: #60C4F0; margin-bottom: 8px; }
.ve-instructions { font-size: 13px; color: rgba(255,255,255,0.75); margin-bottom: 14px; line-height: 1.6; }
.ve-svg { text-align: center; }
.ve-svg svg { max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
.ve-footer { font-size: 11px; color: rgba(255,255,255,0.4); margin-top: 10px; display: flex; gap: 12px; }
.sb-title { color: #FFF; font-size: 15px; font-weight: 800; margin: 0 0 4px; }
.sb-subtitle { color: rgba(255,255,255,0.45); font-size: 10px; font-weight: 500;
    letter-spacing: 0.5px; text-transform: uppercase; margin: 0; }
.sb-model-badge {
    display: inline-flex; align-items: center; gap: 5px; margin-top: 10px; padding: 4px 10px;
    background: rgba(46,139,192,0.25); border: 1px solid rgba(46,139,192,0.4);
    border-radius: 20px; font-size: 10px; color: #60C4F0; font-weight: 600;
}
.sb-body { padding: 16px 14px; }
.sb-section-label { color: rgba(255,255,255,0.35); font-size: 9px; font-weight: 700;
    letter-spacing: 2px; text-transform: uppercase; margin: 18px 0 8px 4px; }
.sb-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 4px; }
.sb-stat { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
    border-radius: var(--radius-sm); padding: 12px 8px; text-align: center; transition: background 0.2s; }
.sb-stat:hover { background: rgba(255,255,255,0.1); }
.sb-stat-num { color: #60C4F0; font-size: 22px; font-weight: 900; line-height: 1; display: block; }
.sb-stat-lbl { color: rgba(255,255,255,0.45); font-size: 9px; font-weight: 500; display: block; margin-top: 4px; }
.tool-chip { display: flex; align-items: center; gap: 9px; padding: 8px 10px;
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.07);
    border-radius: var(--radius-sm); margin-bottom: 5px; transition: all 0.2s; cursor: default; }
.tool-chip:hover { background: rgba(255,255,255,0.09); border-color: rgba(255,255,255,0.14); transform: translateX(-2px); }
.tool-chip-icon { font-size: 13px; width: 18px; text-align: center; flex-shrink: 0; }
.tool-chip-name { color: rgba(255,255,255,0.75); font-size: 11px; font-weight: 500; flex: 1; }
.tool-chip-badge { font-size: 8px; padding: 2px 6px; border-radius: 10px; font-weight: 700;
    background: rgba(16,185,129,0.18); color: #34D399; border: 1px solid rgba(16,185,129,0.25); }
.sb-divider { height: 1px; background: rgba(255,255,255,0.07); margin: 14px 0; }
[data-testid="stSidebar"] .stButton > button {
    font-family: 'Cairo', sans-serif !important; background: rgba(220,38,38,0.12) !important;
    color: rgba(252,165,165,0.9) !important; border: 1px solid rgba(220,38,38,0.25) !important;
    border-radius: var(--radius-sm) !important; font-size: 12px !important; font-weight: 600 !important;
    width: 100% !important; padding: 8px 16px !important; transition: all 0.2s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(220,38,38,0.22) !important; border-color: rgba(220,38,38,0.4) !important;
}

/* MAIN CONTENT */
.main .block-container { max-width: 960px !important; padding: 0 24px 24px !important; margin: 0 auto !important; }

/* PAGE HEADER */
.page-header {
    background: linear-gradient(135deg, #1E3A5F 0%, #2A6496 50%, #1A7A58 100%);
    border-radius: 0 0 var(--radius-xl) var(--radius-xl);
    padding: 26px 32px 22px; margin: 0 -24px 24px; display: flex;
    align-items: center; justify-content: space-between; box-shadow: var(--shadow-md);
}
.ph-left { display: flex; align-items: center; gap: 16px; }
.ph-icon { font-size: 38px; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.3)); }
.ph-title { color: white; font-size: 20px; font-weight: 800; margin: 0 0 3px; line-height: 1.2; }
.ph-sub { color: rgba(255,255,255,0.65); font-size: 11px; font-weight: 500; margin: 0; }
.ph-badges { display: flex; gap: 8px; flex-direction: column; align-items: flex-end; }
.badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px;
    border-radius: 16px; font-size: 10px; font-weight: 700; white-space: nowrap; }
.badge-green { background: rgba(16,185,129,0.2); color: #6EE7B7; border: 1px solid rgba(16,185,129,0.3); }
.badge-blue { background: rgba(96,165,250,0.2); color: #93C5FD; border: 1px solid rgba(96,165,250,0.3); }
.badge-red { background: rgba(239,68,68,0.2); color: #FCA5A5; border: 1px solid rgba(239,68,68,0.3); }

/* PATIENT HEADER */
.patient-header {
    background: linear-gradient(135deg, #1E3A5F, #2E5B8C);
    border-radius: var(--radius); padding: 18px 24px; margin-bottom: 16px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: var(--shadow); color: white;
}
.patient-header .ph-name { font-size: 18px; font-weight: 800; margin: 0; }
.patient-header .ph-meta { font-size: 12px; color: rgba(255,255,255,0.7); margin-top: 4px; }
.patient-header .ph-badges { display: flex; gap: 6px; }

/* PATIENT CARD (Registry) */
.patient-card {
    background: var(--card); border: 2px solid var(--border); border-radius: var(--radius);
    padding: 18px; transition: all 0.25s; box-shadow: var(--shadow-sm);
}
.patient-card:hover { border-color: var(--secondary); box-shadow: var(--shadow); transform: translateY(-2px); }
.patient-card-name { font-size: 16px; font-weight: 700; color: var(--primary); margin: 0 0 6px; }
.patient-card-dx { font-size: 12px; color: var(--text-sub); margin: 0 0 4px; }
.patient-card-meta { font-size: 10px; color: var(--text-muted); }

/* CHAT MESSAGES */
.msg-user { display: flex; justify-content: flex-end; align-items: flex-end; gap: 10px; animation: msgIn 0.3s ease-out; }
.msg-ai { display: flex; justify-content: flex-start; align-items: flex-end; gap: 10px; animation: msgIn 0.3s ease-out; }
@keyframes msgIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.avatar { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 20px; flex-shrink: 0; box-shadow: var(--shadow); }
.avatar-user { background: linear-gradient(135deg, #1E3A5F, #2E8BC0); order: 1; }
.avatar-ai { background: linear-gradient(135deg, #0B5E3D, #0B8457); order: -1; }
.bubble { max-width: 76%; padding: 14px 18px; font-size: 14px; line-height: 1.75;
    color: var(--text); box-shadow: var(--shadow); position: relative; word-break: break-word; }
.bubble-user { background: linear-gradient(145deg, #EBF5FB, #D6EAF8); border: 1px solid #AED6F1;
    border-radius: var(--radius) var(--radius-sm) var(--radius) var(--radius); order: 0; }
.bubble-ai { background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius-sm) var(--radius) var(--radius) var(--radius); order: 0; }
.bubble-footer { display: flex; align-items: center; justify-content: flex-end; gap: 6px;
    margin-top: 8px; font-size: 10px; color: var(--text-muted); }
.bubble-footer-ai { justify-content: flex-start; }
.bubble h1,.bubble h2,.bubble h3 { color: var(--primary); }
.bubble h1 { font-size: 17px; } .bubble h2 { font-size: 15px; } .bubble h3 { font-size: 13px; }
.bubble p { margin: 0 0 8px; } .bubble p:last-child { margin-bottom: 0; }
.bubble ul,.bubble ol { padding-right: 18px; margin: 6px 0; } .bubble li { margin-bottom: 4px; }
.bubble table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 10px 0;
    border-radius: var(--radius-sm); overflow: hidden; }
.bubble th { background: var(--primary); color: white; padding: 8px 12px; font-weight: 700; font-size: 11px; }
.bubble td { padding: 7px 12px; border-bottom: 1px solid var(--border); }
.bubble tr:nth-child(even) td { background: #F7FAFC; }
.bubble code { background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 4px; padding: 1px 5px;
    font-size: 12px; font-family: monospace; direction: ltr; display: inline-block; }
.bubble pre { background: #1E293B; border-radius: var(--radius-sm); padding: 12px; overflow-x: auto; direction: ltr; }
.bubble pre code { background: none; border: none; color: #E2E8F0; }
.bubble blockquote { border-right: 4px solid var(--secondary); background: #EBF8FF;
    margin: 8px 0; padding: 8px 14px; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; color: var(--text-sub); }
.bubble strong { color: var(--primary); } .bubble a { color: var(--secondary); }

/* TOOL CALL */
.tool-call-card { background: linear-gradient(135deg, #FFFBEB, #FEF3C7); border: 1px solid #F59E0B;
    border-radius: var(--radius-sm); padding: 10px 14px; margin: 6px 0; font-size: 12px; }
.tool-call-header { display: flex; align-items: center; gap: 6px; color: #92400E; font-weight: 700;
    margin-bottom: 4px; font-size: 11px; text-transform: uppercase; }
.tool-call-name { font-size: 12px; color: #78350F; font-weight: 600; font-family: monospace;
    background: rgba(0,0,0,0.06); padding: 2px 6px; border-radius: 4px; }

/* THINKING */
.thinking-card { background: linear-gradient(135deg, #FAF5FF, #EDE9FE); border: 1px solid #A78BFA;
    border-radius: var(--radius-sm); padding: 12px 16px; margin: 6px 0; display: flex; align-items: center; gap: 10px; }
.thinking-text { color: #5B21B6; font-size: 12px; font-weight: 600; }
.thinking-dots { display: inline-flex; gap: 5px; }
.thinking-dots span { width: 7px; height: 7px; background: #7C3AED; border-radius: 50%; animation: thinkBounce 1.4s infinite ease-in-out; }
.thinking-dots span:nth-child(2) { animation-delay: 0.16s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.32s; }
@keyframes thinkBounce { 0%,80%,100% { transform: scale(0.5); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

/* INPUT */
.input-wrapper { position: sticky; bottom: 0; z-index: 100; padding: 12px 0 4px;
    background: linear-gradient(to top, var(--bg) 75%, transparent 100%); }
.input-card { background: var(--card); border: 2px solid var(--border); border-radius: var(--radius-xl);
    padding: 12px 16px 10px; box-shadow: var(--shadow-md); transition: border-color 0.25s, box-shadow 0.25s; }
.input-card:focus-within { border-color: var(--secondary); box-shadow: 0 0 0 4px rgba(46,139,192,0.1), var(--shadow-md); }
[data-testid="stTextArea"] { margin: 0 !important; }
[data-testid="stTextArea"] > div { border: none !important; box-shadow: none !important; background: transparent !important; }
[data-testid="stTextArea"] textarea { font-family: 'Cairo', sans-serif !important; font-size: 14px !important;
    direction: rtl !important; border: none !important; box-shadow: none !important;
    background: transparent !important; resize: none !important; color: var(--text) !important;
    padding: 4px 0 !important; min-height: 46px !important; }
[data-testid="stTextArea"] textarea::placeholder { color: var(--text-muted) !important; }
.send-col .stButton > button { font-family: 'Cairo', sans-serif !important;
    background: linear-gradient(135deg, #1E3A5F, #2E5B8C) !important; color: white !important;
    border: none !important; border-radius: var(--radius) !important; font-size: 13px !important;
    font-weight: 700 !important; padding: 8px 20px !important; width: 100% !important;
    box-shadow: 0 3px 10px rgba(30,58,95,0.35) !important; }
.send-col .stButton > button:hover { background: linear-gradient(135deg, #2E5B8C, #3A79B8) !important; }
.clear-col .stButton > button { font-family: 'Cairo', sans-serif !important;
    background: transparent !important; color: var(--text-muted) !important;
    border: 1px solid var(--border) !important; border-radius: var(--radius) !important;
    font-size: 12px !important; font-weight: 600 !important; padding: 8px 14px !important; width: 100% !important; }
.clear-col .stButton > button:hover { background: #FEF2F2 !important; border-color: #FECACA !important; color: #DC2626 !important; }

/* NOTE CARD */
.note-card { background: white; border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 14px; margin-bottom: 10px; box-shadow: var(--shadow-sm); }
.note-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.note-card-type { font-size: 10px; font-weight: 700; color: var(--secondary); text-transform: uppercase; }
.note-card-time { font-size: 10px; color: var(--text-muted); }
.note-card-body { font-size: 13px; color: var(--text); line-height: 1.6; }

/* WELCOME */
.welcome-container { text-align: center; padding: 40px 20px 20px; }
.welcome-emoji { font-size: 80px; display: block; margin-bottom: 20px; animation: welcomeFloat 3.5s ease-in-out infinite; }
@keyframes welcomeFloat { 0%,100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-12px) scale(1.03); } }
.welcome-title { color: var(--primary); font-size: 28px; font-weight: 900; margin: 0 0 8px; }
.welcome-subtitle { color: var(--text-sub); font-size: 15px; margin: 0 0 32px;
    max-width: 520px; margin-left: auto; margin-right: auto; line-height: 1.7; }
.feature-row { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-bottom: 36px; }
.feature-chip { display: flex; align-items: center; gap: 6px; padding: 6px 14px; background: white;
    border: 1px solid var(--border); border-radius: 20px; font-size: 12px; color: var(--text-sub);
    font-weight: 500; box-shadow: var(--shadow-sm); }
.examples-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 12px; max-width: 760px; margin: 0 auto; }

/* ALERTS */
.alert { padding: 12px 16px; border-radius: var(--radius-sm); font-size: 13px;
    display: flex; align-items: flex-start; gap: 10px; margin: 8px 0; }
.alert-info { background: #EBF8FF; border: 1px solid #BEE3F8; color: #2C5282; }
.alert-warning { background: #FFFBEB; border: 1px solid #FCD34D; color: #78350F; }
.alert-success { background: #F0FFF4; border: 1px solid #9AE6B4; color: #22543D; }
.alert-danger { background: #FFF5F5; border: 1px solid #FEB2B2; color: #742A2A; }

/* ── Glassmorphism Cards ── */
.glass-card {
    background: rgba(255,255,255,0.75);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.4);
    border-radius: var(--radius);
    box-shadow: var(--shadow), 0 0 40px rgba(46,139,192,0.04);
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.glass-card:hover {
    box-shadow: var(--shadow-lg), 0 0 60px rgba(46,139,192,0.08);
    transform: translateY(-3px);
    border-color: rgba(46,139,192,0.2);
}

/* ── Enhanced Patient Cards ── */
.patient-card {
    background: rgba(255,255,255,0.82);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    border: 2px solid transparent;
    border-image: linear-gradient(135deg, var(--border) 0%, rgba(46,139,192,0.15) 100%) 1;
    border-image-slice: 1;
    border-radius: var(--radius); border-image: none;
    border: 2px solid var(--border);
    padding: 20px; transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--shadow-sm); position: relative; overflow: hidden;
}
.patient-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--secondary), var(--accent), var(--secondary));
    opacity: 0; transition: opacity 0.3s;
}
.patient-card:hover { border-color: var(--secondary-light); box-shadow: var(--shadow-md), 0 4px 30px rgba(46,139,192,0.1); transform: translateY(-4px); }
.patient-card:hover::before { opacity: 1; }
.patient-card-name { font-size: 17px; font-weight: 800; color: var(--primary); margin: 0 0 8px; letter-spacing: -0.3px; }
.patient-card-dx { font-size: 12px; color: var(--text-sub); margin: 0 0 6px; line-height: 1.5; }
.patient-card-meta { font-size: 10px; color: var(--text-muted); display: flex; gap: 8px; align-items: center; }

/* ── Enhanced Patient Header ── */
.patient-header {
    background: linear-gradient(135deg, #1E3A5F 0%, #2A5F8C 40%, #1A7A58 100%);
    border-radius: var(--radius-lg); padding: 22px 28px; margin-bottom: 20px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: var(--shadow-md), 0 4px 30px rgba(30,58,95,0.2); color: white;
    position: relative; overflow: hidden;
}
.patient-header::before {
    content: ''; position: absolute; top: -50%; right: -20%; width: 60%; height: 200%;
    background: radial-gradient(ellipse, rgba(255,255,255,0.06) 0%, transparent 70%);
    animation: headerShine 6s ease-in-out infinite alternate;
}
@keyframes headerShine {
    0% { transform: translateX(-20%); } 100% { transform: translateX(20%); }
}
.patient-header .ph-name { font-size: 19px; font-weight: 800; margin: 0; position: relative; z-index: 1; }
.patient-header .ph-meta { font-size: 12px; color: rgba(255,255,255,0.75); margin-top: 6px; position: relative; z-index: 1; }
.patient-header .ph-badges { display: flex; gap: 6px; position: relative; z-index: 1; }

/* ── Workflow Progress Bar ── */
.workflow-progress {
    display: flex; gap: 4px; padding: 12px 20px; margin-bottom: 16px;
    background: rgba(255,255,255,0.7); backdrop-filter: blur(8px);
    border-radius: var(--radius); border: 1px solid var(--border); box-shadow: var(--shadow-sm);
}
.workflow-step {
    flex: 1; text-align: center; padding: 8px 4px; border-radius: var(--radius-sm);
    font-size: 10px; font-weight: 600; color: var(--text-muted); transition: all 0.3s;
    position: relative;
}
.workflow-step.active {
    background: linear-gradient(135deg, rgba(46,139,192,0.12), rgba(11,132,87,0.08));
    color: var(--primary); box-shadow: 0 2px 8px rgba(46,139,192,0.12);
}
.workflow-step.done {
    background: rgba(16,185,129,0.08); color: var(--accent);
}
.workflow-step-icon { font-size: 18px; display: block; margin-bottom: 4px; }
.workflow-step-label { display: block; }
.workflow-step-connector {
    position: absolute; top: 50%; left: -8px; width: 12px; height: 2px;
    background: var(--border);
}
.workflow-step.done .workflow-step-connector { background: var(--accent); }

/* ── Metric Cards ── */
.metric-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.metric-card {
    background: rgba(255,255,255,0.8); backdrop-filter: blur(8px);
    border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 14px;
    text-align: center; transition: all 0.3s; position: relative; overflow: hidden;
}
.metric-card::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--secondary), var(--accent));
    opacity: 0.5; transition: opacity 0.3s;
}
.metric-card:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
.metric-card:hover::after { opacity: 1; }
.metric-num { font-size: 28px; font-weight: 900; color: var(--primary); line-height: 1; display: block; }
.metric-label { font-size: 11px; color: var(--text-muted); font-weight: 600; margin-top: 6px; display: block; }

/* ── Quick Actions ── */
.quick-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0; }
.quick-action-btn {
    display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
    background: rgba(255,255,255,0.8); border: 1px solid var(--border);
    border-radius: 20px; font-size: 12px; font-weight: 600; color: var(--text-sub);
    cursor: pointer; transition: all 0.25s; text-decoration: none;
}
.quick-action-btn:hover {
    background: linear-gradient(135deg, rgba(46,139,192,0.08), rgba(11,132,87,0.06));
    border-color: var(--secondary); color: var(--primary); transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(46,139,192,0.1);
}

/* ── Enhanced Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important; background: rgba(255,255,255,0.5) !important;
    padding: 4px !important; border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--radius-sm) !important; font-family: 'Cairo', sans-serif !important;
    font-size: 13px !important; font-weight: 600 !important; padding: 8px 12px !important;
    color: var(--text-muted) !important; transition: all 0.25s !important;
}
.stTabs [data-baseweb="tab"]:hover {
    background: rgba(46,139,192,0.06) !important; color: var(--primary) !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(46,139,192,0.12), rgba(11,132,87,0.08)) !important;
    color: var(--primary) !important; box-shadow: 0 2px 8px rgba(46,139,192,0.1) !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: linear-gradient(90deg, var(--secondary), var(--accent)) !important;
    height: 3px !important; border-radius: 2px !important;
}
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── Enhanced Buttons ── */
.stButton > button[kind="primary"], .stButton > button[data-testid*="primary"] {
    font-family: 'Cairo', sans-serif !important;
    background: linear-gradient(135deg, #1E3A5F 0%, #2E5B8C 100%) !important;
    color: white !important; border: none !important;
    border-radius: var(--radius) !important; font-weight: 700 !important;
    padding: 8px 20px !important; box-shadow: 0 4px 15px rgba(30,58,95,0.3) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #2E5B8C 0%, #3A79B8 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(30,58,95,0.4) !important;
}
.stButton > button:not([kind="primary"]) {
    font-family: 'Cairo', sans-serif !important; border-radius: var(--radius-sm) !important;
    transition: all 0.25s !important; font-weight: 600 !important;
}
.stButton > button:not([kind="primary"]):hover { transform: translateY(-1px) !important; }

/* ── Enhanced Form Inputs ── */
.stTextInput > div > div, .stNumberInput > div > div, .stSelectbox > div > div {
    border-radius: var(--radius-sm) !important;
    border-color: var(--border) !important;
    transition: all 0.25s !important;
    font-family: 'Cairo', sans-serif !important;
}
.stTextInput > div > div:focus-within, .stNumberInput > div > div:focus-within,
.stSelectbox > div > div:focus-within {
    border-color: var(--secondary) !important;
    box-shadow: 0 0 0 3px rgba(46,139,192,0.1) !important;
}

/* ── Enhanced Expanders ── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    background: rgba(255,255,255,0.8) !important;
    backdrop-filter: blur(6px) !important;
    box-shadow: var(--shadow-sm) !important;
    transition: all 0.3s !important;
}
[data-testid="stExpander"]:hover {
    box-shadow: var(--shadow) !important; border-color: rgba(46,139,192,0.15) !important;
}
[data-testid="stExpander"] summary {
    font-family: 'Cairo', sans-serif !important; font-weight: 700 !important;
}

/* ── Enhanced Note Cards ── */
.note-card {
    background: rgba(255,255,255,0.85); backdrop-filter: blur(6px);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px; margin-bottom: 12px; box-shadow: var(--shadow-sm);
    transition: all 0.25s; position: relative; overflow: hidden;
    border-right: 4px solid var(--secondary);
}
.note-card:hover { box-shadow: var(--shadow); transform: translateX(-3px); }

/* ── API Status Pulse ── */
@keyframes statusPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.4); }
    50% { box-shadow: 0 0 0 8px rgba(16,185,129,0); }
}
.badge-green { animation: statusPulse 2s infinite; }

/* ── Activity Timeline ── */
.activity-item {
    display: flex; align-items: flex-start; gap: 12px; padding: 10px 0;
    border-bottom: 1px solid rgba(226,232,240,0.5); position: relative;
}
.activity-item::before {
    content: ''; position: absolute; right: 5px; top: 0; bottom: 0; width: 2px;
    background: linear-gradient(to bottom, var(--secondary), transparent);
}
.activity-dot {
    width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: 4px;
    background: var(--secondary); box-shadow: 0 0 0 3px rgba(46,139,192,0.15);
}
.activity-content { flex: 1; }
.activity-type { font-size: 11px; font-weight: 700; color: var(--primary); }
.activity-desc { font-size: 12px; color: var(--text-sub); margin-top: 2px; }
.activity-time { font-size: 10px; color: var(--text-muted); }

/* ── Info Section ── */
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.info-item {
    padding: 10px 14px; background: rgba(238,242,247,0.6); border-radius: var(--radius-sm);
    border: 1px solid rgba(226,232,240,0.5);
}
.info-label { font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.info-value { font-size: 14px; font-weight: 600; color: var(--primary); margin-top: 2px; }

/* ── Page Header Enhanced ── */
.page-header {
    background: linear-gradient(135deg, #1E3A5F 0%, #2A6496 40%, #1A7A58 80%, #0B8457 100%);
    border-radius: 0 0 var(--radius-xl) var(--radius-xl);
    padding: 28px 34px 24px; margin: 0 -24px 28px; display: flex;
    align-items: center; justify-content: space-between;
    box-shadow: var(--shadow-lg), 0 6px 40px rgba(30,58,95,0.15);
    position: relative; overflow: hidden;
}
.page-header::before {
    content: ''; position: absolute; top: -50%; right: -30%; width: 80%; height: 200%;
    background: radial-gradient(ellipse, rgba(255,255,255,0.05) 0%, transparent 60%);
    animation: headerShine 8s ease-in-out infinite alternate;
}

/* SCROLLBAR */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: linear-gradient(to bottom, #CBD5E0, #A0AEC0); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: linear-gradient(to bottom, #A0AEC0, #718096); }

/* ── Empty State ── */
.empty-state {
    text-align: center; padding: 40px 20px;
    background: rgba(255,255,255,0.5); border-radius: var(--radius-lg);
    border: 2px dashed var(--border);
}
.empty-state-icon { font-size: 60px; display: block; margin-bottom: 16px; opacity: 0.6; }
.empty-state-text { color: var(--text-muted); font-size: 14px; }

/* ── Loading Skeleton ── */
@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
.skeleton {
    background: linear-gradient(90deg, #EEF2F7 25%, #E2E8F0 50%, #EEF2F7 75%);
    background-size: 200% 100%; animation: shimmer 1.5s infinite;
    border-radius: var(--radius-sm);
}

/* RESPONSIVE */
@media (max-width: 768px) {
    .bubble { max-width: 92%; } .page-header { padding: 18px 20px; }
    .ph-title { font-size: 16px; } .ph-badges { display: none; }
    .metric-row { grid-template-columns: repeat(2, 1fr); }
    .workflow-progress { flex-wrap: wrap; }
    .info-grid { grid-template-columns: 1fr; }
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# Chat Backend — Patient-Aware
# ═══════════════════════════════════════════════════════════════

def build_patient_system_context(patient: dict) -> str:
    goals = ", ".join(patient.get("functional_goals", [])) or "لم تُحدد"
    icd = ", ".join(patient.get("diagnosis_icd10", [])) or "—"
    fnum = patient.get("file_number", "—")

    # تضمين آخر التقييمات والملاحظات
    recent_notes = ""
    for note in patient.get("notes", [])[-3:]:
        recent_notes += f"  - [{note.get('type', '')}] {note.get('content', '')[:80]}\n"
    recent_assess = ""
    for a in patient.get("assessment_results", [])[-3:]:
        atype = a.get("type", "")
        ts = a.get("timestamp", "")[:10]
        recent_assess += f"  - {atype} ({ts})\n"
    recent_sessions = ""
    for s in patient.get("intervention_sessions", [])[-3:]:
        stype = s.get("type", "")
        ts = s.get("timestamp", "")[:10]
        recent_sessions += f"  - {stype} ({ts})\n"

    rehab_type = patient.get("rehabilitation_type", "") or "غير محدد"
    treatment_plans_count = len(patient.get("treatment_plans", []))
    active_plans = [p for p in patient.get("treatment_plans", []) if p.get("status") == "active"]

    recent_plans = ""
    for plan in active_plans[-2:]:
        recent_plans += f"  - {plan.get('plan_title', '')} ({plan.get('rehabilitation_type', '')})\n"

    ctx = (
        f"\n\n--- سياق المريض الحالي ---\n"
        f"رقم الملف: {fnum}\n"
        f"معرف المريض: {patient.get('id', '')}\n"
        f"الاسم: {patient.get('name', '')}\n"
        f"العمر: {patient.get('age', '—')}\n"
        f"الجنس: {'ذكر' if patient.get('gender') == 'male' else 'أنثى'}\n"
        f"نوع التأهيل: {rehab_type}\n"
        f"التشخيص: {patient.get('diagnosis_text', '')} ({icd})\n"
    )
    # Specialty-specific context
    rt = patient.get("rehabilitation_type", "")
    if rt == "vision":
        ctx += (
            f"حدة الإبصار: {patient.get('va_logmar', '—')} LogMAR\n"
            f"مجال الرؤية: {patient.get('visual_field_degrees', '—')} درجة\n"
            f"نمط الفقد: {patient.get('vision_pattern', '—')}\n"
        )
    if rt in ("orthopedic", "neuro", "pain"):
        pain_scores = patient.get("pain_scores", [])
        last_pain = pain_scores[-1]["value"] if pain_scores else "لم يُقيَّم"
        ctx += f"مستوى الألم (VAS): {last_pain}\n"
    if rt == "neuro":
        affected = {"right": "أيمن", "left": "أيسر", "bilateral": "ثنائي"}.get(patient.get("affected_side", ""), "—")
        ctx += f"الجانب المصاب: {affected}\n"
    if rt == "cardiac":
        ctx += f"تصنيف NYHA: {patient.get('nyha_class', '—')}\n"

    ctx += (
        f"الحالة الإدراكية: {patient.get('cognitive_status', 'normal')}\n"
        f"PHQ-9: {patient.get('phq9_score', 'لم يُقيَّم')}\n"
        f"الأهداف الوظيفية: {goals}\n"
        f"عدد التقييمات: {len(patient.get('assessment_results', []))} | "
        f"عدد الجلسات: {len(patient.get('intervention_sessions', []))} | "
        f"عدد الملاحظات: {len(patient.get('notes', []))} | "
        f"عدد الخطط العلاجية: {treatment_plans_count}\n"
    )
    if recent_notes:
        ctx += f"آخر الملاحظات:\n{recent_notes}"
    if recent_assess:
        ctx += f"آخر التقييمات:\n{recent_assess}"
    if recent_sessions:
        ctx += f"آخر الجلسات:\n{recent_sessions}"
    if recent_plans:
        ctx += f"الخطط العلاجية النشطة:\n{recent_plans}"
    ctx += (
        f"---\n"
        f"عند الإجابة، استخدم بيانات هذا المريض (ملف #{fnum}) تحديداً.\n"
        f"يمكنك استخدام أداة patient_database للبحث عن مرضى آخرين أو استرجاع بيانات إضافية.\n"
        f"استخدم أداة record_treatment_plan لحفظ الخطط العلاجية في ملف المريض.\n"
        f"بادر بطرح أسئلة لاستكمال المعلومات الناقصة.\n"
    )
    return ctx


_orchestrator = RehabOrchestrator()


def _build_api_messages(patient: dict, user_text: str, images: list = None) -> list:
    """Build API messages from chat history + current message."""
    chat_history = patient.get("chat_history", []) if patient else []
    api_messages = []
    for msg in chat_history:
        if msg["role"] == "user":
            api_messages.append({"role": "user", "content": [{"type": "text", "text": msg["content"]}]})
        else:
            api_messages.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})

    current_content = []
    if images:
        for img in images:
            current_content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": img["media_type"], "data": img["data"]}
            })
    current_content.append({"type": "text", "text": user_text})
    api_messages.append({"role": "user", "content": current_content})
    return api_messages


def chat_with_patient_context(user_text: str, patient: dict = None, images: list = None) -> dict:
    """Synchronous chat (used for non-streaming contexts like AI summary)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "text": "[تنبيه] **مفتاح API غير موجود!**\n\nيرجى إضافة `ANTHROPIC_API_KEY` في متغيرات البيئة.",
            "tool_calls": [], "thinking_used": False,
        }

    user_text = sanitize_patient_input(user_text)
    system = SYSTEM_PROMPT
    if patient:
        system = system + build_patient_system_context(patient)

    api_messages = _build_api_messages(patient, user_text, images)

    try:
        return _orchestrator.execute(
            message=user_text,
            patient=patient,
            messages=api_messages,
            system=system,
            images=images,
            stream=False,
            thinking_budget=st.session_state.thinking_budget,
            use_thinking=st.session_state.use_thinking,
        )
    except anthropic.AuthenticationError:
        return {"text": "[تنبيه] **خطأ في المصادقة:** مفتاح API غير صالح.", "tool_calls": [], "thinking_used": False}
    except anthropic.APIConnectionError:
        return {"text": "[تنبيه] **خطأ في الاتصال:** تحقق من اتصالك بالإنترنت.", "tool_calls": [], "thinking_used": False}
    except anthropic.RateLimitError:
        return {"text": "[تنبيه] **تجاوز حد الاستخدام:** يرجى الانتظار.", "tool_calls": [], "thinking_used": False}


def chat_with_patient_context_stream(user_text: str, patient: dict = None,
                                     images: list = None, placeholder=None) -> dict:
    """Streaming chat — tokens appear word-by-word in the placeholder."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "text": "[تنبيه] **مفتاح API غير موجود!**",
            "tool_calls": [], "thinking_used": False,
        }

    user_text = sanitize_patient_input(user_text)
    system = SYSTEM_PROMPT
    if patient:
        system = system + build_patient_system_context(patient)

    api_messages = _build_api_messages(patient, user_text, images)

    try:
        return _orchestrator.execute(
            message=user_text,
            patient=patient,
            messages=api_messages,
            system=system,
            images=images,
            stream=True,
            placeholder=placeholder,
            thinking_budget=st.session_state.thinking_budget,
            use_thinking=st.session_state.use_thinking,
        )
    except anthropic.AuthenticationError:
        return {"text": "[تنبيه] **خطأ في المصادقة:** مفتاح API غير صالح.", "tool_calls": [], "thinking_used": False}
    except anthropic.APIConnectionError:
        return {"text": "[تنبيه] **خطأ في الاتصال:** تحقق من اتصالك بالإنترنت.", "tool_calls": [], "thinking_used": False}
    except anthropic.RateLimitError:
        return {"text": "[تنبيه] **تجاوز حد الاستخدام:** يرجى الانتظار.", "tool_calls": [], "thinking_used": False}


# ═══════════════════════════════════════════════════════════════
# Rendering Helpers
# ═══════════════════════════════════════════════════════════════

TOOL_NAME_MAP = {t[2]: t[1] for t in TOOLS_MANIFEST}

def tool_display_name(raw_name: str) -> str:
    for key, label in TOOL_NAME_MAP.items():
        if key in raw_name:
            return label
    return raw_name

def render_tool_calls(tool_calls: list):
    if not tool_calls:
        return
    for tc in tool_calls:
        st.markdown(f"""
        <div class="tool-call-card">
            <div class="tool-call-header">استخدام أداة</div>
            <span class="tool-call-name">{html.escape(tool_display_name(tc['name']))}</span>
            <div style="color:#78350F;font-size:10px;margin-top:4px;font-family:monospace;opacity:0.7">
                {html.escape(tc.get('input_preview', ''))}
            </div>
        </div>""", unsafe_allow_html=True)

def render_message(msg: dict):
    role = msg["role"]
    content = msg["content"]
    ts = msg.get("time", "")
    tool_calls = msg.get("tool_calls", [])

    if role == "user":
        # إخفاء رسالة الإطلاق التلقائي (__START_INTAKE__)
        if content.strip() == "__START_INTAKE__":
            return
        st.markdown(f"""
        <div class="msg-user">
            <div class="avatar avatar-user">M</div>
            <div>
                <div class="bubble bubble-user">{html.escape(content)}</div>
                <div class="bubble-footer">{html.escape(ts)}</div>
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        # عرض استدعاءات الأدوات (غير SVG)
        non_svg_calls = [tc for tc in tool_calls if not tc.get("svg_data")]
        if non_svg_calls:
            st.markdown('<div style="padding-right:48px">', unsafe_allow_html=True)
            render_tool_calls(non_svg_calls)
            st.markdown('</div>', unsafe_allow_html=True)

        col_av, col_bub = st.columns([0.06, 0.94])
        with col_av:
            st.markdown('<div class="avatar avatar-ai" style="margin-top:4px;font-size:12px;font-weight:800;color:white">Re</div>', unsafe_allow_html=True)
        with col_bub:
            st.markdown('<div class="bubble bubble-ai" style="max-width:100%">', unsafe_allow_html=True)
            st.markdown(content)
            st.markdown(f'<div class="bubble-footer bubble-footer-ai">{html.escape(ts)}</div></div>', unsafe_allow_html=True)

        # عرض التمارين البصرية SVG
        for tc in tool_calls:
            if tc.get("svg_data"):
                ev = tc.get("svg_evidence", "")
                ev_badge = f'<span style="background:rgba(11,132,87,0.2);color:#10A567;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">مستوى الدليل: {html.escape(ev)}</span>' if ev else ""
                st.markdown(f"""
                <div class="visual-exercise-card">
                    <div class="ve-header">{html.escape(tc.get("svg_title", "تمرين بصري"))}</div>
                    <div class="ve-instructions">{html.escape(tc.get("svg_instructions", ""))}</div>
                    <div class="ve-svg">{tc["svg_data"]}</div>
                    <div class="ve-footer">
                        <span>{tc.get("svg_duration", 10)} دقيقة</span>
                        <span>{tc.get("svg_reps", 3)} مرات</span>
                        {ev_badge}
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# Patient Registry Page
# ═══════════════════════════════════════════════════════════════

def render_patient_registry():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    api_badge = '<span class="badge badge-green">● API متصل</span>' if api_key else '<span class="badge badge-red">○ API غير متصل</span>'
    st.markdown(f"""
    <div class="page-header">
        <div class="ph-left">
            <span class="ph-icon" style="font-size:28px;font-weight:900;color:white">Re</span>
            <div>
                <h1 class="ph-title">مستشار التأهيل الطبي الذكي</h1>
                <p class="ph-sub">Medical Rehabilitation AI Consultant · Claude Sonnet 4.6</p>
            </div>
        </div>
        <div class="ph-badges">
            {api_badge}
            <span class="badge badge-blue">22 أداة متخصصة</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## سجل المرضى")

    if st.button("+ إنشاء ملف مريض جديد", type="primary", key="new_patient_btn"):
        st.session_state.show_new_patient_form = True

    # New patient form
    if st.session_state.show_new_patient_form:
        render_new_patient_form()

    # Patient cards grid
    patients = st.session_state.patients
    if not patients:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon" style="font-size:40px;font-weight:800;color:var(--text-muted)">--</span>
            <p class="empty-state-text">لا يوجد مرضى مسجلون بعد.<br>اضغط على "إنشاء ملف مريض جديد" للبدء.</p>
        </div>""", unsafe_allow_html=True)
        return

    st.markdown(f'<div style="font-size:13px;color:var(--text-muted);font-weight:600;margin-bottom:12px">إجمالي المرضى: <span style="color:var(--primary);font-weight:800">{len(patients)}</span></div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for i, (pid, p) in enumerate(sorted(patients.items(), key=lambda x: x[1].get("updated_at", ""), reverse=True)):
        with cols[i % 3]:
            dx = p.get("diagnosis_text", "—") or "—"
            va = p.get("va_logmar", "—")
            va_str = f"{va} LogMAR" if va is not None else "—"
            updated = p.get("updated_at", "")[:10]
            fnum = p.get("file_number", "—")
            fnum_display = f"#{fnum}" if isinstance(fnum, int) else fnum

            st.markdown(f"""
            <div class="patient-card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <p class="patient-card-name" style="margin:0">{html.escape(p.get('name', pid))}</p>
                    <span class="badge badge-blue" style="font-size:11px;font-weight:800">{html.escape(str(fnum_display))}</span>
                </div>
                <p class="patient-card-dx">{html.escape(dx)}</p>
                <p class="patient-card-meta">VA: {html.escape(str(va_str))} · ملف: {html.escape(str(pid))} · {html.escape(updated)}</p>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("فتح الملف", key=f"open_{pid}", use_container_width=True):
                    st.session_state.current_page = "patient_file"
                    st.session_state.current_patient_id = pid
                    st.rerun()
            with c2:
                if st.button("حذف", key=f"del_{pid}", use_container_width=True):
                    delete_patient(pid)
                    del st.session_state.patients[pid]
                    st.rerun()


REHAB_TYPES = {
    "": "-- اختر نوع التأهيل --",
    "musculoskeletal": "عضلي هيكلي",
    "neurological": "عصبي",
    "cardiopulmonary": "قلبي رئوي",
    "vision": "بصري",
    "pediatric": "أطفال",
    "geriatric": "كبار السن",
    "pain": "إدارة الألم",
    "psychosocial": "نفسي اجتماعي",
}


def render_new_patient_form():
    with st.expander("بيانات المريض الجديد", expanded=True):
        rehab_type = st.selectbox("نوع التأهيل", list(REHAB_TYPES.keys()),
            format_func=lambda x: REHAB_TYPES[x], key="np_rehab_type")

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("اسم المريض (عربي)", key="np_name")
            age = st.number_input("العمر", 0, 120, 60, key="np_age")
            gender = st.selectbox("الجنس", ["male", "female"], format_func=lambda x: "ذكر" if x == "male" else "أنثى", key="np_gender")
            cog = st.selectbox("الحالة الإدراكية",
                ["normal", "mild_impairment", "moderate_impairment", "severe_impairment"],
                format_func=lambda x: {"normal": "طبيعي", "mild_impairment": "خفيف",
                    "moderate_impairment": "متوسط", "severe_impairment": "شديد"}.get(x, x), key="np_cog")
        with col2:
            icd10 = st.multiselect("التشخيص (ICD-10)", list(ICD10_OPTIONS.keys()),
                format_func=lambda x: f"{x}: {ICD10_OPTIONS[x]}", key="np_icd10")
            phq9 = st.number_input("PHQ-9 (اكتئاب)", 0, 27, 0, key="np_phq9")

        # Specialty-specific fields
        va = None
        pattern = ""
        vf = None
        pain_level = None
        affected_side = ""

        if rehab_type == "vision":
            st.markdown("**بيانات بصرية**")
            vc1, vc2, vc3 = st.columns(3)
            va = vc1.number_input("حدة الإبصار (LogMAR)", -0.3, 3.0, 1.0, 0.1, format="%.1f", key="np_va")
            pattern = vc2.selectbox("نمط الفقد البصري", [""] + VISION_PATTERNS, key="np_pattern")
            vf = vc3.number_input("مجال الرؤية (درجات)", 0.0, 180.0, 0.0, 5.0, key="np_vf")

        if rehab_type in ("orthopedic", "neuro", "pain"):
            st.markdown("**بيانات إضافية**")
            pc1, pc2 = st.columns(2)
            pain_level = pc1.slider("مستوى الألم (VAS 0-10)", 0, 10, 0, key="np_pain")
            if rehab_type == "neuro":
                affected_side = pc2.selectbox("الجانب المصاب", ["", "right", "left", "bilateral"],
                    format_func=lambda x: {"": "—", "right": "أيمن", "left": "أيسر", "bilateral": "ثنائي"}.get(x, x), key="np_side")

        if rehab_type == "cardiac":
            st.markdown("**بيانات قلبية**")
            nyha_class = st.selectbox("تصنيف NYHA", ["I", "II", "III", "IV"], key="np_nyha")

        goals = st.multiselect("الأهداف الوظيفية", FUNCTIONAL_GOALS,
            format_func=lambda x: FUNCTIONAL_GOALS_AR.get(x, x), key="np_goals")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("حفظ وفتح الملف", type="primary", key="save_np"):
                if not name.strip():
                    st.error("يرجى إدخال اسم المريض")
                    return
                pid, file_number = generate_patient_id()
                patient = new_patient_template(pid, file_number)
                patient.update({
                    "name": name.strip(), "age": int(age), "gender": gender,
                    "rehabilitation_type": rehab_type,
                    "diagnosis_icd10": icd10,
                    "diagnosis_text": ", ".join(ICD10_OPTIONS.get(c, c) for c in icd10),
                    "cognitive_status": cog, "functional_goals": goals,
                    "phq9_score": int(phq9) if phq9 else None,
                })
                # Vision-specific
                if va is not None:
                    patient["va_logmar"] = float(va)
                if pattern:
                    patient["vision_pattern"] = pattern
                if vf and vf > 0:
                    patient["visual_field_degrees"] = float(vf)
                # Pain
                if pain_level is not None and pain_level > 0:
                    patient["pain_scores"] = [{"value": pain_level, "timestamp": datetime.now().isoformat(), "scale": "VAS"}]
                # Neuro
                if affected_side:
                    patient["affected_side"] = affected_side
                # Cardiac
                if rehab_type == "cardiac":
                    patient["nyha_class"] = nyha_class

                save_patient(patient)
                st.session_state.patients[pid] = patient
                st.session_state.current_page = "patient_file"
                st.session_state.current_patient_id = pid
                st.session_state.show_new_patient_form = False
                st.rerun()
        with c2:
            if st.button("إلغاء", key="cancel_np"):
                st.session_state.show_new_patient_form = False
                st.rerun()


# ═══════════════════════════════════════════════════════════════
# Patient File Page — Header + Tabs
# ═══════════════════════════════════════════════════════════════

def render_patient_file(patient: dict):
    pid = patient["id"]

    # Back button
    if st.button("← العودة لسجل المرضى", key="back_to_registry"):
        st.session_state.current_page = "registry"
        st.session_state.current_patient_id = None
        st.rerun()

    # Patient header
    name = patient.get("name", pid)
    dx = patient.get("diagnosis_text", "—") or "—"
    icd = ", ".join(patient.get("diagnosis_icd10", [])) or "—"
    age = patient.get("age", "—")
    rehab_type = patient.get("rehabilitation_type", "")
    rehab_type_ar = REHAB_TYPES.get(rehab_type, rehab_type) or "عام"

    fnum = patient.get("file_number", "—")
    fnum_display = f"#{fnum}" if isinstance(fnum, int) else fnum

    # Build meta line based on rehab type
    meta_parts = [f"ملف {html.escape(str(fnum_display))}", f"العمر: {html.escape(str(age))}", f"التشخيص: {html.escape(dx)} ({html.escape(icd)})"]
    if rehab_type == "vision" and patient.get("va_logmar") is not None:
        meta_parts.append(f"VA: {patient.get('va_logmar')} LogMAR")
    meta_line = " · ".join(meta_parts)

    st.markdown(f"""
    <div class="patient-header">
        <div>
            <p class="ph-name">{html.escape(name)}</p>
            <p class="ph-meta">{meta_line}</p>
        </div>
        <div class="ph-badges">
            <span class="badge badge-green" style="font-size:12px;font-weight:900">{html.escape(str(fnum_display))}</span>
            <span class="badge badge-blue">{html.escape(rehab_type_ar)}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Tabs
    tab_summary, tab_chat, tab_notes, tab_plans, tab_assess, tab_cdss, tab_intervene, tab_docs = st.tabs([
        "الملخص", "المحادثة", "الملاحظات", "الخطط العلاجية",
        "التقييمات", "CDSS", "التدخلات", "التقارير"
    ])

    with tab_summary:
        render_summary_tab(patient)
    with tab_chat:
        render_chat_tab(patient)
    with tab_notes:
        render_notes_tab(patient)
    with tab_plans:
        render_treatment_plans_tab(patient)
    with tab_assess:
        render_assessments_tab(patient)
    with tab_cdss:
        render_cdss_tab(patient)
    with tab_intervene:
        render_interventions_tab(patient)
    with tab_docs:
        render_documents_tab(patient)


# ═══════════════════════════════════════════════════════════════
# Tab: Summary
# ═══════════════════════════════════════════════════════════════

def render_summary_tab(patient: dict):
    n_assess = len(patient.get("assessment_results", []))
    n_sessions = len(patient.get("intervention_sessions", []))
    n_notes = len(patient.get("notes", []))
    n_cdss = len(patient.get("cdss_evaluations", []))

    # Workflow progress bar
    steps = [
        ("1", "التسجيل", True),
        ("2", "التقييم", n_assess > 0),
        ("3", "CDSS", n_cdss > 0),
        ("4", "التدخل", n_sessions > 0),
        ("5", "التقارير", len(patient.get("documents", [])) > 0),
    ]
    steps_html = ""
    for i, (icon, label, done) in enumerate(steps):
        cls = "done" if done else ""
        connector = f'<span class="workflow-step-connector"></span>' if i > 0 else ""
        steps_html += f"""
        <div class="workflow-step {cls}">
            {connector}
            <span class="workflow-step-icon">{icon}</span>
            <span class="workflow-step-label">{label}</span>
        </div>"""
    st.markdown(f'<div class="workflow-progress">{steps_html}</div>', unsafe_allow_html=True)

    # Metric cards
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card"><span class="metric-num">{n_assess}</span><span class="metric-label">التقييمات</span></div>
        <div class="metric-card"><span class="metric-num">{n_sessions}</span><span class="metric-label">الجلسات</span></div>
        <div class="metric-card"><span class="metric-num">{n_notes}</span><span class="metric-label">الملاحظات</span></div>
        <div class="metric-card"><span class="metric-num">{n_cdss}</span><span class="metric-label">تقييمات CDSS</span></div>
    </div>
    """, unsafe_allow_html=True)

    # Patient info grid — dynamic based on rehabilitation type
    cog_map = {"normal": "طبيعي", "mild_impairment": "خفيف", "moderate_impairment": "متوسط", "severe_impairment": "شديد"}
    cog_val = cog_map.get(patient.get('cognitive_status', 'normal'), '—')
    rehab_type = patient.get("rehabilitation_type", "") or "—"
    rehab_type_ar = REHAB_TYPES.get(rehab_type, rehab_type)
    goals_ar = ", ".join(FUNCTIONAL_GOALS_AR.get(g, g) for g in patient.get("functional_goals", [])) or "—"
    n_plans = len(patient.get("treatment_plans", []))

    fnum_s = patient.get("file_number", "—")
    fnum_badge = f"#{fnum_s}" if isinstance(fnum_s, int) else str(fnum_s)

    # Core info items (always shown)
    info_items = f"""
            <div class="info-item"><div class="info-label">رقم الملف</div><div class="info-value" style="color:var(--secondary);font-weight:900;font-size:18px">{html.escape(fnum_badge)}</div></div>
            <div class="info-item"><div class="info-label">نوع التأهيل</div><div class="info-value">{html.escape(rehab_type_ar)}</div></div>
            <div class="info-item"><div class="info-label">التشخيص</div><div class="info-value">{html.escape(patient.get('diagnosis_text', '—') or '—')}</div></div>
            <div class="info-item"><div class="info-label">ICD-10</div><div class="info-value">{html.escape(', '.join(patient.get('diagnosis_icd10', [])) or '—')}</div></div>"""

    # Specialty-specific items
    if rehab_type == "vision":
        va_val = patient.get('va_logmar', '—')
        vf_val = patient.get('visual_field_degrees', '—')
        info_items += f"""
            <div class="info-item"><div class="info-label">حدة الإبصار</div><div class="info-value">{html.escape(str(va_val))} LogMAR</div></div>
            <div class="info-item"><div class="info-label">مجال الرؤية</div><div class="info-value">{html.escape(str(vf_val))} درجة</div></div>
            <div class="info-item"><div class="info-label">نمط الفقد</div><div class="info-value">{html.escape(patient.get('vision_pattern', '—') or '—')}</div></div>"""
    elif rehab_type in ("orthopedic", "pain"):
        pain_scores = patient.get("pain_scores", [])
        last_pain = pain_scores[-1]["value"] if pain_scores else "—"
        info_items += f"""
            <div class="info-item"><div class="info-label">مستوى الألم (VAS)</div><div class="info-value">{html.escape(str(last_pain))}/10</div></div>"""
    elif rehab_type == "neuro":
        affected = {"right": "أيمن", "left": "أيسر", "bilateral": "ثنائي"}.get(patient.get("affected_side", ""), "—")
        pain_scores = patient.get("pain_scores", [])
        last_pain = pain_scores[-1]["value"] if pain_scores else "—"
        info_items += f"""
            <div class="info-item"><div class="info-label">الجانب المصاب</div><div class="info-value">{html.escape(str(affected))}</div></div>
            <div class="info-item"><div class="info-label">مستوى الألم (VAS)</div><div class="info-value">{html.escape(str(last_pain))}/10</div></div>"""
    elif rehab_type == "cardiac":
        nyha = patient.get("nyha_class", "—")
        info_items += f"""
            <div class="info-item"><div class="info-label">تصنيف NYHA</div><div class="info-value">{html.escape(str(nyha))}</div></div>"""

    # Common items (always shown)
    info_items += f"""
            <div class="info-item"><div class="info-label">الحالة الإدراكية</div><div class="info-value">{html.escape(cog_val)}</div></div>
            <div class="info-item"><div class="info-label">PHQ-9</div><div class="info-value">{html.escape(str(patient.get('phq9_score', '—') or '—'))}</div></div>
            <div class="info-item"><div class="info-label">الأهداف</div><div class="info-value">{html.escape(goals_ar)}</div></div>
            <div class="info-item"><div class="info-label">الخطط العلاجية</div><div class="info-value">{n_plans}</div></div>
            <div class="info-item"><div class="info-label">تاريخ الإنشاء</div><div class="info-value">{html.escape(patient.get('created_at', '—')[:10])}</div></div>"""

    st.markdown(f"""
    <div style="margin-top:4px">
        <div style="font-size:15px;font-weight:800;color:var(--primary);margin-bottom:12px">المعلومات الأساسية</div>
        <div class="info-grid">{info_items}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # AI Summary button
    if st.button("توليد ملخص AI للمريض", key="ai_summary", type="primary"):
        with st.spinner("يحلل بيانات المريض..."):
            r_type = REHAB_TYPES.get(patient.get("rehabilitation_type", ""), "عام")
            goals_list = ", ".join(FUNCTIONAL_GOALS_AR.get(g, g) for g in patient.get("functional_goals", [])) or "لم تُحدد"
            prompt = (
                f"لخّص حالة هذا المريض سريرياً واقترح الخطوات التالية:\n"
                f"الاسم: {patient.get('name')}, العمر: {patient.get('age')}\n"
                f"نوع التأهيل: {r_type}\n"
                f"التشخيص: {patient.get('diagnosis_text')} ({', '.join(patient.get('diagnosis_icd10', []))})\n"
                f"الأهداف الوظيفية: {goals_list}\n"
                f"عدد التقييمات: {len(patient.get('assessment_results', []))}, "
                f"عدد الجلسات: {len(patient.get('intervention_sessions', []))}, "
                f"عدد الخطط العلاجية: {len(patient.get('treatment_plans', []))}"
            )
            result = chat_with_patient_context(prompt, patient)
            st.markdown(result["text"])

    # Recent activity timeline
    all_activities = []
    type_icons = {"ملاحظة": "N", "تقييم": "A", "جلسة": "S", "CDSS": "C", "وثيقة": "D"}
    type_colors = {"ملاحظة": "#2E8BC0", "تقييم": "#7C3AED", "جلسة": "#0B8457", "CDSS": "#D97706", "وثيقة": "#DC2626"}
    for n in patient.get("notes", []):
        all_activities.append({"time": n.get("timestamp", ""), "type": "ملاحظة", "desc": n.get("content", "")[:60]})
    for a in patient.get("assessment_results", []):
        all_activities.append({"time": a.get("timestamp", ""), "type": "تقييم", "desc": a.get("type", "")})
    for s in patient.get("intervention_sessions", []):
        all_activities.append({"time": s.get("timestamp", ""), "type": "جلسة", "desc": s.get("type", "")})
    for c in patient.get("cdss_evaluations", []):
        all_activities.append({"time": c.get("timestamp", ""), "type": "CDSS", "desc": "تقييم CDSS"})
    for d in patient.get("documents", []):
        all_activities.append({"time": d.get("timestamp", ""), "type": "وثيقة", "desc": d.get("type", "")})

    if all_activities:
        all_activities.sort(key=lambda x: x["time"], reverse=True)
        st.markdown('<div style="font-size:15px;font-weight:800;color:var(--primary);margin:20px 0 12px">آخر الأنشطة</div>', unsafe_allow_html=True)
        for act in all_activities[:6]:
            icon = type_icons.get(act["type"], "-")
            color = type_colors.get(act["type"], "#718096")
            st.markdown(f"""
            <div class="activity-item">
                <div class="activity-dot" style="background:{color}"></div>
                <div class="activity-content">
                    <span class="activity-type">{icon} {html.escape(act['type'])}</span>
                    <div class="activity-desc">{html.escape(act['desc'])}</div>
                </div>
                <span class="activity-time">{html.escape(act['time'][:16])}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon" style="font-size:40px;font-weight:800;color:var(--text-muted)">--</span>
            <p class="empty-state-text">لا توجد أنشطة بعد. ابدأ بإجراء تقييم أو إضافة ملاحظة.</p>
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# Tab: Treatment Plans
# ═══════════════════════════════════════════════════════════════

def render_treatment_plans_tab(patient: dict):
    pid = patient["id"]
    plans = patient.get("treatment_plans", [])

    st.markdown("### الخطط العلاجية")
    st.caption("الخطط العلاجية المسجلة عبر المحادثة مع المستشار — يمكن تعديل حالتها.")

    if not plans:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon" style="font-size:40px;font-weight:800;color:var(--text-muted)">--</span>
            <p class="empty-state-text">لا توجد خطط علاجية بعد. اطلب من المستشار في المحادثة إعداد خطة علاجية.</p>
        </div>""", unsafe_allow_html=True)
        return

    # Summary metrics
    active_count = sum(1 for p in plans if p.get("status") == "active")
    completed_count = sum(1 for p in plans if p.get("status") == "completed")
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card"><span class="metric-num">{len(plans)}</span><span class="metric-label">إجمالي الخطط</span></div>
        <div class="metric-card"><span class="metric-num">{active_count}</span><span class="metric-label">نشطة</span></div>
        <div class="metric-card"><span class="metric-num">{completed_count}</span><span class="metric-label">مكتملة</span></div>
    </div>
    """, unsafe_allow_html=True)

    # Display each plan
    for i, plan in enumerate(reversed(plans)):
        plan_idx = len(plans) - 1 - i
        status = plan.get("status", "active")
        status_ar = {"active": "نشطة", "completed": "مكتملة", "cancelled": "ملغاة"}.get(status, status)
        status_color = {"active": "green", "completed": "blue", "cancelled": "orange"}.get(status, "blue")
        title = plan.get("plan_title", f"خطة #{plan_idx + 1}")
        r_type = REHAB_TYPES.get(plan.get("rehabilitation_type", ""), "عام")
        created = plan.get("created_at", "")[:10]

        with st.expander(f"{title} — {r_type} [{status_ar}] ({created})", expanded=(i == 0 and status == "active")):
            # Goals
            goals = plan.get("goals", [])
            if goals:
                st.markdown("**الأهداف:**")
                for g in goals:
                    timeframe = g.get("timeframe", "")
                    desc = g.get("description", str(g) if isinstance(g, str) else "")
                    tf_label = f" ({timeframe})" if timeframe else ""
                    st.markdown(f"- {desc}{tf_label}")

            # Interventions
            interventions = plan.get("interventions", [])
            if interventions:
                st.markdown("**التدخلات:**")
                for inv in interventions:
                    if isinstance(inv, dict):
                        freq = inv.get("frequency", "")
                        st.markdown(f"- {inv.get('name', inv.get('type', ''))} — {freq}")
                    else:
                        st.markdown(f"- {inv}")

            # Precautions
            precautions = plan.get("precautions", [])
            if precautions:
                st.markdown("**الاحتياطات:**")
                for pr in precautions:
                    st.markdown(f"- {pr}")

            # Follow-up
            followup = plan.get("follow_up_schedule", "")
            if followup:
                st.markdown(f"**جدول المتابعة:** {followup}")

            # Notes
            notes = plan.get("notes", "")
            if notes:
                st.markdown(f"**ملاحظات:** {notes}")

            # Status toggle
            col1, col2, col3 = st.columns(3)
            if status == "active":
                if col1.button("اكتمال", key=f"plan_complete_{pid}_{plan_idx}"):
                    patient["treatment_plans"][plan_idx]["status"] = "completed"
                    save_patient(patient)
                    st.session_state.patients[pid] = patient
                    st.rerun()
                if col2.button("إلغاء", key=f"plan_cancel_{pid}_{plan_idx}"):
                    patient["treatment_plans"][plan_idx]["status"] = "cancelled"
                    save_patient(patient)
                    st.session_state.patients[pid] = patient
                    st.rerun()
            elif status in ("completed", "cancelled"):
                if col1.button("إعادة تفعيل", key=f"plan_reactivate_{pid}_{plan_idx}"):
                    patient["treatment_plans"][plan_idx]["status"] = "active"
                    save_patient(patient)
                    st.session_state.patients[pid] = patient
                    st.rerun()


# ═══════════════════════════════════════════════════════════════
# Tab: Chat (Patient-Aware)
# ═══════════════════════════════════════════════════════════════

def render_chat_tab(patient: dict):
    pid = patient["id"]
    chat_history = patient.get("chat_history", [])

    # Chat area — auto-start if no history
    chat_area = st.container()
    with chat_area:
        if not chat_history:
            st.markdown("""
            <div class="welcome-container">
                <div class="ai-loading">
                    <div class="ai-loading-dot"></div>
                    <div class="ai-loading-dot"></div>
                    <div class="ai-loading-dot"></div>
                </div>
                <p style="color:var(--text-muted);font-size:13px;margin-top:8px;text-align:center">
                    جارٍ بدء جلسة التقييم…
                </p>
            </div>
            """, unsafe_allow_html=True)
            # أرسل trigger تلقائي لـ Claude ليبدأ المقابلة الاستهلالية
            _send_chat_message(patient, "__START_INTAKE__")
            st.rerun()
        else:
            for msg in chat_history:
                render_message(msg)

    # Input area
    st.markdown('<div class="input-wrapper"><div class="input-card">', unsafe_allow_html=True)

    uploaded_file = None
    show_upload = st.checkbox("إرفاق صورة طبية", value=False, key=f"upload_{pid}")
    if show_upload:
        uploaded_file = st.file_uploader("ارفع صورة", type=["png", "jpg", "jpeg", "webp"], key=f"file_{pid}", label_visibility="collapsed")

    user_input = st.text_area("رسالتك", placeholder="اكتب سؤالك السريري هنا…", key=f"input_{pid}", height=80, label_visibility="collapsed")

    col_send, col_clear, _ = st.columns([2, 1, 4])
    with col_send:
        st.markdown('<div class="send-col">', unsafe_allow_html=True)
        send_btn = st.button("إرسال ↗", key=f"send_{pid}", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col_clear:
        st.markdown('<div class="clear-col">', unsafe_allow_html=True)
        if st.button("مسح المحادثة", key=f"clear_{pid}", use_container_width=True):
            patient["chat_history"] = []
            save_patient(patient)
            st.session_state.patients[pid] = patient
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)

    if send_btn and user_input and user_input.strip():
        images = None
        if uploaded_file:
            img_bytes = uploaded_file.read()
            img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
            ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
            media_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
            images = [{"media_type": media_map.get(ext, "image/jpeg"), "data": img_b64}]
        # Show user message immediately + stream response
        with chat_area:
            render_message({"role": "user", "content": user_input.strip(), "time": datetime.now().strftime("%H:%M"), "tool_calls": []})
            stream_placeholder = st.empty()
        _send_chat_message(patient, user_input.strip(), images, placeholder=stream_placeholder)
        st.rerun()


def _send_chat_message(patient: dict, text: str, images: list = None, placeholder=None):
    pid = patient["id"]
    now = datetime.now().strftime("%H:%M")
    patient.setdefault("chat_history", [])
    patient["chat_history"].append({"role": "user", "content": text, "time": now, "tool_calls": []})

    try:
        if placeholder:
            result = chat_with_patient_context_stream(text, patient, images, placeholder)
        else:
            result = chat_with_patient_context(text, patient, images)
        patient["chat_history"].append({
            "role": "assistant", "content": result["text"],
            "time": datetime.now().strftime("%H:%M"), "tool_calls": result["tool_calls"],
        })
    except Exception as e:
        patient["chat_history"].append({
            "role": "assistant", "content": f"[تنبيه] حدث خطأ: {str(e)}",
            "time": datetime.now().strftime("%H:%M"), "tool_calls": [],
        })

    save_patient(patient)
    st.session_state.patients[pid] = patient


# ═══════════════════════════════════════════════════════════════
# Tab: Notes
# ═══════════════════════════════════════════════════════════════

def render_notes_tab(patient: dict):
    pid = patient["id"]
    st.markdown("### الملاحظات السريرية")

    note_type = st.selectbox("نوع الملاحظة", ["ملاحظة عامة", "تقييم", "متابعة", "إحالة"], key=f"nt_{pid}")
    note_content = st.text_area("محتوى الملاحظة", height=100, key=f"nc_{pid}")

    if st.button("+ إضافة ملاحظة", key=f"add_note_{pid}", type="primary"):
        if note_content.strip():
            patient.setdefault("notes", [])
            patient["notes"].append({
                "timestamp": datetime.now().isoformat(),
                "type": note_type,
                "content": note_content.strip(),
                "author": "clinician",
            })
            save_patient(patient)
            st.session_state.patients[pid] = patient
            st.rerun()
        else:
            st.warning("يرجى كتابة محتوى الملاحظة")

    # Display notes (newest first)
    notes = patient.get("notes", [])
    if notes:
        st.markdown("---")
        for i, note in enumerate(reversed(notes)):
            idx = len(notes) - 1 - i
            st.markdown(f"""
            <div class="note-card">
                <div class="note-card-header">
                    <span class="note-card-type">{html.escape(note.get('type', ''))}</span>
                    <span class="note-card-time">{html.escape(note.get('timestamp', '')[:16])}</span>
                </div>
                <div class="note-card-body">{html.escape(note.get('content', ''))}</div>
            </div>""", unsafe_allow_html=True)
            if st.button("حذف", key=f"del_note_{pid}_{idx}"):
                patient["notes"].pop(idx)
                save_patient(patient)
                st.session_state.patients[pid] = patient
                st.rerun()
    else:
        st.markdown("""
        <div class="empty-state">
            <span class="empty-state-icon" style="font-size:40px;font-weight:800;color:var(--text-muted)">--</span>
            <p class="empty-state-text">لا توجد ملاحظات بعد. أضف ملاحظتك الأولى أعلاه.</p>
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# Tab: Assessments (Patient-Aware)
# ═══════════════════════════════════════════════════════════════

def render_assessments_tab(patient: dict):
    pid = patient["id"]
    st.markdown("### التقييمات السريرية الرقمية")
    st.caption("أجرِ تقييمات رقمية متخصصة — تُحفظ النتائج تلقائياً في ملف المريض.")

    # Previous results
    prev = patient.get("assessment_results", [])
    if prev:
        with st.expander(f"نتائج سابقة ({len(prev)} تقييم)", expanded=False):
            for a in reversed(prev):
                st.write(f"**{a.get('type', '')}** — {a.get('timestamp', '')[:16]}")
                st.json(a.get("result", {}))
                st.markdown("---")

    assess_type = st.selectbox("نوع التقييم", ["fixation", "reading", "visual_search", "contrast"],
        format_func=lambda x: {"fixation": "ثبات التثبيت (BCEA)", "reading": "سرعة القراءة (MNREAD)",
            "visual_search": "المسح البصري", "contrast": "حساسية التباين"}.get(x, x), key=f"at_{pid}")

    if assess_type == "fixation":
        st.info("أدخل إحداثيات تتبع العين (X, Y) لجلستين.")
        col1, col2 = st.columns(2)
        with col1:
            s1x = st.text_input("Session 1 — X", "0.5, 0.7, -0.2, 1.2, 0.9, 0.3, -0.1, 0.8", key=f"fx1x_{pid}")
            s1y = st.text_input("Session 1 — Y", "0.1, -0.5, 0.8, 1.1, -0.2, 0.4, -0.3, 0.6", key=f"fx1y_{pid}")
        with col2:
            s2x = st.text_input("Session 2 — X", "0.1, 0.2, 0.0, -0.1, 0.1, 0.05, -0.05, 0.15", key=f"fx2x_{pid}")
            s2y = st.text_input("Session 2 — Y", "0.0, 0.1, -0.1, 0.0, 0.2, -0.05, 0.1, -0.1", key=f"fx2y_{pid}")
        if st.button("تحليل التثبيت", key=f"run_fix_{pid}", type="primary"):
            try:
                params = {"assessment_type": "fixation", "action": "evaluate_progress",
                    "session1_x": [float(x) for x in s1x.split(",")], "session1_y": [float(x) for x in s1y.split(",")],
                    "session2_x": [float(x) for x in s2x.split(",")], "session2_y": [float(x) for x in s2y.split(",")]}
                result = run_assessment(params)
                c1, c2, c3 = st.columns(3)
                c1.metric("BCEA قبل", f"{result['bcea_before']} deg²")
                c2.metric("BCEA بعد", f"{result['bcea_after']} deg²")
                c3.metric("التحسن", f"{result['improvement_pct']}%")
                st.success(f"**الحالة:** {result['status_ar']} — **الإجراء:** {result['action_ar']}")
                _save_assessment(patient, "fixation", result)
            except Exception as e:
                st.error(f"خطأ: {e}")

    elif assess_type == "reading":
        st.info("أدخل قراءات MNREAD.")
        num = st.number_input("عدد القراءات", 3, 10, 5, key=f"mn_n_{pid}")
        readings = []
        for i in range(int(num)):
            cols = st.columns(3)
            size = cols[0].number_input(f"حجم {i+1} (LogMAR)", 0.0, 1.5, max(0.0, 1.0 - i * 0.2), 0.1, key=f"mn_s_{pid}_{i}")
            time_s = cols[1].number_input(f"زمن {i+1} (ث)", 1.0, 120.0, 5.0 + i * 3, 0.5, key=f"mn_t_{pid}_{i}")
            errs = cols[2].number_input(f"أخطاء {i+1}", 0, 10, min(i, 5), key=f"mn_e_{pid}_{i}")
            readings.append({"print_size_logmar": size, "reading_time_seconds": time_s, "word_errors": int(errs)})
        if st.button("تحليل القراءة", key=f"run_mn_{pid}", type="primary"):
            result = run_assessment({"assessment_type": "reading", "readings": readings})
            c1, c2, c3 = st.columns(3)
            c1.metric("MRS", f"{result['mrs_wpm']} WPM")
            c2.metric("CPS", f"{result['cps_logmar']} LogMAR")
            c3.metric("RA", f"{result['reading_acuity_logmar']} LogMAR")
            _save_assessment(patient, "reading", result)

    elif assess_type == "contrast":
        st.info("أدخل استجابات Pelli-Robson.")
        levels = [0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.20, 1.35]
        responses = []
        cols = st.columns(5)
        for i, lvl in enumerate(levels):
            c = cols[i % 5]
            correct = c.number_input(f"LogCS {lvl}", 0, 3, 3 if i < 5 else 2, key=f"pr_{pid}_{i}")
            responses.append({"log_cs_level": lvl, "letters_correct": int(correct)})
        if st.button("تحليل التباين", key=f"run_cs_{pid}", type="primary"):
            result = run_assessment({"assessment_type": "contrast", "method": "pelli_robson", "responses": responses})
            c1, c2 = st.columns(2)
            c1.metric("LogCS", result["threshold_logcs"])
            c2.metric("التصنيف", result["classification"]["label_ar"])
            _save_assessment(patient, "contrast", result)

    elif assess_type == "visual_search":
        st.info("محاكاة اختبار شطب رقمي.")
        diff = st.slider("الصعوبة", 1, 5, 2, key=f"vs_d_{pid}")
        targets = st.slider("الأهداف", 10, 40, 20, key=f"vs_t_{pid}")
        if st.button("توليد اختبار", key=f"run_vs_{pid}", type="primary"):
            result = run_assessment({"assessment_type": "visual_search", "action": "generate_trial", "difficulty": diff, "target_count": targets})
            st.success(f"تم توليد {result['total_targets']} هدف + {result['total_distractors']} مشتت")
            _save_assessment(patient, "visual_search", result)


def _save_assessment(patient: dict, atype: str, result: dict):
    patient.setdefault("assessment_results", [])
    patient["assessment_results"].append({"timestamp": datetime.now().isoformat(), "type": atype, "result": result})
    save_patient(patient)
    st.session_state.patients[patient["id"]] = patient
    st.success("تم حفظ نتيجة التقييم في ملف المريض")


# ═══════════════════════════════════════════════════════════════
# Tab: CDSS (Patient-Aware)
# ═══════════════════════════════════════════════════════════════

def render_cdss_tab(patient: dict):
    pid = patient["id"]
    st.markdown("### نظام دعم القرار السريري (CDSS)")
    st.caption("يُملأ تلقائياً من بيانات المريض. يمكنك تعديل القيم قبل التقييم.")

    # Previous evaluations
    prev_cdss = patient.get("cdss_evaluations", [])
    if prev_cdss:
        with st.expander(f"تقييمات سابقة ({len(prev_cdss)})", expanded=False):
            for ev in reversed(prev_cdss):
                st.write(f"**{ev.get('timestamp', '')[:16]}**")
                recs = ev.get("result", {}).get("recommendations", [])
                for r in recs[:3]:
                    st.write(f"  - {r.get('technique_ar', r.get('technique', ''))}: أولوية {r.get('priority', '')}")
                st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        va = st.number_input("VA (LogMAR)", -0.3, 3.0, float(patient.get("va_logmar", 1.0) or 1.0), 0.1, format="%.1f", key=f"cdss_va_{pid}")
        icd_input = st.text_input("ICD-10", ", ".join(patient.get("diagnosis_icd10", [])), key=f"cdss_icd_{pid}")
        phq9 = st.number_input("PHQ-9", 0, 27, int(patient.get("phq9_score", 0) or 0), key=f"cdss_phq_{pid}")
    with col2:
        patterns = st.multiselect("نمط الفقد", VISION_PATTERNS,
            default=[patient.get("vision_pattern", "")] if patient.get("vision_pattern") else [], key=f"cdss_pat_{pid}")
        goals = st.multiselect("الأهداف", FUNCTIONAL_GOALS,
            default=patient.get("functional_goals", []),
            format_func=lambda x: FUNCTIONAL_GOALS_AR.get(x, x), key=f"cdss_goals_{pid}")
        cog = st.selectbox("الحالة الإدراكية", ["normal", "mild_impairment", "moderate_impairment", "severe_impairment"],
            index=["normal", "mild_impairment", "moderate_impairment", "severe_impairment"].index(patient.get("cognitive_status", "normal")),
            key=f"cdss_cog_{pid}")

    language = st.radio("لغة التقرير", ["ar", "en"], horizontal=True, key=f"cdss_lang_{pid}")

    if st.button("تشغيل تقييم CDSS", type="primary", key=f"cdss_run_{pid}"):
        icd_list = [c.strip() for c in icd_input.split(",") if c.strip()]
        patient_data = {
            "age": patient.get("age", 60), "active_icd10": icd_list, "vision_patterns": patterns,
            "va_logmar": va, "phq9_score": phq9, "functional_goals": goals,
            "cognitive_status": cog, "equipment_available": [], "setting": "clinic", "language": language,
        }
        with st.spinner("يعالج البيانات..."):
            try:
                params = {"input_type": "manual", "patient_data": patient_data, "patient_id": pid, "language": language}
                result = run_cdss_evaluation(params)
                _render_cdss_result(result)
                # Save
                patient.setdefault("cdss_evaluations", [])
                patient["cdss_evaluations"].append({"timestamp": datetime.now().isoformat(), "result": result})
                save_patient(patient)
                st.session_state.patients[pid] = patient
                st.success("تم حفظ نتيجة CDSS في ملف المريض")
            except Exception as e:
                st.error(f"خطأ: {e}")


def _render_cdss_result(result: dict):
    if "error" in result:
        st.error(f"{result['error']}")
        return

    for err in result.get("errors", []):
        msg = err.get("message_ar", str(err)) if isinstance(err, dict) else str(err)
        st.error(msg)
    for warn in result.get("warnings", []):
        msg = warn.get("message_ar", str(warn)) if isinstance(warn, dict) else str(warn)
        st.warning(msg)

    recs = result.get("recommendations", [])
    c1, c2, c3 = st.columns(3)
    c1.metric("القواعد المُقيَّمة", result.get("total_rules_evaluated", "—"))
    c2.metric("التوصيات", result.get("total_matched", len(recs)))
    c3.metric("التحقق", "صالح" if result.get("is_valid", True) else "أخطاء")

    report = result.get("clinical_report", "") or result.get("report", "")
    if report:
        st.markdown("---")
        st.markdown(report)
    elif recs:
        st.markdown("---")
        for i, rec in enumerate(recs, 1):
            with st.expander(f"{i}. {rec.get('technique_ar', rec.get('technique', ''))} — أولوية {rec.get('priority', '')}"):
                st.write(f"**الدليل:** {rec.get('evidence_level', '')} | **الملاءمة:** {rec.get('suitability_score', '')}")
                st.write(f"**الإجراء:** {rec.get('action', '')}")
                if rec.get("justification"):
                    st.info(rec["justification"])

    audit = result.get("audit_trail", {})
    if audit:
        with st.expander("مسار التدقيق"):
            st.json(audit)


# ═══════════════════════════════════════════════════════════════
# Tab: Interventions (Patient-Aware)
# ═══════════════════════════════════════════════════════════════

def render_interventions_tab(patient: dict):
    pid = patient["id"]
    st.markdown("### التدخلات العلاجية الرقمية")
    st.caption("شغّل جلسات تأهيل رقمية — تُحفظ النتائج تلقائياً في ملف المريض.")

    prev = patient.get("intervention_sessions", [])
    if prev:
        with st.expander(f"جلسات سابقة ({len(prev)})", expanded=False):
            for s in reversed(prev):
                st.write(f"**{s.get('type', '')}** — {s.get('timestamp', '')[:16]}")
                st.json(s.get("result", {}))
                st.markdown("---")

    int_type = st.selectbox("نوع التدخل", ["scanning", "perceptual_learning", "device_routing", "visual_augmentation"],
        format_func=lambda x: {"scanning": "تدريب المسح البصري", "perceptual_learning": "التعلم الإدراكي",
            "device_routing": "التوجيه الذكي للمعدات", "visual_augmentation": "التعزيز البصري"}.get(x, x),
        key=f"it_{pid}")

    if int_type == "scanning":
        col1, col2 = st.columns(2)
        blind_side = col1.selectbox("الجانب الأعمى", ["right", "left"], key=f"sc_s_{pid}")
        num_trials = col2.slider("المحاولات", 10, 50, 20, key=f"sc_n_{pid}")
        if st.button("تشغيل", key=f"run_sc_{pid}", type="primary"):
            result = run_intervention({"intervention_type": "scanning", "action": "simulate_session", "blind_side": blind_side, "num_trials": num_trials})
            s = result["session_summary"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("المحاولات", s["total_trials"]); c2.metric("الدقة", f"{s['accuracy_pct']}%")
            c3.metric("أعلى صعوبة", s["max_difficulty_reached"]); c4.metric("الانعكاسات", s["total_reversals"])
            _save_intervention(patient, "scanning", result)

    elif int_type == "perceptual_learning":
        col1, col2 = st.columns(2)
        sc = col1.slider("تباين البداية", 0.1, 1.0, 1.0, 0.05, key=f"pl_c_{pid}")
        num_t = col2.slider("المحاولات", 20, 100, 50, key=f"pl_n_{pid}")
        if st.button("تشغيل", key=f"run_pl_{pid}", type="primary"):
            result = run_intervention({"intervention_type": "perceptual_learning", "action": "simulate_session", "starting_contrast": sc, "num_trials": num_t})
            s = result["session_summary"]
            c1, c2, c3 = st.columns(3)
            c1.metric("المحاولات", s["total_trials"]); c2.metric("الدقة", f"{s['accuracy_pct']}%")
            c3.metric("التباين النهائي", f"{s['ending_contrast']:.3f}")
            _save_intervention(patient, "perceptual_learning", result)

    elif int_type == "device_routing":
        col1, col2 = st.columns(2)
        va = col1.number_input("VA", 0.0, 3.0, float(patient.get("va_logmar", 1.0) or 1.0), 0.1, key=f"dr_va_{pid}")
        vf = col2.number_input("مجال الرؤية", 0.0, 180.0, float(patient.get("visual_field_degrees", 60) or 60), 5.0, key=f"dr_vf_{pid}")
        cog = st.checkbox("تدهور إدراكي", value=patient.get("cognitive_status", "normal") != "normal", key=f"dr_cog_{pid}")
        dr_goals = st.multiselect("الأهداف", FUNCTIONAL_GOALS, default=patient.get("functional_goals", []),
            format_func=lambda x: FUNCTIONAL_GOALS_AR.get(x, x), key=f"dr_g_{pid}")
        if st.button("توصية الجهاز", key=f"run_dr_{pid}", type="primary"):
            result = run_intervention({"intervention_type": "device_routing", "va_logmar": va, "visual_field_degrees": vf,
                "has_cognitive_decline": cog, "functional_goals": dr_goals, "budget_usd": 5000})
            for w in result.get("guardrail_warnings", []):
                st.warning(f"[تنبيه] {w.get('message_ar', w)}")
            dev = result.get("primary_device")
            if dev:
                st.success(f"**الجهاز:** {dev['name_ar']} ({dev['name']}) — ${dev['price_usd']}")
                st.info(result.get("justification_ar", ""))
            _save_intervention(patient, "device_routing", result)

    elif int_type == "visual_augmentation":
        st.info("محاكاة معالجة صورة لأنماط ضعف البصر.")
        if st.button("تشغيل العرض", key=f"run_va_{pid}", type="primary"):
            result = run_intervention({"intervention_type": "visual_augmentation", "action": "demo"})
            for mode, data in result.get("demo_results", {}).items():
                if mode == "environment_analysis":
                    st.write(f"**تحليل البيئة:** إضاءة {data.get('estimated_lux', 'N/A')} لوكس")
                else:
                    st.write(f"**{mode}:** تم المعالجة تم")
            _save_intervention(patient, "visual_augmentation", result)


def _save_intervention(patient: dict, itype: str, result: dict):
    patient.setdefault("intervention_sessions", [])
    patient["intervention_sessions"].append({"timestamp": datetime.now().isoformat(), "type": itype, "result": result})
    save_patient(patient)
    st.session_state.patients[patient["id"]] = patient
    st.success("تم حفظ نتيجة الجلسة في ملف المريض")


# ═══════════════════════════════════════════════════════════════
# Tab: Documents
# ═══════════════════════════════════════════════════════════════

def render_documents_tab(patient: dict):
    pid = patient["id"]
    st.markdown("### التقارير والوثائق")
    st.caption("ولّد تقارير سريرية وخطابات إحالة بالذكاء الاصطناعي — تُحفظ تلقائياً.")

    prev_docs = patient.get("documents", [])
    if prev_docs:
        with st.expander(f"وثائق سابقة ({len(prev_docs)})", expanded=False):
            for d in reversed(prev_docs):
                st.write(f"**{d.get('type', '')}** — {d.get('timestamp', '')[:16]}")
                st.markdown(d.get("content", ""))
                st.markdown("---")

    doc_type = st.selectbox("نوع الوثيقة", ["تقرير شامل", "خطاب إحالة", "خطة علاجية"], key=f"doc_type_{pid}")

    if doc_type == "خطاب إحالة":
        specialty = st.selectbox("التخصص", ["ophthalmology", "neurology", "orthopedics", "cardiology",
            "pulmonology", "psychiatry", "psychology", "pediatrics", "ot", "om",
            "social_work", "optometry", "pain_management"], key=f"ref_spec_{pid}")

    if st.button(f"توليد {doc_type}", type="primary", key=f"gen_doc_{pid}"):
        with st.spinner("يولد الوثيقة..."):
            r_type = REHAB_TYPES.get(patient.get("rehabilitation_type", ""), "عام")
            goals_str = ", ".join(FUNCTIONAL_GOALS_AR.get(g, g) for g in patient.get("functional_goals", [])) or "لم تُحدد"
            if doc_type == "تقرير شامل":
                prompt = (f"أنشئ تقريراً سريرياً شاملاً لهذا المريض بصيغة SOAP.\n"
                    f"اسم المريض: {patient.get('name')}, العمر: {patient.get('age')}\n"
                    f"نوع التأهيل: {r_type}\n"
                    f"التشخيص: {patient.get('diagnosis_text')}\n"
                    f"الأهداف: {goals_str}\n"
                    f"عدد التقييمات: {len(patient.get('assessment_results', []))}\n"
                    f"عدد الجلسات: {len(patient.get('intervention_sessions', []))}\n"
                    f"عدد الخطط العلاجية: {len(patient.get('treatment_plans', []))}")
            elif doc_type == "خطاب إحالة":
                prompt = (f"أنشئ خطاب إحالة لتخصص {specialty} لهذا المريض.\n"
                    f"اسم المريض: {patient.get('name')}, العمر: {patient.get('age')}\n"
                    f"نوع التأهيل: {r_type}\n"
                    f"التشخيص: {patient.get('diagnosis_text')}")
            else:
                prompt = (f"أنشئ خطة علاجية تفصيلية لهذا المريض.\n"
                    f"نوع التأهيل: {r_type}\n"
                    f"التشخيص: {patient.get('diagnosis_text')}\n"
                    f"الأهداف: {goals_str}")

            result = chat_with_patient_context(prompt, patient)
            st.markdown(result["text"])

            patient.setdefault("documents", [])
            patient["documents"].append({
                "timestamp": datetime.now().isoformat(), "type": doc_type, "content": result["text"],
            })
            save_patient(patient)
            st.session_state.patients[pid] = patient
            st.success("تم حفظ الوثيقة في ملف المريض")


# ═══════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="sb-header">
            <div class="sb-logo-wrap">
              <svg width="72" height="72" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <circle cx="50" cy="50" r="46" fill="none" stroke="rgba(46,139,192,0.45)" stroke-width="1.5" stroke-dasharray="8 4">
                  <animateTransform attributeName="transform" type="rotate" values="0 50 50;360 50 50" dur="18s" repeatCount="indefinite"/>
                </circle>
                <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(11,132,87,0.3)" stroke-width="1" stroke-dasharray="4 6">
                  <animateTransform attributeName="transform" type="rotate" values="360 50 50;0 50 50" dur="12s" repeatCount="indefinite"/>
                </circle>
                <ellipse cx="50" cy="50" rx="30" ry="18" fill="#1E3A5F" stroke="#2E8BC0" stroke-width="1.8"/>
                <circle cx="50" cy="50" r="11" fill="#2E8BC0">
                  <animate attributeName="r" values="11;9;11" dur="3s" repeatCount="indefinite"/>
                  <animate attributeName="fill" values="#2E8BC0;#4FA8D8;#2E8BC0" dur="3s" repeatCount="indefinite"/>
                </circle>
                <circle cx="50" cy="50" r="5" fill="#0B1E3F"/>
                <circle cx="46" cy="46" r="2" fill="white" opacity="0.65"/>
                <line x1="50" y1="8" x2="50" y2="50" stroke="rgba(46,139,192,0.55)" stroke-width="1.5">
                  <animateTransform attributeName="transform" type="rotate" values="0 50 50;360 50 50" dur="5s" repeatCount="indefinite"/>
                </line>
                <circle cx="50" cy="50" r="20" fill="none" stroke="rgba(46,139,192,0.5)" stroke-width="1">
                  <animate attributeName="r" values="20;46;20" dur="4s" repeatCount="indefinite"/>
                  <animate attributeName="opacity" values="0.5;0;0.5" dur="4s" repeatCount="indefinite"/>
                </circle>
              </svg>
            </div>
            <h2 class="sb-title">مستشار التأهيل الطبي</h2>
            <p class="sb-subtitle">Medical Rehab AI Consultant</p>
            <div class="sb-model-badge">Claude Sonnet 4.6 · Extended Thinking</div>
        </div>
        <div class="sb-body">
        """, unsafe_allow_html=True)

        # API Status
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            st.markdown('<div style="text-align:center;margin-bottom:12px"><span class="badge badge-green">● API متصل</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="text-align:center;margin-bottom:12px"><span class="badge badge-red">○ API غير متصل</span></div>', unsafe_allow_html=True)
            st.error("ANTHROPIC_API_KEY غير موجود!")

        # Settings
        st.markdown('<div class="sb-section-label">الإعدادات</div>', unsafe_allow_html=True)
        st.session_state.use_thinking = st.toggle("تفعيل التفكير العميق", value=st.session_state.use_thinking, key="toggle_thinking")
        if st.session_state.use_thinking:
            st.session_state.thinking_budget = st.slider("حد التفكير (tokens)", 4000, 16000, st.session_state.thinking_budget, 1000, key="thinking_slider")

        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        # Tools
        st.markdown('<div class="sb-section-label">الأدوات المتاحة</div>', unsafe_allow_html=True)
        for icon, name, _ in TOOLS_MANIFEST:
            st.markdown(f"""
            <div class="tool-chip">
                <span class="tool-chip-icon">{icon}</span>
                <span class="tool-chip-name">{name}</span>
                <span class="tool-chip-badge">نشط</span>
            </div>""", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# Main Router
# ═══════════════════════════════════════════════════════════════

render_sidebar()

if st.session_state.current_page == "patient_file" and st.session_state.current_patient_id:
    pid = st.session_state.current_patient_id
    patient = st.session_state.patients.get(pid)
    if patient:
        render_patient_file(patient)
    else:
        st.error("المريض غير موجود")
        st.session_state.current_page = "registry"
        st.rerun()
else:
    render_patient_registry()
