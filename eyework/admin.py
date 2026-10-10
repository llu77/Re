"""
أداة المشغّل
============
تعمل بدور المالك (`EYEWORK_OWNER_DATABASE_URL`) من سطر الأوامر، لا من الويب:
خادم الويب لا يملك هذه الصلاحيات أصلاً.

    python -m eyework.admin create-user --login ali@example.sa --profession MARKETING [--name "علي"]
    python -m eyework.admin set-name --login ali@example.sa --name "علي" | --clear
    python -m eyework.admin set-profession --login ali@example.sa --profession STOREKEEPER
    python -m eyework.admin issue-signup-codes --count 10 [--hours 72] [--label riyadh-oct]
    python -m eyework.admin reissue-activation --login ali@example.sa
    python -m eyework.admin deactivate --login ali@example.sa
    python -m eyework.admin delete-user --login ali@example.sa --confirm-delete-all-data
    python -m eyework.admin purge

**الدعوة رابطٌ يُطبع، لا يُرسل.** لا بريد يخرج من التطبيق ولا يُخزَّن: المشغّل
يسلّم الرابط بنفسه، ويحفظ صلة الاسم بصاحبه خارج النظام. والرمز في جزء
الرابط بعد `#`، فلا يصل خادماً ولا سجلّاً ولا إحالة.

**اسم الدخول بحروفٍ لاتينية بسيطة.** التوحيد (NFKC) لا يجمع «أ» و«ا» ولا «ى»
و«ي»؛ اسمٌ عربي قد يُكتب عند الدخول بغير ما كُتب عند الدعوة فلا يطابق.

**الاحتفاظ.** `purge` يُشغَّل يومياً من مجدول النظام: الحملة المعتمدة أو
الملغاة تُحذف بعد تسعين يوماً، وغير المنتهية بعد ثلاثين يوماً من آخر تعديل،
والجلسات ورموز التفعيل والتسجيل بعد ثلاثين يوماً من انتهائها أو استعمالها،
وتحدّيات مفاتيح المرور حين تنتهي مهلتها (خمس دقائق)، ودفتر التسجيل بعد يومه.
ودفتر استدعاءات النموذج (`ai_requests`، أرقامٌ بلا محتوى) بعد ثلاثين يوماً —
وما بقي فيه مفتوحاً ساعةً انقطعت عمليّته يُغلق `ABANDONED` محسوباً — وتنبيهات
المراجِع التي لم يُعتمد عملها بعد ثلاثين يوماً؛ أما التنبيه المعتمد فيبقى مع
موضوعه وقراراته.

**التسجيل المفتوح.** حين يكون `EYEWORK_REGISTRATION=open` يُنشئ الزائر حسابه
بنفسه من المسار `/api/auth/register` بلا رمز، فلا يعرفه المشغّل. بريده غير
موثَّق هنا أيضاً: `reissue-activation` له يبقى بـ`--owner-verified` كحساب الرابط.
ومن سجّل أحدٌ ببريده قبله يكتب إلى `EYEWORK_SUPPORT_CONTACT` من ذلك البريد نفسه،
فيردّ المشغّل عليه ليتحقّق، ثم يحذف الحساب الدخيل
(`delete-user --login <البريد> --confirm-delete-all-data`) ليسجّل صاحب البريد
من جديد. وتوقّف التسجيل المفتوح يومَه (ستّون جواباً «مأخوذ») يظهر في سجلّ الخادم
(«قيد registration_open_paused على /api/auth/register»)، لا أمرَ له هنا.

**التسجيل برابط.** `issue-signup-codes` يطبع روابط تسجيلٍ لا تُربط ببريد، كلٌّ
لحسابٍ واحد. يفتح صاحبه الرابط فيكتب اسمه وتاريخ ميلاده وبريده وكلمة مروره
ويختار مهنته. والرمز يُقفل بعد ثلاث محاولاتٍ ببريدٍ مأخوذ: لا يصير أداة سؤالٍ عن
الناس. وتسمية الدفعة (`--label`) تقول من أين جاء حسابٌ إن أسيء استعماله.

**المهنة تُفتح بها البوابة.** حسابٌ ينشئه صاحبه يختار مهنته عند التسجيل؛ وحساب
الدعوة يسمّيها المشغّل. وتغييرها بعد ذلك للمشغّل وحده (`set-profession`). وحين
يغادر الحساب التسويق تُلغى حملاته المفتوحة في المعاملة نفسها (وتُحذف صورها):
لا يبقى عملٌ قائم في بوابةٍ لم تعد تُفتح له.

**الاسترداد.** رابط تفعيلٍ جديد (`reissue-activation`) يضع كلمة مرورٍ جديدة. لحساب
الدعوة يعرف المشغّل صاحبه؛ أما حساب التسجيل فبريده غير موثَّق، ومن يطلب رابطه
قد لا يكون صاحبه — فيُطلب `--owner-verified` تصريحاً بأن المشغّل تحقّق منه.

**الاسم اختياري.** يناديه به المساعد في الواجهة («أنا سيمبول، مساعدك الشخصي يا
علي»). يُخزَّن في قاعدة التطبيق وحدها ولا يصل مزوّد النموذج. الاسم الأول أو
الكنية تكفي: كل حرفٍ زائد بيانٌ عن صاحبه لا تحتاجه الواجهة.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import psycopg

from eyework import auth, config
from eyework.professions import NAMES, Profession

__all__ = ["main"]

ACTIVATION_HOURS = 72
_LOGIN = re.compile(r"^[a-z0-9._@+-]{3,254}$")

_CREATE_USER = "INSERT INTO users (login_hmac, profession) VALUES (%s, %s) RETURNING id"
_USER_BY_LOGIN = "SELECT id, is_active FROM users WHERE login_hmac = %s"
_CLOSE_TOKENS = "UPDATE activation_tokens SET used_at = now() WHERE user_id = %s AND used_at IS NULL"
_NEW_TOKEN = """
INSERT INTO activation_tokens (token_hash, user_id, expires_at)
VALUES (%s, %s, now() + make_interval(hours => %s))
"""
_DEACTIVATE = "UPDATE users SET is_active = false WHERE id = %s"
_ORIGIN = "SELECT self_registered FROM users WHERE id = %s"
_NEW_SIGNUP_CODE = """
INSERT INTO signup_codes (code_hash, label, expires_at)
VALUES (%s, %s, now() + make_interval(hours => %s))
"""
_CANCEL_OPEN_CAMPAIGNS = """
UPDATE campaigns SET status = 'CANCELLED'
 WHERE user_id = %s AND status IN ('DRAFT', 'COPY_PROPOSED', 'COPY_APPROVED')
