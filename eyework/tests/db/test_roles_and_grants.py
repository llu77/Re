"""
الأدوار والمنح
==============
دور الويب `eyework_app` هو كل ما يحمله الخادم، فما لا يملكه هذا الدور لا
يصل إليه خطأٌ في الشيفرة ولا حقنٌ فيها. الضمانة: لا يتجاوز العزل، ولا يحذف
ولا يُفرغ جدولاً، ولا يكتب إلا الأعمدة المسمّاة، ولا يلمس جداول الهوية، ولا
يستدعي إلا الدوالّ المعلنة. ولا يتصل بالقاعدة أحدٌ غيره وغير مالكها.

يُفحص كلٌّ مرتين: في الكتالوج، فيظهر منحٌ زائد لم يجرّبه أحد؛ وبالمحاولة
الفعلية بدور الويب، فيثبت أن الرفض يقع فعلاً وأن سببه الصلاحية لا غيرها.
"""

from __future__ import annotations

import functools
import hashlib
import io

import psycopg
import pytest
from PIL import Image

from eyework.images import process
from eyework.tests.conftest import (
    DESCRIPTION,
    TITLE,
    add_version,
    as_user,
    create_campaign,
    row_version,
)

ALL_TABLES = frozenset({
    "schema_migrations", "users", "activation_tokens", "sessions", "campaign_transition",
    "campaigns", "generation_attempts", "copy_versions", "campaign_images",
    # 0005: المهن ورموز التسجيل وأثر المحاولات المحذوفة — للمالك وحده؛ الويب
    # يصلها عبر دوالّ.
    "professions", "signup_codes", "attempt_tombstones",
    # 0006: مفاتيح المرور وتحدّياتها — هويةٌ كالجلسات.
    "passkeys", "passkey_challenges",
    # 0008: دفتر التسجيل — وقتٌ وطريقٌ ونتيجة، للمالك وحده؛ منه تُعدّ السقوف.
    "registration_ledger",
    # 0009: أدوات النموذج وسقوفها (للمالك وحده)، ودفتر استدعاءاته، وتنبيهات المراجِع
    # وقرارات أصحابها (يقرؤها الويب صفوفَه وحدها، ويكتبها بالدوالّ).
    "ai_features", "ai_requests", "ai_flags", "ai_flag_decisions",
    # 0010: المخزون — الإعداد والعدّادات (للمالك وحده) والموردون والأصناف والفواتير وأسطرها
    # والمرتجعات وأسطرها والسندات والحركات ودفتر المشتريات وتنبيهات القواعد.
    "inv_settings", "inv_counters", "inv_suppliers", "inv_supplier_reps", "inv_categories", "inv_items", "inv_purchases",
    "inv_purchase_lines", "inv_returns", "inv_return_lines", "inv_count_sessions", "inv_vouchers", "inv_count_lines",
    "inv_movements", "inv_ledger", "inv_review_flags",
    # 0011: مكتب الدعم الفني.
    "support_settings", "support_sla_targets", "support_ticket_transition", "support_tickets", "support_messages",
    "kb_articles", "kb_versions", "support_drafts", "support_draft_citations", "support_replies", "support_flags",
    "support_escalations", "support_events",
})
READABLE = frozenset({
    "campaign_transition", "campaigns", "generation_attempts", "copy_versions", "campaign_images",
    # 0009: القراءة بالجدول كلّه تحت عزل الصفّ؛ لا سياسة كتابةٍ لدور الويب عليها.
    "ai_requests", "ai_flags", "ai_flag_decisions",
    # 0010: القراءة بالجدول كلّه تحت عزل الصفّ، والكتابة بالأعمدة المسمّاة أو بالدوالّ وحدها.
    "inv_settings", "inv_suppliers", "inv_supplier_reps", "inv_categories", "inv_items", "inv_purchases", "inv_purchase_lines",
    "inv_returns", "inv_return_lines", "inv_count_sessions", "inv_vouchers", "inv_count_lines", "inv_movements", "inv_ledger",
    "inv_review_flags",
    # 0011: كل جداول المكتب عدا آلة الحالات (تُقرأ عبر الدوالّ).
    "support_settings", "support_sla_targets", "support_tickets", "support_messages", "kb_articles", "kb_versions",
    "support_drafts", "support_draft_citations", "support_replies", "support_flags", "support_escalations", "support_events",
})
IDENTITY_TABLES = ("public.users", "public.sessions", "public.activation_tokens",
                   "public.passkeys", "public.passkey_challenges")
