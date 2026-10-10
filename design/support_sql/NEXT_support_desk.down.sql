-- ════════════════════════════════════════════════════════════════════════
-- NEXT_support_desk — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- يُعيد المخطّط إلى ما بعد 0007 بالضبط. الجداول تسقط بسياساتها ومحفّزاتها، والدوالّ
-- تُسقط صراحةً، وew_begin_generation تعود بجسم 0007 حرفاً بحرف (مولَّدٌ منه لا معاد كتابته).
--
-- **ما يضيع.** التذاكر ورسائلها وقاعدة المعرفة وسجلّ القرارات تُحذف كلها: لا مكان لها في
-- مخطّط 0007. واستدعاءات النموذج في آخر يوم تترك آثارها في attempt_tombstones (محفّز
-- الحذف يكتبها قبل سقوطه)، فلا يُفرغ التراجعُ السقفَ العام.
-- ════════════════════════════════════════════════════════════════════════

-- الآثار أولاً، والمحفّز ما زال قائماً: حذف الاستدعاءات صراحةً يكتب أثر كلٍّ منها.
DELETE FROM support_ai_calls;

CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
    fresh   boolean;
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- الكلفة تُفرض حيث تقع: حسابٌ نُقل إلى مهنةٍ أخرى لا يكتب لحملةٍ قديمة.
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND profession = 'MARKETING') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    SELECT * INTO c FROM campaigns WHERE id = p_campaign AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF c.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF p_kind NOT IN ('INITIAL','EDIT')
       OR (p_kind = 'INITIAL' AND (c.status <> 'DRAFT' OR p_expected_version IS NOT NULL))
       OR (p_kind = 'EDIT' AND (c.status <> 'COPY_PROPOSED' OR c.current_version_id IS DISTINCT FROM p_expected_version)) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_wrong_state';
    END IF;
    SELECT sha256 INTO image FROM campaign_images WHERE campaign_id = p_campaign;
    IF image IS NULL THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_needs_image';
    END IF;
    IF EXISTS (SELECT 1 FROM generation_attempts
                WHERE user_id = uid AND finished_at IS NULL
                  AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_in_progress';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND started_at > now() - interval '10 minutes') >= 6 THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_rate';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= 40 THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_daily_cap';
    END IF;
    -- الحساب المفتوح الجديد: عشرة في اليوم. وقفل صفّ المستخدم أعلاه يجعل العدّ والإدراج ذرّيين.
    fresh := ew_new_open_account(uid);
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE user_id = uid AND ew_is_billable(outcome)
                     AND started_at > now() - interval '24 hours') >= 10 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_account_cap';
    END IF;
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    -- حصّة الحسابات الجديدة كلّها من السقف العام، تحت القفل نفسه. أثر المحاولة
    -- المحذوفة يُعدّ فيها أيضاً.
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
               + (SELECT count(*) FROM attempt_tombstones
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256, new_account)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image, fresh)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;

-- الدوالّ التي تُرجع صفوف الجداول أولاً، ثم الجداول، ثم دوالّ محفّزاتها وقيودها.
DROP FUNCTION IF EXISTS ew_support_my_ai_usage();
DROP FUNCTION IF EXISTS ew_kb_record_review(uuid, jsonb, integer, integer, text, text, text);
DROP FUNCTION IF EXISTS ew_kb_begin_review(uuid, smallint);
DROP FUNCTION IF EXISTS ew_kb_record_proposal(uuid, text, text, text, text, text, integer, integer, text, text, text);
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
DROP FUNCTION IF EXISTS ew_support_release_reply(uuid, text, bytea, boolean);
DROP FUNCTION IF EXISTS ew_support_ack_flag(uuid, text, text);
DROP FUNCTION IF EXISTS ew_support_record_review(uuid, jsonb, integer, integer, text, text, text);
DROP FUNCTION IF EXISTS ew_support_begin_review(uuid);
DROP FUNCTION IF EXISTS ew_support_prepare_reply(uuid, integer, uuid, uuid, text, boolean, text, text, jsonb);
DROP FUNCTION IF EXISTS ew_support_reject_draft(uuid, text, text);
DROP FUNCTION IF EXISTS ew_support_finish_call(uuid, text, integer, integer, text, text, text);
DROP FUNCTION IF EXISTS ew_support_record_draft(uuid, text, text, text, text, text, text, text, text, boolean, text,
                                                text, text[], text, uuid, jsonb, integer, integer, text, text, text);
DROP FUNCTION IF EXISTS ew_support_begin_draft(uuid, integer);
DROP FUNCTION IF EXISTS ew_support_set_ticket(uuid, integer, text, text, text, uuid);
DROP FUNCTION IF EXISTS ew_support_add_message(uuid, integer, text, text, smallint, uuid);
DROP FUNCTION IF EXISTS ew_support_create_ticket(uuid, text, text, text, text, text, text, smallint);
DROP FUNCTION IF EXISTS ew_support_save_settings(text, jsonb);
DROP FUNCTION IF EXISTS ew_support_accept_notice(text);
DROP FUNCTION IF EXISTS ew_support_ai_settle(uuid, uuid, text, text, integer, integer, text, text, text, boolean);
DROP FUNCTION IF EXISTS ew_support_ai_open(uuid, text, uuid, uuid, uuid, smallint, uuid);
DROP FUNCTION IF EXISTS ew_ai_spend(boolean);
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
DROP TABLE IF EXISTS support_ai_calls;
DROP TABLE IF EXISTS support_messages;
DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS support_ticket_transition;
DROP TABLE IF EXISTS support_ai_limits;
DROP TABLE IF EXISTS support_sla_targets;
DROP TABLE IF EXISTS support_settings;

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
DROP FUNCTION IF EXISTS ew_support_ai_tombstone();
DROP FUNCTION IF EXISTS ew_support_priority_rank(text);
DROP FUNCTION IF EXISTS ew_support_priority_for(text, text, boolean);
DROP FUNCTION IF EXISTS ew_kb_norm(text);
DROP FUNCTION IF EXISTS ew_support_kb_clean(text);
DROP FUNCTION IF EXISTS ew_support_contact_free(text);
DROP FUNCTION IF EXISTS ew_support_text_ok(text, boolean);