"""
# FOR UPDATE: حملةٌ تُنشأ في اللحظة نفسها تقرأ المهنة FOR SHARE (محفّز الإدراج)،
# فإمّا تنتظر هذا الأمر وتُرفض، وإمّا ينتظرها فتظهر لإلغاء الحملات المفتوحة.
_PROFESSION_OF = "SELECT profession FROM users WHERE id = %s FOR UPDATE"
_SET_NAME = "UPDATE users SET display_name = %s WHERE id = %s"
_SET_PROFESSION = "UPDATE users SET profession = %s WHERE id = %s"
_REVOKE_ALL = "UPDATE sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL"
_DELETE_USER = "DELETE FROM users WHERE id = %s"

# محاولات اليوم تعدّها السقوف (اليومي والعام). حذف حملتها يمحوها فيستردّ
# صاحبها حصّةً دُفعت؛ فلا تُحذف حملةٌ فيها محاولةٌ عمرها دون يوم (الشرط الأخير
# في العبارتين).
_PURGE_FINAL = """
DELETE FROM campaigns c
 WHERE ((c.status = 'READY' AND c.ready_at < now() - interval '90 days')
     OR (c.status = 'CANCELLED' AND c.cancelled_at < now() - interval '90 days'))
   AND NOT EXISTS (SELECT 1 FROM generation_attempts a
                    WHERE a.campaign_id = c.id AND a.started_at > now() - interval '24 hours')