COLUMN_WRITES = {
    ("campaigns", "INSERT"): {"user_id"},
    # current_version_id: الاستعادة. المحفّز يقصرها على أحدث نسخة أو أساس الحالية.
    ("campaigns", "UPDATE"): {"status", "current_version_id", "budget_sar", "days"},
    ("copy_versions", "INSERT"): {
        "campaign_id", "user_id", "attempt_id", "title", "description", "edit_presets",
        "edit_note", "warnings", "served_model", "prompt_version", "api_request_id",
        # 0003: كلمة المساعد للمستخدم مع النسخة.
        "assistant_note",
    },
    ("campaign_images", "INSERT"): {"campaign_id", "user_id", "jpeg", "width", "height", "sha256"},
    ("campaign_images", "UPDATE"): {"jpeg", "width", "height", "sha256"},
    # 0010: ما يكتبه الويب في المخزون؛ الأرقام والأرصدة والحالات والمجاميع تكتبها الدوالّ والمحفّزات.
    ("inv_settings", "INSERT"): {"user_id", "cost_includes_vat", "store_name", "store_location"},
    ("inv_settings", "UPDATE"): {"cost_includes_vat", "store_name", "store_location"},
    ("inv_suppliers", "INSERT"): {"user_id", "name", "vat_number", "cr_number", "phone", "note"},
    ("inv_suppliers", "UPDATE"): {"name", "vat_number", "cr_number", "phone", "note", "is_active"},
    ("inv_supplier_reps", "INSERT"): {"user_id", "supplier_id", "name", "mobile", "is_default"},
    ("inv_supplier_reps", "UPDATE"): {"name", "mobile", "is_default", "is_active"},
    ("inv_categories", "INSERT"): {"user_id", "name"},
    ("inv_categories", "UPDATE"): {"name", "is_active"},
    ("inv_items", "INSERT"): {"user_id", "name", "supplier_code", "barcode", "kind", "unit", "category_id", "vat_category",
                              "vat_exemption_reason", "price_halalas", "selling_price_halalas", "selling_price_includes_vat",
                              "reorder_level_milli", "target_level_milli", "preferred_supplier_id", "note"},
    ("inv_items", "UPDATE"): {"name", "supplier_code", "barcode", "kind", "unit", "category_id", "vat_category",
                              "vat_exemption_reason", "price_halalas", "selling_price_halalas", "selling_price_includes_vat",
                              "reorder_level_milli", "target_level_milli", "preferred_supplier_id", "note", "is_active"},
    ("inv_purchases", "INSERT"): {"user_id", "supplier_id", "supplier_invoice_no", "invoice_date", "prices_include_vat",
                                  "printed_total_halalas", "printed_vat_halalas", "note", "rep_id", "delivery_note_no", "received_on"},
    ("inv_purchases", "UPDATE"): {"supplier_id", "supplier_invoice_no", "invoice_date", "prices_include_vat",
                                  "printed_total_halalas", "printed_vat_halalas", "note", "rep_id", "delivery_note_no", "received_on"},
    ("inv_purchase_lines", "INSERT"): {"purchase_id", "user_id", "item_id", "quantity_milli", "unit_price_halalas", "discount_halalas",
                                       "vat_category", "received_quantity_milli"},
    ("inv_purchase_lines", "UPDATE"): {"item_id", "quantity_milli", "unit_price_halalas", "discount_halalas", "vat_category",
                                       "received_quantity_milli"},
    ("inv_returns", "INSERT"): {"user_id", "purchase_id", "return_date", "reason", "note", "rep_id"},
    ("inv_returns", "UPDATE"): {"return_date", "reason", "note", "rep_id", "credit_note_no", "credit_note_date"},
    ("inv_count_sessions", "UPDATE"): {"blind", "note"},
    ("inv_count_lines", "UPDATE"): {"counted_milli", "unit_cost_halalas", "reason", "note"},
    ("inv_return_lines", "INSERT"): {"return_id", "user_id", "line_no", "quantity_milli"},
    ("inv_return_lines", "UPDATE"): {"quantity_milli"},
}
APP_FUNCTIONS = frozenset({
    "ew_login_lookup", "ew_open_session", "ew_resolve_session", "ew_revoke_session",
    "ew_activate", "ew_begin_generation", "ew_finish_generation",
    # 0003: اسم صاحب الجلسة وحده، لا قائمة المستخدمين.
    "ew_my_display_name",
    # 0005: التسجيل برمزه وسقفه اليومي، ومهنة صاحب الجلسة، وحذفه حسابه بنفسه.
    "ew_signup_code_usable", "ew_register", "ew_my_profession", "ew_delete_me",
    # 0006: تحدّي مفتاح المرور، والدخول به، وإضافته لصاحب الجلسة وقراءة مفاتيحه وحده.
    "ew_passkey_take_challenge", "ew_passkey_lookup", "ew_passkey_signed_in",
    "ew_passkey_add", "ew_my_passkeys",
    # 0007: جلسة كلمة المرور بوقتها، وتحدّيا الدخول والإضافة منفصلين (بدل ew_passkey_challenge).
    "ew_open_password_session", "ew_passkey_login_challenge", "ew_passkey_add_challenge",
    # 0008: التسجيل المفتوح وما يمنعه الآن، وحدّ الكتابة اليومي لصاحب الجلسة، وطريقة
    # استخدامه قراءةً وكتابة، ونسخة موافقته وقبوله نسخةً أحدث.
    "ew_register_open", "ew_open_registration_blocker", "ew_my_generation_limit",
    "ew_my_ui_size", "ew_set_my_ui_size", "ew_my_terms_version", "ew_accept_terms",
    # 0009: قرار صاحب التنبيه، وإغلاق استدعاءٍ لم يُنتج شيئاً، وحصّته من كل أداة،
    # وسؤال المساعد بدايةً ونهاية.
    "ew_ai_decide", "ew_ai_request_fail", "ew_ai_my_usage", "ew_assistant_begin", "ew_assistant_finish",
    # 0010: الأفعال (التسجيل والعكس والسندات وحذف السطور ونبذ المسودة ومراجعة سيمبول بدايةً
    # وتسجيلاً)، والحساب والبصمات وتنبيهات القواعد بصلاحية من يسأل، وتاريخ الرياض لتنبيه «تاريخٌ قديم».
    "ew_inv_post_purchase", "ew_inv_post_return", "ew_inv_reverse_purchase", "ew_inv_stock_voucher",
    "ew_inv_remove_purchase_line", "ew_inv_remove_return_line", "ew_inv_discard_draft",
    "ew_inv_review_begin", "ew_inv_review_record",
    "ew_inv_count_open", "ew_inv_count_add_item", "ew_inv_count_refresh", "ew_inv_count_post", "ew_inv_count_cancel",
    "ew_inv_text_ok", "ew_inv_qty_ok", "ew_inv_vat_bp", "ew_inv_doc_no_ok", "ew_inv_doc_key", "ew_inv_name_key", "ew_inv_phone_ok",
    "ew_inv_purchase_calc", "ew_inv_purchase_digest", "ew_inv_return_digest", "ew_inv_purchase_flags",
    "ew_inv_return_flags", "ew_inv_flag_keys", "ew_riyadh_today",
    # 0011: واجهة المكتب، ودوالّ القيود والأعمدة المولّدة.
    "ew_support_accept_notice", "ew_support_save_settings", "ew_support_create_ticket", "ew_support_add_message",
    "ew_support_set_ticket", "ew_support_begin_draft", "ew_support_record_draft", "ew_support_finish_call",
    "ew_support_reject_draft", "ew_support_prepare_reply", "ew_support_review_begin", "ew_support_review_record",
    "ew_support_ack_flag", "ew_support_release_reply", "ew_support_confirm_reply", "ew_support_escalate",
    "ew_support_return_escalation", "ew_support_resolve", "ew_support_reopen", "ew_support_follow_up", "ew_support_close_due",
    "ew_kb_create", "ew_kb_add_version", "ew_kb_publish", "ew_kb_set_state", "ew_kb_mark_review", "ew_kb_search",
    "ew_kb_begin_proposal", "ew_kb_record_proposal", "ew_kb_review_begin", "ew_kb_current_digest", "ew_kb_review_record",
    "ew_support_text_ok", "ew_support_contact_free", "ew_support_kb_clean", "ew_kb_norm", "ew_support_priority_for",
    "ew_support_priority_rank",
    # تستدعيها السياسات والقيود بصلاحية من يكتب:
    "ew_current_user", "ew_budget_allowed", "ew_is_billable", "ew_jpeg_has_no_metadata",
})
#: ما لا يستدعيه الويب: محفّزاتٌ ودوالّ قيودٍ، وما تستدعيه دوالّ المالك بصلاحيتها.
#: دالّةٌ جديدة تُعلَن هنا أو في APP_FUNCTIONS، وإلا لم يُقرَّر لمن هي.
INTERNAL_FUNCTIONS = frozenset({
    # 0002: حرّاس الحملة والصورة والنسخة والمحاولة.
    "ew_campaign_insert_guard", "ew_campaign_guard", "ew_purge_image_on_cancel", "ew_image_guard",
    "ew_version_insert_guard", "ew_version_becomes_current", "ew_forbid_update", "ew_attempt_settle_once",
    # 0004: لمس الصورة عند استبدالها.
    "ew_image_touch",
    # 0005: أثر المحاولة المحذوفة. (تاريخ الرياض صار للويب في 0010.)
    "ew_attempt_tombstone",
    # 0008: حسابٌ مفتوحٌ جديد، وما يمنع تسجيلاً بطريقٍ الآن (من الدفتر وحده).
    "ew_new_open_account", "ew_registration_blocker",
    # 0009: فحص نصّ النموذج، وأثر الاستدعاء المحذوف وحارس التنبيه، والسقوف والدفتر
    # (الفتح والإغلاق والإنفاق)، وقفل الموضوع وكتابة التنبيهات والبوابة والنسيان والمحو.
    "ew_ai_text_ok", "ew_ai_request_tombstone", "ew_ai_flag_guard", "ew_ai_spend", "ew_ai_request_open",
    "ew_ai_request_settle", "ew_ai_lock_subject", "ew_ai_flags_put", "ew_ai_gate", "ew_ai_forget_subject",
    "ew_ai_erase_subject",
    # 0010: المهنة، والرقم التالي، وقفل الأصناف، وفحص الإقرار، وحرّاس الجداول ومحفّزات الثبات.
    "ew_inv_require_storekeeper", "ew_inv_next_no", "ew_inv_lock_items", "ew_inv_check_ack", "ew_inv_rep_ok", "ew_inv_count_voucher",
    "ew_inv_settings_guard", "ew_inv_supplier_guard", "ew_inv_supplier_rep_guard", "ew_inv_category_guard", "ew_inv_item_guard",
    "ew_inv_purchase_insert_guard", "ew_inv_purchase_guard", "ew_inv_purchase_line_guard", "ew_inv_return_insert_guard",
    "ew_inv_return_guard", "ew_inv_return_line_guard", "ew_inv_count_session_guard", "ew_inv_count_line_guard",
    "ew_inv_movement_insert", "ew_inv_keep_record", "ew_inv_keep_posted_lines",
    # 0011: المحفّزات والداخلية.
    "ew_support_me", "ew_support_require_notice", "ew_support_ticket_for", "ew_support_log", "ew_support_request_for",
    "ew_kb_version_digest", "ew_support_settings_defaults", "ew_support_ticket_insert_guard", "ew_support_ticket_update_guard",
    "ew_support_ticket_status_event", "ew_support_message_insert_guard", "ew_support_draft_insert_guard",
    "ew_support_draft_update_guard", "ew_support_citation_guard", "ew_support_draft_grounded", "ew_support_reply_insert_guard",
    "ew_support_reply_update_guard", "ew_support_flag_insert_guard", "ew_support_flag_update_guard",
    "ew_kb_article_insert_guard", "ew_kb_article_update_guard", "ew_kb_version_insert_guard", "ew_kb_version_update_guard",
})


