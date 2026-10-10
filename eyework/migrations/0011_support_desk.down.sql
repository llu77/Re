-- ════════════════════════════════════════════════════════════════════════
-- 0011_support_desk — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- يُعيد المخطّط إلى ما بعد 0010 بالضبط. الجداول تسقط بسياساتها ومحفّزاتها، والدوالّ
-- تُسقط صراحةً. لا شيء في 0009 تغيّر هنا: صفوف ai_features للدعم من 0009 وتبقى.
--
-- **ما يضيع.** التذاكر ورسائلها وقاعدة المعرفة وسجلّ القرارات تُحذف كلها: لا مكان لها في
-- مخطّط 0010. وما قاله سيمبول عن ردٍّ أو مقالةٍ يُحذف معها؛ والدفتر (ai_requests) يبقى
-- فلا يُفرغ التراجعُ السقوف.
-- ════════════════════════════════════════════════════════════════════════

DELETE FROM ai_flags WHERE subject_kind IN ('SUPPORT_REPLY', 'KB_ARTICLE');

-- الدوالّ التي تُرجع صفوف الجداول أولاً، ثم الجداول، ثم دوالّ محفّزاتها وقيودها.
DROP FUNCTION IF EXISTS ew_kb_review_record(uuid, jsonb, jsonb);
DROP FUNCTION IF EXISTS ew_kb_current_digest(uuid);
DROP FUNCTION IF EXISTS ew_kb_review_begin(uuid, smallint);
DROP FUNCTION IF EXISTS ew_kb_record_proposal(uuid, text, text, text, text, text, jsonb);
DROP FUNCTION IF EXISTS ew_kb_begin_proposal(uuid);
DROP FUNCTION IF EXISTS ew_kb_search(text, integer);
DROP FUNCTION IF EXISTS ew_kb_mark_review(uuid, integer, boolean);
DROP FUNCTION IF EXISTS ew_kb_set_state(uuid, integer, text);
DROP FUNCTION IF EXISTS ew_kb_publish(uuid, integer, smallint);
DROP FUNCTION IF EXISTS ew_kb_add_version(uuid, integer, text, text, text, text, text);
DROP FUNCTION IF EXISTS ew_kb_create(uuid, text, text, text, text, text, uuid);
DROP FUNCTION IF EXISTS ew_support_close_due();
DROP FUNCTION IF EXISTS ew_support_follow_up(uuid, uuid, text, smallint);
DROP FUNCTION IF EXISTS ew_support_reopen(uuid, integer);
DROP FUNCTION IF EXISTS ew_support_resolve(uuid, integer, text, boolean);
DROP FUNCTION IF EXISTS ew_support_return_escalation(uuid, integer, text);
DROP FUNCTION IF EXISTS ew_support_escalate(uuid, integer, text, text);
DROP FUNCTION IF EXISTS ew_support_confirm_reply(uuid, boolean);
DROP FUNCTION IF EXISTS ew_support_release_reply(uuid, text, bytea);
DROP FUNCTION IF EXISTS ew_support_ack_flag(uuid, text, text);
DROP FUNCTION IF EXISTS ew_support_review_record(uuid, jsonb, jsonb);
DROP FUNCTION IF EXISTS ew_support_review_begin(uuid);
DROP FUNCTION IF EXISTS ew_support_prepare_reply(uuid, integer, uuid, uuid, text, boolean, text, text, jsonb);
DROP FUNCTION IF EXISTS ew_support_reject_draft(uuid, text, text);
DROP FUNCTION IF EXISTS ew_support_finish_call(uuid, text, jsonb);
DROP FUNCTION IF EXISTS ew_support_record_draft(uuid, uuid, text, text, text, text, text, text, text, text, boolean,
                                                text, text, text[], text, uuid, jsonb, jsonb);
DROP FUNCTION IF EXISTS ew_support_begin_draft(uuid, integer);
DROP FUNCTION IF EXISTS ew_support_set_ticket(uuid, integer, text, text, text, uuid);
DROP FUNCTION IF EXISTS ew_support_add_message(uuid, integer, text, text, smallint, uuid);
DROP FUNCTION IF EXISTS ew_support_create_ticket(uuid, text, text, text, text, text, text, smallint);
DROP FUNCTION IF EXISTS ew_support_save_settings(text, jsonb);
DROP FUNCTION IF EXISTS ew_support_accept_notice(text);
DROP FUNCTION IF EXISTS ew_support_request_for(uuid, uuid, text);
DROP FUNCTION IF EXISTS ew_kb_version_digest(uuid, smallint);
DROP FUNCTION IF EXISTS ew_support_log(uuid, uuid, uuid, text, text, uuid, uuid, uuid, text);
DROP FUNCTION IF EXISTS ew_support_ticket_for(uuid, uuid, integer);
DROP FUNCTION IF EXISTS ew_support_require_notice(uuid);
DROP FUNCTION IF EXISTS ew_support_me(boolean);

DROP TABLE IF EXISTS support_events;
DROP TABLE IF EXISTS support_escalations;
DROP TABLE IF EXISTS support_flags;
ALTER TABLE IF EXISTS support_messages DROP CONSTRAINT IF EXISTS support_message_reply_fk;
DROP TABLE IF EXISTS support_replies;
DROP TABLE IF EXISTS support_draft_citations;
DROP TABLE IF EXISTS support_drafts;
DROP TABLE IF EXISTS kb_versions;
DROP TABLE IF EXISTS kb_articles;
DROP TABLE IF EXISTS support_messages;
DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS support_ticket_transition;
DROP TABLE IF EXISTS support_sla_targets;
DROP TABLE IF EXISTS support_settings;

DROP FUNCTION IF EXISTS ew_support_events_keep();
DROP FUNCTION IF EXISTS ew_support_event_update_guard();
DROP FUNCTION IF EXISTS ew_kb_version_update_guard();
DROP FUNCTION IF EXISTS ew_kb_version_insert_guard();
DROP FUNCTION IF EXISTS ew_kb_article_update_guard();
DROP FUNCTION IF EXISTS ew_kb_article_insert_guard();
DROP FUNCTION IF EXISTS ew_support_flag_update_guard();
DROP FUNCTION IF EXISTS ew_support_flag_insert_guard();
DROP FUNCTION IF EXISTS ew_support_reply_update_guard();
DROP FUNCTION IF EXISTS ew_support_reply_insert_guard();
DROP FUNCTION IF EXISTS ew_support_draft_grounded();
DROP FUNCTION IF EXISTS ew_support_citation_guard();
DROP FUNCTION IF EXISTS ew_support_draft_update_guard();
DROP FUNCTION IF EXISTS ew_support_draft_insert_guard();
DROP FUNCTION IF EXISTS ew_support_message_insert_guard();
DROP FUNCTION IF EXISTS ew_support_ticket_status_event();
DROP FUNCTION IF EXISTS ew_support_ticket_update_guard();
DROP FUNCTION IF EXISTS ew_support_ticket_insert_guard();
DROP FUNCTION IF EXISTS ew_support_settings_defaults();
DROP FUNCTION IF EXISTS ew_support_priority_rank(text);
DROP FUNCTION IF EXISTS ew_support_priority_for(text, text, boolean);
DROP FUNCTION IF EXISTS ew_kb_norm(text);
DROP FUNCTION IF EXISTS ew_support_kb_clean(text);
DROP FUNCTION IF EXISTS ew_support_contact_free(text);
DROP FUNCTION IF EXISTS ew_support_text_ok(text, boolean);