"""
#: الخمول من آخر نشاطٍ أيّاً كان: تعديل الحملة، أو تغيير الصورة، أو محاولة كتابة.
_PURGE_IDLE = """
DELETE FROM campaigns c
 WHERE c.status IN ('DRAFT', 'COPY_PROPOSED', 'COPY_APPROVED')
   AND GREATEST(
           c.updated_at,
           coalesce((SELECT i.updated_at FROM campaign_images i WHERE i.campaign_id = c.id), c.updated_at),
           coalesce((SELECT max(a.started_at) FROM generation_attempts a WHERE a.campaign_id = c.id), c.updated_at)
       ) < now() - interval '30 days'
   AND NOT EXISTS (SELECT 1 FROM generation_attempts a
                    WHERE a.campaign_id = c.id AND a.started_at > now() - interval '24 hours')
"""
_PURGE_SESSIONS = """
DELETE FROM sessions
 WHERE expires_at < now() - interval '30 days' OR revoked_at < now() - interval '30 days'
"""
_PURGE_TOKENS = """
DELETE FROM activation_tokens
 WHERE expires_at < now() - interval '30 days' OR used_at < now() - interval '30 days'
"""
#: أثر المحاولات المحذوفة لا يعدّه السقف بعد يومه.
_PURGE_TOMBSTONES = """
DELETE FROM attempt_tombstones WHERE started_at < now() - interval '24 hours'
"""
_PURGE_SIGNUP_CODES = """
DELETE FROM signup_codes
 WHERE expires_at < now() - interval '30 days' OR used_at < now() - interval '30 days'
"""
#: التحدّي لا يُقبل بعد مهلته ولا يُقرأ لشيء: لا سبب لبقائه.
_PURGE_PASSKEY_CHALLENGES = "DELETE FROM passkey_challenges WHERE expires_at < now()"
#: دفتر التسجيل تُعدّ منه سقوف آخر يوم وحدها؛ بعد يومه لا يُقرأ لشيء.
_PURGE_REGISTRATION_LEDGER = "DELETE FROM registration_ledger WHERE occurred_at < now() - interval '24 hours'"
#: استدعاءٌ بقي مفتوحاً ساعةً انقطعت عمليّته: يُغلق محسوباً، فلا يحجز مقعد صاحبه ولا يبقى مبهماً.
_PURGE_AI_ABANDONED = """
UPDATE ai_requests SET finished_at = now(), outcome = 'ABANDONED'
 WHERE finished_at IS NULL AND started_at < now() - interval '1 hour'
"""
#: الدفتر بلا محتوى، وسقوفه ليومٍ واحد؛ ثلاثون يوماً لمراجعة الكلفة ثم يُحذف.
_PURGE_AI_REQUESTS = "DELETE FROM ai_requests WHERE started_at < now() - interval '30 days'"
#: تنبيهٌ لم يُعتمد عمله في ثلاثين يوماً لا قرار ينتظره.
_PURGE_AI_OPEN_FLAGS = "DELETE FROM ai_flags WHERE closed_at IS NULL AND created_at < now() - interval '30 days'"
#: مسودات المخزون الخاملة ثلاثين يوماً (كل تعديلٍ في الأسطر يحدّث رأسها). المسجَّل لا يُحذف
#: إلا مع حسابه (inv_record_is_permanent).
_PURGE_INV_PURCHASE_DRAFTS = "DELETE FROM inv_purchases WHERE status = 'DRAFT' AND updated_at < now() - interval '30 days'"
_PURGE_INV_RETURN_DRAFTS = "DELETE FROM inv_returns WHERE status = 'DRAFT' AND updated_at < now() - interval '30 days'"
#: مكتب الدعم (0011): الإغلاق الآلي، ثم نصوص التذكرة بعد ثلاثين يوماً من إغلاقها، ثم التذكرة
#: وسجلّها بعد سنة، ثم الاقتراحات التي لم يمسّها الموظف. بلا جلسة: لا يُنسب شيءٌ منها إلى أحد.
_SUPPORT_CLOSE_RESOLVED = """
UPDATE support_tickets SET status = 'CLOSED', close_reason = 'AFTER_RESOLVED'
 WHERE status = 'RESOLVED' AND resolved_at < now() - interval '4 days'