def _assert_permission_denied(caught: pytest.ExceptionInfo, table: str) -> None:
    message = caught.value.diag.message_primary or ""
    assert "permission denied" in message and table in message, message


@functools.cache
def _clean_jpeg() -> tuple[bytes, int, int]:
    buffer = io.BytesIO()
    Image.effect_noise((640, 480), 40).convert("RGB").save(buffer, "JPEG")
    image = process(buffer.getvalue())
    return image.jpeg, image.width, image.height


def _attach_image(app, user_id, campaign) -> None:
    jpeg, width, height = _clean_jpeg()
    as_user(app, user_id)
    with app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (campaign, user_id, jpeg, width, height, hashlib.sha256(jpeg).digest()),
        )


def _campaign(app, user_id, *, with_image: bool = True):
    campaign = create_campaign(app, user_id, with_image=False)
    if with_image:
        _attach_image(app, user_id, campaign)
    return campaign


def _open_attempt(app, user_id, campaign):
    as_user(app, user_id)
    with app.cursor() as cursor:
        cursor.execute(
            "SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)",
            (campaign, row_version(app, campaign)),
        )
        return cursor.fetchone()[0]


# ── الدور نفسه ─────────────────────────────────────────────────────────

def test_app_role_cannot_bypass_isolation(owner):
    """دورٌ بـSUPERUSER أو BYPASSRLS يرى صفوف الجميع مهما كانت السياسات، وبـCREATEROLE يمنح نفسه ما شاء."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb"
            " FROM pg_roles WHERE rolname = 'eyework_app'"
        )
        assert cursor.fetchone() == (False, False, False, False)


def test_app_role_inherits_from_no_role(owner):
    """عضويةٌ في دور المالك تمنح دور الويب كل ما يملكه المالك دون منحٍ ظاهرٍ على أي جدول."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT roleid::regrole::text FROM pg_auth_members"
            " WHERE member = 'eyework_app'::regrole"
        )
        assert cursor.fetchall() == []


# ── الجداول ────────────────────────────────────────────────────────────

def test_app_holds_no_delete_or_truncate_on_any_table(owner):
    """الحذف من التطبيق يمحو أثر المحاولات المحسوبة وما اعتمده المستخدم؛ لا جدول يُستثنى."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname,"
            "       has_table_privilege('eyework_app', c.oid, 'DELETE'),"
            "       has_table_privilege('eyework_app', c.oid, 'TRUNCATE')"
            "  FROM pg_class c"
            " WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p', 'v', 'm', 'f')"
        )
        rows = cursor.fetchall()
    assert {name for name, _, _ in rows} >= ALL_TABLES
    assert [(name, d, t) for name, d, t in rows if d or t] == []


@pytest.mark.parametrize("statement", [
    "DELETE FROM campaigns",
    "DELETE FROM generation_attempts",
    "DELETE FROM copy_versions",
    "DELETE FROM campaign_images",
    "DELETE FROM campaign_transition",
    "DELETE FROM users",
    "DELETE FROM sessions",
    "DELETE FROM activation_tokens",
    "DELETE FROM schema_migrations",
    "DELETE FROM passkeys",
    "DELETE FROM passkey_challenges",
    "DELETE FROM registration_ledger",
    "DELETE FROM ai_features",
    "DELETE FROM ai_requests",
    "DELETE FROM ai_flags",
    "DELETE FROM ai_flag_decisions",
    "TRUNCATE campaigns",
    "TRUNCATE generation_attempts",
    "TRUNCATE copy_versions",
    "TRUNCATE campaign_images",
    "TRUNCATE campaign_transition",
    "TRUNCATE users",
    "TRUNCATE sessions",
    "TRUNCATE activation_tokens",
    "TRUNCATE schema_migrations",
    "TRUNCATE passkeys",
    "TRUNCATE passkey_challenges",
    "TRUNCATE registration_ledger",
    "TRUNCATE ai_features",
    "TRUNCATE ai_requests",
    "TRUNCATE ai_flags",
    "TRUNCATE ai_flag_decisions",
    *[f"{verb} {table}" for verb in ("DELETE FROM", "TRUNCATE") for table in (
        "inv_settings", "inv_counters", "inv_suppliers", "inv_supplier_reps", "inv_categories", "inv_items", "inv_purchases",
        "inv_purchase_lines", "inv_returns", "inv_return_lines", "inv_count_sessions", "inv_vouchers", "inv_count_lines",
        "inv_movements", "inv_ledger", "inv_review_flags",
        "support_settings", "support_sla_targets", "support_ticket_transition", "support_tickets", "support_messages",
        "kb_articles", "kb_versions", "support_drafts", "support_draft_citations", "support_replies", "support_flags",
        "support_escalations", "support_events")],
])
def test_app_delete_and_truncate_are_refused(app, two_users, statement):
    """المنح في الكتالوج قد يغيب ويبقى الحذف ممكناً بطريقٍ آخر؛ المحاولة نفسها تُرفض."""
    as_user(app, two_users[0])
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement)
    _assert_permission_denied(caught, statement.split()[-1])


def test_table_level_privileges_are_exactly_select_on_data_tables(owner):
    """منحٌ على مستوى الجدول يتخطّى المنح بالأعمدة كلها: INSERT واحدةٌ على campaigns تكتب status."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, p.privilege"
            "  FROM pg_class c"
            "  CROSS JOIN unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE',"
            "                          'REFERENCES', 'TRIGGER']) AS p(privilege)"
            " WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p', 'v', 'm', 'f')"
            "   AND has_table_privilege('eyework_app', c.oid, p.privilege)"
        )
        assert set(cursor.fetchall()) == {(table, "SELECT") for table in READABLE}