"""
_SUPPORT_CLOSE_IDLE = """
UPDATE support_tickets SET status = 'CLOSED', close_reason = 'IDLE'
 WHERE status <> 'CLOSED' AND last_activity_at < now() - interval '90 days'
"""
_SUPPORT_WITHDRAW = """
UPDATE support_replies r SET state = 'WITHDRAWN', withdrawn_at = now()
  FROM support_tickets t
 WHERE t.id = r.ticket_id AND t.status = 'CLOSED' AND r.state IN ('READY', 'RELEASED')
"""
#: نصوص التذكرة بعد ثلاثين يوماً من إغلاقها (الشرط نفسه في الخطوات الستّ).
_SUPPORT_PURGE_FLAG_QUOTES = """
UPDATE support_flags f SET evidence = NULL FROM support_tickets t
 WHERE t.id = f.ticket_id AND f.evidence IS NOT NULL
   AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL AND t.closed_at < now() - interval '30 days'
"""
_SUPPORT_PURGE_DRAFTS = """
DELETE FROM support_drafts d USING support_tickets t
 WHERE t.id = d.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL AND t.closed_at < now() - interval '30 days'
"""
_SUPPORT_PURGE_REPLIES = """
DELETE FROM support_replies r USING support_tickets t
 WHERE t.id = r.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL AND t.closed_at < now() - interval '30 days'
"""
_SUPPORT_PURGE_MESSAGES = """
DELETE FROM support_messages m USING support_tickets t
 WHERE t.id = m.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL AND t.closed_at < now() - interval '30 days'
"""
_SUPPORT_PURGE_ESCALATIONS = """
DELETE FROM support_escalations e USING support_tickets t
 WHERE t.id = e.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL AND t.closed_at < now() - interval '30 days'
"""
_SUPPORT_TEXTS_EVENT = """
INSERT INTO support_events (user_id, ticket_id, event, actor)
SELECT t.user_id, t.id, 'TEXTS_PURGED', 'SYSTEM' FROM support_tickets t
 WHERE t.status = 'CLOSED' AND t.texts_purged_at IS NULL AND t.closed_at < now() - interval '30 days'
"""
_SUPPORT_TEXTS_MARK = """
UPDATE support_tickets t SET subject = NULL, customer_label = NULL, texts_purged_at = now()
 WHERE t.status = 'CLOSED' AND t.texts_purged_at IS NULL AND t.closed_at < now() - interval '30 days'