def test_column_level_privileges_are_exactly_the_declared_ones(owner):
    """عمودٌ زائد في المنح يترك العميل يكتب ما يكتبه المحفّز وحده: النسخة المعتمدة، والعدّاد، والأوقات."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, a.attname"
            "  FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped"
            " WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p')"
        )
        columns: dict[str, set[str]] = {}
        for table, column in cursor.fetchall():
            columns.setdefault(table, set()).add(column)
        cursor.execute(
            "SELECT c.relname, p.privilege, a.attname"
            "  FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped"
            "  CROSS JOIN unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'REFERENCES']) AS p(privilege)"
            " WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p')"
            "   AND has_column_privilege('eyework_app', c.oid, a.attnum, p.privilege)"
        )
        granted: dict[tuple[str, str], set[str]] = {}
        for table, privilege, column in cursor.fetchall():
            granted.setdefault((table, privilege), set()).add(column)
    expected = {(table, "SELECT"): columns[table] for table in READABLE}
    expected.update(COLUMN_WRITES)
    assert granted == expected


@pytest.mark.parametrize("statement", [
    "UPDATE campaigns SET approved_version_id = current_version_id WHERE id = %s",
    "UPDATE campaigns SET row_version = row_version WHERE id = %s",
    "UPDATE campaigns SET ready_at = now() WHERE id = %s",
    "UPDATE campaigns SET approved_at = now() WHERE id = %s",
    "UPDATE campaigns SET cancelled_at = now() WHERE id = %s",
    "UPDATE campaigns SET user_id = user_id WHERE id = %s",
    "UPDATE campaigns SET created_at = now() WHERE id = %s",
])
def test_app_cannot_update_managed_campaign_columns(app, two_users, statement):
    """العميل لا يختار ما يُعتمد ولا متى، ولا يعيد العدّاد ليمرّر ضغطةً مكرّرة."""
    user = two_users[0]
    campaign = _campaign(app, user)
    add_version(app, user, campaign)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement, (campaign,))
    _assert_permission_denied(caught, "campaigns")


@pytest.mark.parametrize("statement", [
    "INSERT INTO campaigns (user_id, status) VALUES (%s, 'READY')",
    "INSERT INTO campaigns (user_id, row_version) VALUES (%s, 100)",
    "INSERT INTO campaigns (user_id, budget_sar, days) VALUES (%s, 500, 5)",
    "INSERT INTO campaigns (user_id, approved_at) VALUES (%s, now())",
    "INSERT INTO campaigns (id, user_id) VALUES (gen_random_uuid(), %s)",
])
def test_app_cannot_insert_a_campaign_past_its_draft_state(app, two_users, statement):
    """حملةٌ تُولد READY بمالٍ دون نصٍّ معتمد تتخطّى كل خطوة يراها صاحبها."""
    user = two_users[0]
    as_user(app, user)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement, (user,))
    _assert_permission_denied(caught, "campaigns")


@pytest.mark.parametrize("statement", [
    "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
    " served_model, prompt_version, version) VALUES (%s, %s, %s, %s, %s, 'claude-opus-5-5', 'test', 1)",
    "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
    " served_model, prompt_version, created_at)"
    " VALUES (%s, %s, %s, %s, %s, 'claude-opus-5-5', 'test', now() - interval '1 day')",
    "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
    " served_model, prompt_version, id)"
    " VALUES (%s, %s, %s, %s, %s, 'claude-opus-5-5', 'test', gen_random_uuid())",
])
def test_app_cannot_insert_managed_version_columns(app, two_users, statement):
    """رقم النسخة ووقتها يكتبهما المحفّز؛ عميلٌ يختارهما يعيد ترتيب ما رآه المستخدم."""
    user = two_users[0]
    campaign = _campaign(app, user)
    attempt = _open_attempt(app, user, campaign)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement, (campaign, user, attempt, TITLE, DESCRIPTION))
    _assert_permission_denied(caught, "copy_versions")


def test_app_cannot_update_a_version(app, two_users):
    """النسخة لا تُعدَّل بعد كتابتها؛ والرفض هنا من المنح، قبل محفّز «إلحاقٍ فقط»."""
    user = two_users[0]
    campaign = _campaign(app, user)
    add_version(app, user, campaign)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute("UPDATE copy_versions SET title = %s WHERE campaign_id = %s", (TITLE, campaign))
    _assert_permission_denied(caught, "copy_versions")


@pytest.mark.parametrize("statement", [
    "INSERT INTO generation_attempts (campaign_id, user_id, kind) VALUES (%s, %s, 'INITIAL')",
    "UPDATE generation_attempts SET finished_at = now(), outcome = 'DISCARDED'"
    " WHERE campaign_id = %s AND user_id = %s",
])
def test_app_writes_attempts_only_through_the_capped_functions(app, two_users, statement):
    """محاولةٌ تُكتب مباشرةً تتخطّى سقوف الكلفة، ومحاولةٌ تُغلق مباشرةً تفتح الباب لأخرى."""
    user = two_users[0]
    campaign = _campaign(app, user)
    _open_attempt(app, user, campaign)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement, (campaign, user))
    _assert_permission_denied(caught, "generation_attempts")


@pytest.mark.parametrize("statement", [
    "UPDATE campaign_images SET user_id = %s WHERE campaign_id = %s",
    "UPDATE campaign_images SET campaign_id = campaign_id WHERE user_id = %s AND campaign_id = %s",
    "UPDATE campaign_images SET created_at = now() WHERE user_id = %s AND campaign_id = %s",
])
def test_app_cannot_move_or_redate_an_image(app, two_users, statement):
    """صورةٌ تُنقل إلى حملةٍ أو مستخدمٍ آخر تظهر تحت نصٍّ لم يُكتب عنها."""
    user = two_users[0]
    campaign = _campaign(app, user)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement, (user, campaign))
    _assert_permission_denied(caught, "campaign_images")


def test_app_cannot_backdate_an_image(app, two_users):
    """وقت الصورة يكتبه المحفّز؛ الإدراج لا يحمله."""
    user = two_users[0]
    campaign = _campaign(app, user, with_image=False)
    jpeg, width, height = _clean_jpeg()
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, now() - interval '1 day')",
            (campaign, user, jpeg, width, height, hashlib.sha256(jpeg).digest()),
        )
    _assert_permission_denied(caught, "campaign_images")


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_identity_tables_grant_nothing_beyond_the_owner(owner, table):
    """منحٌ واحد على جداول الهوية يكشف من يستخدم التطبيق — وهي معلومةٌ صحّية."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT NULL::text, a.grantee::regrole::text, a.privilege_type"
            "  FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a"
            " WHERE c.oid = %s::regclass AND a.grantee <> c.relowner"
            " UNION ALL"
            " SELECT att.attname::text, a.grantee::regrole::text, a.privilege_type"
            "  FROM pg_attribute att CROSS JOIN LATERAL aclexplode(att.attacl) a"
            " WHERE att.attrelid = %s::regclass",
            (table, table),
        )
        assert cursor.fetchall() == []
        cursor.execute(
            "SELECT has_table_privilege('eyework_app', %s::regclass,"
            "                           'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'),"
            "       has_any_column_privilege('eyework_app', %s::regclass, 'SELECT, INSERT, UPDATE, REFERENCES')",
            (table, table),
        )
        assert cursor.fetchone() == (False, False)