"""
_SUPPORT_PURGE_TICKETS = "DELETE FROM support_tickets WHERE status = 'CLOSED' AND closed_at < now() - interval '365 days'"
_SUPPORT_DISCARD_PROPOSALS = """
UPDATE kb_articles SET state = 'DISCARDED' WHERE state = 'PROPOSED' AND updated_at < now() - interval '30 days'
"""
_SUPPORT_PURGE_DISCARDED = "DELETE FROM kb_articles WHERE state = 'DISCARDED' AND discarded_at < now() - interval '30 days'"
#: خروج الحساب من الدعم الفني: تُسحب ردوده الحيّة وتُغلق تذاكره المفتوحة (لا تُحذف؛ يمحو
#: purge نصوصها بعد ثلاثين يوماً).
_SUPPORT_LEAVE_REPLIES = "UPDATE support_replies SET state = 'WITHDRAWN', withdrawn_at = now() WHERE user_id = %s AND state IN ('READY', 'RELEASED')"
_SUPPORT_LEAVE_TICKETS = """
UPDATE support_tickets SET status = 'CLOSED', close_reason = 'PROFESSION_CHANGED' WHERE user_id = %s AND status <> 'CLOSED'
"""


class AdminError(Exception):
    """خطأٌ يُطبع للمشغّل ويُنهي الأمر بحالة 1."""


def _owner_url() -> str:
    value = os.environ.get("EYEWORK_OWNER_DATABASE_URL", "").strip()
    if not value:
        raise AdminError("EYEWORK_OWNER_DATABASE_URL غير مضبوط")
    return value


def _settings() -> tuple[bytes, str]:
    try:
        key = config.login_key()
        origin = config.public_origin()
    except config.ConfigError as exc:
        raise AdminError(str(exc)) from exc
    return key, origin


def _login(raw: str) -> str:
    login = auth.normalize_login(raw)
    if not _LOGIN.match(login):
        raise AdminError("اسم الدخول: من 3 إلى 254 حرفاً من a-z و0-9 و. _ @ + -")
    return login


def _name(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        return auth.check_name(raw)
    except auth.RegistrationInvalid as exc:
        raise AdminError("الاسم: حتى 30 حرفاً عربياً أو لاتينياً، بمسافاتٍ مفردة، بلا أرقامٍ ولا تشكيل") from exc


def _fragment_value(text: str) -> str:
    """ترميز ما يحتاج ترميزاً من الحروف المسموحة في اسم الدخول وحدها."""
    return text.replace("%", "%25").replace("@", "%40").replace("+", "%2B")


def _issue(cursor, user_id, origin: str, login: str) -> str:
    cursor.execute(_CLOSE_TOKENS, (user_id,))
    token = auth.new_token()
    cursor.execute(_NEW_TOKEN, (auth.hash_token(token), user_id, ACTIVATION_HOURS))
    return f"{origin}/#activate={token}&u={_fragment_value(login)}"


def _find(cursor, key: bytes, login: str):
    cursor.execute(_USER_BY_LOGIN, (auth.login_hmac(key, login),))
    row = cursor.fetchone()
    if row is None:
        raise AdminError("لا حساب بهذا الاسم")
    return row


def _profession(raw: str) -> Profession:
    try:
        return Profession(raw.strip().upper())
    except ValueError as exc:
        raise AdminError("المهنة: " + " أو ".join(p.value for p in Profession)) from exc


def create_user(raw_login: str, raw_profession: str, raw_name: str | None = None) -> str:
    key, origin = _settings()
    login = _login(raw_login)
    profession = _profession(raw_profession)
    name = _name(raw_name)
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        try:
            cursor.execute(_CREATE_USER, (auth.login_hmac(key, login), profession.value))
        except psycopg.errors.UniqueViolation as exc:
            # لا يُقترح إصدار رابطٍ لحسابٍ قائم: قد يكون غريبٌ سجّل بهذا البريد أولاً.
            raise AdminError("البريد اسم دخولٍ لحسابٍ قائم. إن كان حساباً أنشأه صاحبه بالتسجيل"
                             " فقد لا يكون صاحب البريد؛ لا تُصدر له رابطاً قبل التحقّق") from exc
        user_id = cursor.fetchone()[0]
        if name is not None:
            cursor.execute(_SET_NAME, (name, user_id))
        return _issue(cursor, user_id, origin, login)


def set_name(raw_login: str, raw_name: str | None) -> None:
    """يضع الاسم الذي يناديه به المساعد، أو يمحوه (`None`)."""
    key, _ = _settings()
    name = _name(raw_name)
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, _ = _find(cursor, key, _login(raw_login))
        cursor.execute(_SET_NAME, (name, user_id))


def set_profession(raw_login: str, raw_profession: str) -> int:
    """
    ينقل الحساب إلى بوابة مهنةٍ أخرى، ويُرجع عدد ما أُغلق: الحملات المفتوحة أو التذاكر.

    حين يغادر التسويق تُلغى حملاته غير المنتهية في المعاملة نفسها (ويحذف محفّز
    الإلغاء صورها)؛ الحملات الجاهزة تبقى إلى الاحتفاظ المعتاد. وحين يغادر الدعم الفني
    تُسحب ردوده التي لم تُرسل وتُغلق تذاكره، وتُمحى نصوصها في موعدها.
    """
    key, _ = _settings()
    profession = _profession(raw_profession)
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, _ = _find(cursor, key, _login(raw_login))
        cursor.execute(_PROFESSION_OF, (user_id,))
        current = cursor.fetchone()[0]
        if current == profession.value:
            raise AdminError("الحساب في هذه المهنة أصلاً")
        cancelled = 0
        if current == Profession.MARKETING.value:
            cursor.execute(_CANCEL_OPEN_CAMPAIGNS, (user_id,))
            cancelled = cursor.rowcount
        if current == Profession.SUPPORT.value:
            cursor.execute(_SUPPORT_LEAVE_REPLIES, (user_id,))
            cursor.execute(_SUPPORT_LEAVE_TICKETS, (user_id,))
            cancelled = cursor.rowcount
        cursor.execute(_SET_PROFESSION, (profession.value, user_id))
        return cancelled


#: أكثر من هذا في دفعةٍ واحدة يعني أن الروابط تُوزَّع بلا معرفةٍ بأصحابها.
SIGNUP_BATCH_MAX = 200
#: نظير القيد signup_window في الترحيل 0005.
SIGNUP_HOURS_MAX = 720


def issue_signup_codes(count: int, hours: int = 72, label: str | None = None) -> list[str]:
    """روابط تسجيل، كلٌّ لحسابٍ واحد. الرمز في جزء الرابط بعد `#` فلا يصل خادماً."""
    if not 1 <= count <= SIGNUP_BATCH_MAX:
        raise AdminError(f"العدد: من 1 إلى {SIGNUP_BATCH_MAX}")
    if not 1 <= hours <= SIGNUP_HOURS_MAX:
        raise AdminError(f"المدّة: من ساعة إلى {SIGNUP_HOURS_MAX} ساعة")
    if label is not None and not re.fullmatch(r"[A-Za-z0-9 _.-]{1,40}", label):
        raise AdminError("اسم الدفعة: حتى 40 حرفاً لاتينياً أو رقماً أو مسافة أو . _ -")
    _, origin = _settings()
    links = []
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        for _ in range(count):
            code = auth.new_token()
            cursor.execute(_NEW_SIGNUP_CODE, (auth.hash_token(code), label, hours))
            links.append(f"{origin}/#signup={code}")
    return links


def reissue_activation(raw_login: str, owner_verified: bool = False) -> str:
    """
    رابطٌ جديد، والقديم يُغلق. هذا طريق الاسترداد الوحيد.

    حساب التسجيل بريده غير موثَّق: من يطلب رابطه قد لا يكون صاحبه، فلا يصدر
    الرابط إلا بتصريح المشغّل أنه تحقّق ممّن يطلبه (`owner_verified`).
    """
    key, origin = _settings()
    login = _login(raw_login)
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, is_active = _find(cursor, key, login)
        if not is_active:
            raise AdminError("الحساب معطّل")
        cursor.execute(_ORIGIN, (user_id,))
        if cursor.fetchone()[0] and not owner_verified:
            raise AdminError("حسابٌ أنشأه صاحبه بالتسجيل وبريده غير موثَّق. تحقّق ممّن يطلب الرابط"
                             " ثم أعد الأمر مع --owner-verified")
        return _issue(cursor, user_id, origin, login)


def deactivate(raw_login: str) -> None:
    key, _ = _settings()
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, _ = _find(cursor, key, _login(raw_login))
        cursor.execute(_DEACTIVATE, (user_id,))
        cursor.execute(_REVOKE_ALL, (user_id,))


def delete_user(raw_login: str) -> None:
    """يحذف الحساب وكل ما يتبعه: الجلسات، والرموز، والحملات، والنسخ، والصور."""
    key, _ = _settings()
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, _ = _find(cursor, key, _login(raw_login))
        cursor.execute(_DELETE_USER, (user_id,))


def purge() -> dict[str, int]:
    counts = {}
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        for name, statement in (("final_campaigns", _PURGE_FINAL), ("idle_campaigns", _PURGE_IDLE),
                                ("sessions", _PURGE_SESSIONS), ("activation_tokens", _PURGE_TOKENS),
                                ("signup_codes", _PURGE_SIGNUP_CODES), ("attempt_tombstones", _PURGE_TOMBSTONES),
                                ("passkey_challenges", _PURGE_PASSKEY_CHALLENGES),
                                ("registration_ledger", _PURGE_REGISTRATION_LEDGER),
                                # بهذا الترتيب: يُغلق المهجور قبل أن يُحذف القديم، وتُحذف التنبيهات
                                # المفتوحة بعد أن يُفكّ ما يبقى منها عن دفترٍ حُذف.
                                ("ai_abandoned", _PURGE_AI_ABANDONED), ("ai_requests", _PURGE_AI_REQUESTS),
                                ("ai_open_flags", _PURGE_AI_OPEN_FLAGS),
                                ("inv_purchase_drafts", _PURGE_INV_PURCHASE_DRAFTS),
                                ("inv_return_drafts", _PURGE_INV_RETURN_DRAFTS),
                                ("support_closed_resolved", _SUPPORT_CLOSE_RESOLVED),
                                ("support_closed_idle", _SUPPORT_CLOSE_IDLE),
                                ("support_replies_withdrawn", _SUPPORT_WITHDRAW),
                                ("support_flag_quotes", _SUPPORT_PURGE_FLAG_QUOTES),
                                ("support_drafts", _SUPPORT_PURGE_DRAFTS),
                                ("support_replies", _SUPPORT_PURGE_REPLIES),
                                ("support_messages", _SUPPORT_PURGE_MESSAGES),
                                ("support_escalations", _SUPPORT_PURGE_ESCALATIONS),
                                ("support_texts_events", _SUPPORT_TEXTS_EVENT),
                                ("support_texts_purged", _SUPPORT_TEXTS_MARK),
                                ("support_tickets", _SUPPORT_PURGE_TICKETS),
                                ("kb_proposals_discarded", _SUPPORT_DISCARD_PROPOSALS),
                                ("kb_articles_deleted", _SUPPORT_PURGE_DISCARDED)):
            cursor.execute(statement)
            counts[name] = cursor.rowcount
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eyework.admin", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create-user", "reissue-activation", "deactivate", "delete-user", "set-name",
                 "set-profession"):
        command = commands.add_parser(name)
        # بلا --login يُسأل عنه: سطر الأوامر يُحفظ في سجلّ الصدفة، فتتجمّع فيه
        # قائمة المستخدمين التي لا تحفظها القاعدة إلا HMAC.
        command.add_argument("--login")
        if name == "delete-user":
            command.add_argument("--confirm-delete-all-data", action="store_true", required=True)
        if name in ("create-user", "set-profession"):
            command.add_argument("--profession", required=True, choices=[p.value for p in Profession])
        if name == "create-user":
            command.add_argument("--name")
        if name == "reissue-activation":
            command.add_argument("--owner-verified", action="store_true")
        if name == "set-name":
            choice = command.add_mutually_exclusive_group(required=True)
            choice.add_argument("--name")
            choice.add_argument("--clear", action="store_true")
    commands.add_parser("purge")
    codes = commands.add_parser("issue-signup-codes")
    codes.add_argument("--count", type=int, required=True)
    codes.add_argument("--hours", type=int, default=72)
    codes.add_argument("--label")
    args = parser.parse_args(argv)
    if getattr(args, "login", "absent") is None:
        args.login = input("اسم الدخول: ").strip()

    try:
        if args.command == "create-user":
            print(create_user(args.login, args.profession, args.name))
        elif args.command == "set-profession":
            cancelled = set_profession(args.login, args.profession)
            print("نُقل الحساب إلى بوابة " + NAMES[Profession(args.profession)]
                  + (f"، وأُلغيت {cancelled} حملةً مفتوحة" if cancelled else ""))
        elif args.command == "issue-signup-codes":
            print("\n".join(issue_signup_codes(args.count, args.hours, args.label)))
        elif args.command == "set-name":
            set_name(args.login, None if args.clear else args.name)
            print("مُحي الاسم" if args.clear else "وُضع الاسم")
        elif args.command == "reissue-activation":
            print(reissue_activation(args.login, args.owner_verified))
        elif args.command == "deactivate":
            deactivate(args.login)
            print("عُطّل الحساب وأُلغيت جلساته")
        elif args.command == "delete-user":
            delete_user(args.login)
            print("حُذف الحساب وكل بياناته")
        else:
            for name, count in purge().items():
                print(f"{name}: {count}")
    except AdminError as exc:
        print(f"خطأ: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