@pytest.mark.parametrize(("table", "statement"), [
    ("users", "INSERT INTO users (login_hmac) VALUES (sha256(convert_to(%s::text, 'UTF8')))"),
    ("sessions", "INSERT INTO sessions (user_id, token_hash, expires_at)"
                 " VALUES (%s, sha256('forged'::bytea), now() + interval '1 day')"),
    ("activation_tokens", "INSERT INTO activation_tokens (user_id, token_hash, expires_at)"
                          " VALUES (%s, sha256('forged'::bytea), now() + interval '1 hour')"),
    ("passkeys", "INSERT INTO passkeys (user_id, credential_id, public_key)"
                 " VALUES (%s, 'forged'::bytea, 'forged'::bytea)"),
    ("passkey_challenges", "INSERT INTO passkey_challenges (challenge_hash, purpose, user_id, expires_at)"
                           " VALUES (sha256('forged'::bytea), 'ADD', %s, now() + interval '1 minute')"),
])
def test_app_cannot_insert_into_identity_tables(app, two_users, table, statement):
    """
    جلسةٌ يكتبها دور الويب بنفسه دخولٌ بلا كلمة مرور، ورمزٌ يزرعه يستردّ به حساب غيره،
    ومفتاحٌ يزرعه بلا تحقّقٍ يُدخل صاحبَ المفتاح الخاص إلى أيّ حساب.
    """
    user = two_users[0]
    as_user(app, user)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement, (user,))
    _assert_permission_denied(caught, table)


@pytest.mark.parametrize(("table", "statement"), [
    ("users", "UPDATE users SET is_active = true"),
    ("sessions", "UPDATE sessions SET revoked_at = NULL"),
    ("activation_tokens", "UPDATE activation_tokens SET used_at = NULL"),
    ("passkeys", "UPDATE passkeys SET sign_count = 0"),
    ("passkey_challenges", "UPDATE passkey_challenges SET used_at = NULL"),
])
def test_app_cannot_update_identity_tables(app, two_users, table, statement):
    """جلسةٌ مُبطلة تعود، ورمزٌ مستعمل يُفتح ثانية. بلا شرطٍ يقرأ عموداً، فغياب SELECT لا يحجب منحَ UPDATE زائداً."""
    as_user(app, two_users[0])
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement)
    _assert_permission_denied(caught, table)


def test_app_cannot_create_objects_in_the_schema(owner):
    """من يُنشئ في public يظلّل جدولاً أو دالّةً تستدعيها شيفرة المالك."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT has_schema_privilege('eyework_app', 'public', 'CREATE')")
        assert cursor.fetchone()[0] is False
        cursor.execute(
            "SELECT a.privilege_type FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a"
            " WHERE n.nspname = 'public' AND a.grantee = 0"
        )
        assert cursor.fetchall() == []


# ── الدوالّ ────────────────────────────────────────────────────────────

def test_security_definer_functions_pin_search_path_with_pg_temp_last(owner):
    """دالّةٌ بصلاحية المالك ومسارها مفتوح تنفّذ كائناً زرعه غيره؛ وpg_temp غير المسمّى يُبحث فيه أولاً."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT p.oid::regprocedure::text, p.proconfig FROM pg_proc p"
            " WHERE p.pronamespace = 'public'::regnamespace"
        )
        rows = cursor.fetchall()
    # كل دالّة، لا دوالّ SECURITY DEFINER وحدها: دالّة قيدٍ أو محفّزٍ بلا مسارٍ
    # مثبَّت تبحث في pg_temp أولاً عن أسماء الجداول.
    assert len(rows) >= len(APP_FUNCTIONS)
    unpinned = []
    for function, config in rows:
        paths = [entry.split("=", 1)[1] for entry in config or () if entry.startswith("search_path=")]
        if not paths or [part.strip() for part in paths[0].split(",")][-1] != "pg_temp":
            unpinned.append((function, config))
    assert unpinned == []


def test_no_function_is_executable_by_public(owner):
    """EXECUTE لـPUBLIC افتراضيٌّ في Postgres؛ ينسى الترحيل سحبه فيستدعي أيّ دورٍ دالّةً بصلاحية المالك."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT p.oid::regprocedure::text"
            "  FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a"
            " WHERE p.pronamespace = 'public'::regnamespace AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'"
        )
        assert cursor.fetchall() == []


def test_app_executes_exactly_the_declared_interface(owner):
    """دالّة محفّزٍ يستدعيها الويب مباشرةً تعمل خارج الصفّ الذي صُمّمت له."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT p.proname FROM pg_proc p"
            " WHERE p.pronamespace = 'public'::regnamespace"
            "   AND has_function_privilege('eyework_app', p.oid, 'EXECUTE')"
        )
        assert {row[0] for row in cursor.fetchall()} == APP_FUNCTIONS


def test_every_function_in_the_schema_is_declared_web_facing_or_internal(owner):
    """ترحيلٌ يضيف دالّةً دون أن يقرّر من يستدعيها يترك سؤال «من يصلها؟» بلا جواب."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT DISTINCT p.proname FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace")
        functions = {row[0] for row in cursor.fetchall()}
    assert not (APP_FUNCTIONS & INTERNAL_FUNCTIONS)
    assert functions == APP_FUNCTIONS | INTERNAL_FUNCTIONS


# ── القاعدة ────────────────────────────────────────────────────────────

def test_public_cannot_connect_or_create_temporary_objects(owner):
    """CONNECT وTEMPORARY لـPUBLIC افتراضيّان؛ بقاؤهما يفتح القاعدة لكل دورٍ في العنقود."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT a.privilege_type"
            "  FROM pg_database d CROSS JOIN LATERAL aclexplode(coalesce(d.datacl, acldefault('d', d.datdba))) a"
            " WHERE d.datname = current_database() AND a.grantee = 0"
        )
        assert cursor.fetchall() == []


def test_only_the_app_role_is_granted_on_the_database(owner):
    """منحٌ لدورٍ ثالث، أو TEMPORARY لدور الويب، بابٌ لم يُقرَّر."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT a.grantee::regrole::text, a.privilege_type"
            "  FROM pg_database d CROSS JOIN LATERAL aclexplode(coalesce(d.datacl, acldefault('d', d.datdba))) a"
            " WHERE d.datname = current_database() AND a.grantee <> d.datdba"
        )
        assert cursor.fetchall() == [("eyework_app", "CONNECT")]


@pytest.mark.parametrize("role", ["app_patient", "app_practitioner"])
def test_clinical_platform_roles_cannot_connect(owner, role):
    """أدوار المنصّة السريرية في العنقود نفسه؛ اتصالها هنا يجمع بيانات المنصّتين."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role,))
        if cursor.fetchone() is None:
            pytest.skip(f"الدور {role} غير موجود في هذا العنقود")
        cursor.execute(
            "SELECT has_database_privilege(%s, current_database(), 'CONNECT, TEMPORARY')", (role,)
        )
        assert cursor.fetchone()[0] is False


def test_no_other_role_in_the_cluster_can_connect(owner):
    """دورٌ يُضاف إلى العنقود لاحقاً لا يرث اتصالاً بهذه القاعدة."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT r.rolname FROM pg_roles r, pg_database d"
            " WHERE d.datname = current_database() AND NOT r.rolsuper"
            "   AND r.oid <> d.datdba AND r.rolname <> 'eyework_app'"
            "   AND has_database_privilege(r.oid, d.oid, 'CONNECT, TEMPORARY')"
        )
        assert cursor.fetchall() == []


@pytest.mark.parametrize("target", ["NULL", "gen_random_uuid()"])
def test_the_displayed_version_cannot_be_pointed_anywhere(app, two_users, target):
    """
    منحُ `current_version_id` للاستعادة لا يفتح بابها: المحفّز لا يقبل إلا أحدث
    نسخة أو أساس الحالية، والمفتاح الأجنبي يرفض ما ليس من نسخ الحملة.
    """
    user = two_users[0]
    campaign = _campaign(app, user)
    add_version(app, user, campaign)
    statement = {
        "NULL": "UPDATE campaigns SET current_version_id = NULL WHERE id = %s",
        "gen_random_uuid()": "UPDATE campaigns SET current_version_id = gen_random_uuid() WHERE id = %s",
    }[target]
    with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation)) as caught, \
            app.cursor() as cursor:
        cursor.execute(statement, (campaign,))
    assert caught.value.diag.constraint_name in (
        "current_version_target", "copy_states_have_copy", "current_version_belongs")
