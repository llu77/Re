SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;
CREATE FUNCTION public.ew_accept_terms(p_version text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    accepted text;
BEGIN
    IF p_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    SELECT terms_version INTO accepted FROM users WHERE id = ew_current_user() AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF accepted > p_version THEN
        RAISE EXCEPTION 'older' USING ERRCODE = 'check_violation', CONSTRAINT = 'terms_version_backwards';
    END IF;
    UPDATE users SET terms_version = p_version, terms_accepted_at = now() WHERE id = ew_current_user();
END
$$;
ALTER FUNCTION public.ew_accept_terms(p_version text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid;
BEGIN
    UPDATE activation_tokens t SET used_at = now()
      FROM users u
     WHERE t.token_hash = p_token AND t.used_at IS NULL AND t.expires_at > now()
       AND u.id = t.user_id AND u.is_active AND u.login_hmac = p_login
    RETURNING t.user_id INTO uid;
    IF uid IS NULL THEN
        RETURN NULL;
    END IF;
    UPDATE users SET password_hash = p_password_hash, activated_at = coalesce(activated_at, now())
     WHERE id = uid;
    UPDATE sessions SET revoked_at = now() WHERE user_id = uid AND revoked_at IS NULL;
    DELETE FROM passkeys WHERE user_id = uid;
    RETURN uid;
END
$$;
ALTER FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_ai_spend(p_new_only boolean) RETURNS bigint
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT (SELECT count(*) FROM generation_attempts
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM support_ai_calls
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM attempt_tombstones
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
$$;
ALTER FUNCTION public.ew_ai_spend(p_new_only boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_attempt_settle_once() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF OLD.finished_at IS NOT NULL THEN
        RAISE EXCEPTION 'settled' USING ERRCODE = 'check_violation', CONSTRAINT = 'attempt_settled';
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_attempt_settle_once() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_attempt_tombstone() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, new_account)
        VALUES (OLD.started_at, OLD.outcome, OLD.new_account);
    END IF;
    RETURN OLD;
END
$$;
ALTER FUNCTION public.ew_attempt_tombstone() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_begin_generation(p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
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
    -- support: السقف العام يعدّ استدعاءات المكتب مع المحاولات وآثارها.
    IF ew_ai_spend(false) >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    -- حصّة الحسابات الجديدة كلّها من السقف العام، تحت القفل نفسه. أثر المحاولة
    -- المحذوفة يُعدّ فيها أيضاً.
    -- support: وكذلك استدعاءات المكتب من حساباتٍ جديدة.
    IF fresh AND ew_ai_spend(true) >= 400 THEN
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
ALTER FUNCTION public.ew_begin_generation(p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_budget_allowed(v integer) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT (v BETWEEN 50 AND 1000 AND v % 50 = 0) OR (v BETWEEN 1250 AND 5000 AND v % 250 = 0)
$$;
ALTER FUNCTION public.ew_budget_allowed(v integer) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_campaign_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    newest   uuid;
    previous uuid;
BEGIN
    IF OLD.status = 'CANCELLED' OR (OLD.status = 'READY' AND NEW.status <> 'CANCELLED') THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_is_final';
    END IF;
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_managed_columns';
    END IF;
    IF NEW.status <> OLD.status AND NOT EXISTS (
           SELECT 1 FROM campaign_transition
            WHERE from_status = OLD.status AND to_status = NEW.status) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_transition';
    END IF;
    IF (NEW.budget_sar IS DISTINCT FROM OLD.budget_sar OR NEW.days IS DISTINCT FROM OLD.days)
       AND NOT (OLD.status = 'COPY_APPROVED' AND NEW.status = 'COPY_APPROVED') THEN
        RAISE EXCEPTION 'money' USING ERRCODE = 'check_violation', CONSTRAINT = 'money_only_while_approved';
    END IF;
    -- النسخة المعروضة تتغيّر والحملة مقترحةٌ فقط، وإلى أحدث نسخة (نسخةٌ
    -- جديدة) أو إلى النسخة التي بُنيت عليها الحالية (استعادة) — لا غير.
    IF NEW.current_version_id IS DISTINCT FROM OLD.current_version_id THEN
        IF NEW.status <> 'COPY_PROPOSED' OR OLD.status NOT IN ('DRAFT','COPY_PROPOSED') THEN
            RAISE EXCEPTION 'copy' USING ERRCODE = 'check_violation', CONSTRAINT = 'approved_copy_is_fixed';
        END IF;
        SELECT id INTO newest FROM copy_versions
         WHERE campaign_id = NEW.id ORDER BY version DESC LIMIT 1;
        SELECT based_on_version_id INTO previous FROM copy_versions WHERE id = OLD.current_version_id;
        IF NEW.current_version_id IS DISTINCT FROM newest
           AND (previous IS NULL OR NEW.current_version_id IS DISTINCT FROM previous) THEN
            RAISE EXCEPTION 'target' USING ERRCODE = 'check_violation', CONSTRAINT = 'current_version_target';
        END IF;
    END IF;
    -- أعمدةٌ يكتبها المحفّز وحده: العميل لا يختار ما يُعتمد ولا متى.
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at  := now();
    NEW.approved_version_id := CASE
        WHEN NEW.status = 'COPY_APPROVED' AND OLD.status = 'COPY_PROPOSED' THEN NEW.current_version_id
        WHEN NEW.status IN ('COPY_APPROVED','READY','CANCELLED')          THEN OLD.approved_version_id
        ELSE NULL END;
    NEW.approved_at := CASE
        WHEN NEW.status = 'COPY_APPROVED' AND OLD.status = 'COPY_PROPOSED' THEN now()
        WHEN NEW.status IN ('COPY_APPROVED','READY','CANCELLED')          THEN OLD.approved_at
        ELSE NULL END;
    NEW.ready_at := CASE
        WHEN NEW.status = 'READY' AND OLD.status <> 'READY' THEN now()
        ELSE OLD.ready_at END;
    NEW.cancelled_at := CASE WHEN NEW.status = 'CANCELLED' THEN now() ELSE NULL END;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_campaign_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_campaign_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.current_version_id IS NOT NULL
       OR NEW.approved_version_id IS NOT NULL OR NEW.budget_sar IS NOT NULL OR NEW.days IS NOT NULL
       OR NEW.approved_at IS NOT NULL OR NEW.ready_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_starts_as_draft';
    END IF;
    -- FOR SHARE يقف أمام تغيير المهنة (admin set-profession يقفل الصفّ للتعديل):
    -- إمّا تنتظره الحملة فتُرفض بالمهنة الجديدة، وإمّا ينتظرها فيلغيها.
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    -- قفلٌ على المستخدم يمنع حملتين متزامنتين من تجاوز السقف معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.user_id::text, 0));
    IF (SELECT count(*) FROM campaigns
         WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'open_campaign_cap';
    END IF;
    IF ew_new_open_account(NEW.user_id)
       AND (SELECT count(*) FROM campaigns
             WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 3 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'new_account_campaign_cap';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_campaign_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_current_user() RETURNS uuid
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT nullif(current_setting('eyework.user_id', true), '')::uuid
$$;
ALTER FUNCTION public.ew_current_user() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_delete_me() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    DELETE FROM users WHERE id = uid AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
END
$$;
ALTER FUNCTION public.ew_delete_me() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_finish_generation(p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    IF (p_outcome = 'OK') <> EXISTS (SELECT 1 FROM copy_versions WHERE attempt_id = p_attempt) THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'outcome_matches_version';
    END IF;
    UPDATE generation_attempts
       SET finished_at = now(), outcome = p_outcome,
           input_tokens = p_input_tokens, output_tokens = p_output_tokens
     WHERE id = p_attempt AND user_id = uid AND finished_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'attempt' USING ERRCODE = 'no_data_found';
    END IF;
END
$$;
ALTER FUNCTION public.ew_finish_generation(p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_forbid_update() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    RAISE EXCEPTION 'append-only: %', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
END
$$;
ALTER FUNCTION public.ew_forbid_update() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_image_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    current_status text;
BEGIN
    -- القفل أولاً: بدءُ توليدٍ يحجز صفّ الحملة نفسه، فينتظر أحدهما الآخر ولا
    -- تُستبدل الصورة بين قراءة النموذج لها وكتابة نصّه.
    SELECT status INTO current_status FROM campaigns WHERE id = NEW.campaign_id FOR UPDATE;
    IF current_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'image_only_in_draft';
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.campaign_id <> OLD.campaign_id OR NEW.user_id <> OLD.user_id) THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'image_only_in_draft';
    END IF;
    -- لا تتغيّر الصورة تحت نصٍّ يُكتب عنها الآن.
    IF EXISTS (SELECT 1 FROM generation_attempts
                WHERE campaign_id = NEW.campaign_id AND finished_at IS NULL
                  AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'locked' USING ERRCODE = 'check_violation', CONSTRAINT = 'image_locked_during_generation';
    END IF;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_image_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_image_touch() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_image_touch() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_is_billable(o text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT o IS NULL OR o NOT IN ('UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE', 'UPSTREAM_ERROR')
$$;
ALTER FUNCTION public.ew_is_billable(o text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_jpeg_has_no_metadata(b bytea) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT bool_and(position(set_byte('\xff00'::bytea, 1, m) IN b) = 0)
      FROM unnest(ARRAY[225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 254]) AS m
$$;
ALTER FUNCTION public.ew_jpeg_has_no_metadata(b bytea) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_add_version(p_article uuid, p_expected_row_version integer, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text) RETURNS smallint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
    v   smallint;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF (SELECT count(*) FROM kb_versions WHERE user_id = uid AND created_at > now() - interval '24 hours') >= 100 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_daily_version_cap';
    END IF;
    INSERT INTO kb_versions (article_id, user_id, title, issue, environment, resolution, cause, origin)
    VALUES (p_article, uid, p_title, p_issue, p_environment, p_resolution, p_cause, 'EMPLOYEE')
    RETURNING version INTO v;
    UPDATE kb_articles SET updated_at = now() WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article, 'ARTICLE_VERSION_ADDED', NULL, NULL, NULL, NULL, NULL);
    RETURN v;
END
$$;
ALTER FUNCTION public.ew_kb_add_version(p_article uuid, p_expected_row_version integer, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_article_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    n integer;
BEGIN
    PERFORM 1 FROM users WHERE id = NEW.user_id AND is_active AND profession = 'SUPPORT' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    IF NEW.state NOT IN ('PROPOSED', 'DRAFT') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_starts_unpublished';
    END IF;
    INSERT INTO support_settings (user_id) VALUES (NEW.user_id) ON CONFLICT (user_id) DO NOTHING;
    SELECT next_article_number INTO n FROM support_settings WHERE user_id = NEW.user_id FOR UPDATE;
    IF (SELECT count(*) FROM kb_articles WHERE user_id = NEW.user_id AND state <> 'DISCARDED') >= 300 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_cap';
    END IF;
    UPDATE support_settings SET next_article_number = n + 1, updated_at = now() WHERE user_id = NEW.user_id;
    NEW.number := n;
    NEW.published_version := NULL;
    NEW.latest_version := 0;
    NEW.needs_review := false;
    NEW.needs_review_reason := NULL;
    NEW.reuse_count := 0;
    NEW.row_version := 1;
    NEW.created_at := now();
    NEW.updated_at := now();
    NEW.published_at := NULL;
    NEW.archived_at := NULL;
    NEW.discarded_at := NULL;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_kb_article_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_article_update_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.number <> OLD.number
       OR NEW.created_at <> OLD.created_at OR NEW.row_version <> OLD.row_version
       OR NEW.client_token IS DISTINCT FROM OLD.client_token
       OR (NEW.source_ticket_id IS DISTINCT FROM OLD.source_ticket_id AND NEW.source_ticket_id IS NOT NULL)
       OR NEW.latest_version < OLD.latest_version OR NEW.reuse_count < OLD.reuse_count THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_managed_columns';
    END IF;
    IF OLD.state = 'DISCARDED' AND (NEW.state <> 'DISCARDED' OR NEW.latest_version <> OLD.latest_version) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    IF NEW.state <> OLD.state AND NOT (
           (OLD.state = 'PROPOSED' AND NEW.state IN ('DRAFT', 'PUBLISHED', 'DISCARDED'))
        OR (OLD.state = 'DRAFT' AND NEW.state IN ('PUBLISHED', 'DISCARDED'))
        OR (OLD.state = 'PUBLISHED' AND NEW.state = 'ARCHIVED')
        OR (OLD.state = 'ARCHIVED' AND NEW.state = 'PUBLISHED')) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    IF NEW.published_version IS DISTINCT FROM OLD.published_version AND NEW.published_version IS NOT NULL
       AND NEW.published_version <> NEW.latest_version THEN
        RAISE EXCEPTION 'version' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_publish_latest_only';
    END IF;
    NEW.published_at := CASE
        WHEN NEW.state = 'PUBLISHED' AND NEW.published_version IS DISTINCT FROM OLD.published_version THEN now()
        WHEN NEW.state IN ('PUBLISHED', 'ARCHIVED') THEN OLD.published_at
        ELSE NULL END;
    NEW.archived_at := CASE WHEN NEW.state = 'ARCHIVED' THEN coalesce(OLD.archived_at, now()) ELSE NULL END;
    NEW.discarded_at := CASE WHEN NEW.state = 'DISCARDED' THEN coalesce(OLD.discarded_at, now()) ELSE NULL END;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_kb_article_update_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_begin_proposal(p_ticket uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(true);
    call uuid;
BEGIN
    PERFORM 1 FROM support_tickets WHERE id = p_ticket AND user_id = uid AND texts_purged_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket' USING ERRCODE = 'no_data_found';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM support_messages WHERE ticket_id = p_ticket AND author = 'AGENT')
       AND NOT EXISTS (SELECT 1 FROM support_drafts WHERE ticket_id = p_ticket AND reject_reason = 'NOT_IN_KB') THEN
        RAISE EXCEPTION 'source' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_proposal_needs_source';
    END IF;
    IF (SELECT count(*) FROM support_ai_calls WHERE ticket_id = p_ticket AND kind = 'ARTICLE_PROPOSAL') >= 2 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_ticket_proposal_cap';
    END IF;
    call := ew_support_ai_open(uid, 'ARTICLE_PROPOSAL', p_ticket, NULL, NULL, NULL, NULL);
    RETURN call;
END
$$;
ALTER FUNCTION public.ew_kb_begin_proposal(p_ticket uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_begin_review(p_article uuid, p_version smallint) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(true);
    a    kb_articles%ROWTYPE;
    call uuid;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.latest_version <> p_version OR a.state IN ('ARCHIVED', 'DISCARDED')
       OR a.published_version IS NOT DISTINCT FROM p_version THEN
        RAISE EXCEPTION 'review' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_review_not_pending';
    END IF;
    IF EXISTS (SELECT 1 FROM support_ai_calls
                WHERE kind = 'ARTICLE_REVIEW' AND article_id = p_article AND article_version = p_version
                  AND (outcome = 'OK' OR (finished_at IS NULL AND started_at > now() - interval '5 minutes'))) THEN
        RAISE EXCEPTION 'review' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_review_not_pending';
    END IF;
    call := ew_support_ai_open(uid, 'ARTICLE_REVIEW', NULL, NULL, p_article, p_version, NULL);
    RETURN call;
END
$$;
ALTER FUNCTION public.ew_kb_begin_review(p_article uuid, p_version smallint) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_create(p_client_token uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_source_ticket uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    aid uuid;
BEGIN
    SELECT id INTO aid FROM kb_articles WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN aid;
    END IF;
    INSERT INTO kb_articles (user_id, state, client_token, source_ticket_id)
    VALUES (uid, 'DRAFT', p_client_token, p_source_ticket)
    RETURNING id INTO aid;
    INSERT INTO kb_versions (article_id, user_id, title, issue, environment, resolution, cause, origin)
    VALUES (aid, uid, p_title, p_issue, p_environment, p_resolution, p_cause, 'EMPLOYEE');
    PERFORM ew_support_log(uid, p_source_ticket, aid, 'ARTICLE_CREATED', NULL, NULL, NULL, NULL, NULL);
    RETURN aid;
END
$$;
ALTER FUNCTION public.ew_kb_create(p_client_token uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_source_ticket uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_mark_review(p_article uuid, p_expected_row_version integer, p_needs boolean) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    UPDATE kb_articles
       SET needs_review = p_needs, needs_review_reason = CASE WHEN p_needs THEN 'EMPLOYEE' END
     WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article,
                           CASE WHEN p_needs THEN 'ARTICLE_MARKED_REVIEW' ELSE 'ARTICLE_REVIEW_CLEARED' END,
                           NULL, NULL, NULL, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_kb_mark_review(p_article uuid, p_expected_row_version integer, p_needs boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_norm(t text) RETURNS text
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT btrim(regexp_replace(
               regexp_replace(lower(normalize(t, NFKC)), '[ً-ٰٟـ]', '', 'g'),
               '[[:space:]]+', ' ', 'g'))
$$;
ALTER FUNCTION public.ew_kb_norm(t text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_publish(p_article uuid, p_expected_row_version integer, p_version smallint) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version OR a.latest_version <> p_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF EXISTS (SELECT 1 FROM support_flags
                WHERE article_id = p_article AND article_version = p_version AND state = 'OPEN') THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flags_open';
    END IF;
    IF EXISTS (SELECT 1 FROM support_ai_calls
                WHERE kind = 'ARTICLE_REVIEW' AND article_id = p_article AND article_version = p_version
                  AND finished_at IS NULL AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'review' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_review_waiting';
    END IF;
    UPDATE kb_articles
       SET state = 'PUBLISHED', published_version = p_version, needs_review = false, needs_review_reason = NULL
     WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article, 'ARTICLE_PUBLISHED', 'V' || p_version, NULL, NULL, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_kb_publish(p_article uuid, p_expected_row_version integer, p_version smallint) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_record_proposal(p_call uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    c   support_ai_calls%ROWTYPE;
    aid uuid;
BEGIN
    SELECT * INTO c FROM support_ai_calls WHERE id = p_call AND user_id = uid;
    IF NOT FOUND OR c.kind <> 'ARTICLE_PROPOSAL' THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_call_not_open';
    END IF;
    INSERT INTO kb_articles (user_id, state, source_ticket_id) VALUES (uid, 'PROPOSED', c.ticket_id)
    RETURNING id INTO aid;
    INSERT INTO kb_versions (article_id, user_id, title, issue, environment, resolution, cause, origin, call_id)
    VALUES (aid, uid, p_title, p_issue, p_environment, p_resolution, p_cause, 'AI', p_call);
    PERFORM ew_support_ai_settle(uid, p_call, 'ARTICLE_PROPOSAL', 'OK', p_input, p_output, p_model,
                                 p_prompt_version, p_request_id, true);
    PERFORM ew_support_log(uid, c.ticket_id, aid, 'ARTICLE_PROPOSED', NULL, NULL, NULL, NULL, 'ASSISTANT');
    RETURN aid;
END
$$;
ALTER FUNCTION public.ew_kb_record_proposal(p_call uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    c    support_ai_calls%ROWTYPE;
    f    jsonb;
    flag uuid;
BEGIN
    c := ew_support_ai_settle(uid, p_call, 'ARTICLE_REVIEW', 'OK', p_input, p_output, p_model, p_prompt_version,
                              p_request_id, true);
    IF jsonb_typeof(p_flags) <> 'array' OR jsonb_array_length(p_flags) > 4 THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
    END IF;
    FOR f IN SELECT value FROM jsonb_array_elements(p_flags) LOOP
        IF f ->> 'code' NOT IN ('CONTRADICTS_ARTICLE', 'PERSONAL_DATA', 'UNSAFE_INSTRUCTION', 'UNCLEAR_STEPS') THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
        END IF;
        INSERT INTO support_flags (user_id, article_id, article_version, source, code, evidence, related_article_id,
                                   call_id)
        VALUES (uid, c.article_id, c.article_version, 'AI', f ->> 'code', f ->> 'evidence',
                (f ->> 'related_article_id')::uuid, p_call)
        RETURNING id INTO flag;
        PERFORM ew_support_log(uid, NULL, c.article_id, 'FLAG_RAISED', f ->> 'code', NULL, NULL, flag, 'ASSISTANT');
    END LOOP;
END
$$;
ALTER FUNCTION public.ew_kb_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_search(p_query text, p_limit integer) RETURNS TABLE(article_id uuid, number integer, version smallint, title text, issue text, environment text, resolution text, cause text, rank real)
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_current_user();
    q   tsquery;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND is_active AND profession = 'SUPPORT') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    IF p_query IS NULL OR char_length(p_query) NOT BETWEEN 2 AND 200 OR p_limit NOT BETWEEN 1 AND 10 THEN
        RAISE EXCEPTION 'query' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_search_query';
    END IF;
    SELECT to_tsquery('simple', string_agg(quote_literal(lexeme), ' | '))
      INTO q FROM unnest(tsvector_to_array(to_tsvector('arabic'::regconfig, p_query))) AS lexeme;
    IF q IS NULL THEN
        RETURN;
    END IF;
    RETURN QUERY
    SELECT a.id, a.number, v.version, v.title, v.issue, v.environment, v.resolution, v.cause,
           ts_rank_cd(v.search, q) AS r
      FROM kb_articles a JOIN kb_versions v ON v.article_id = a.id AND v.version = a.published_version
     WHERE a.user_id = uid AND a.state = 'PUBLISHED' AND v.search @@ q
     ORDER BY r DESC, a.reuse_count DESC, a.number
     LIMIT p_limit;
END
$$;
ALTER FUNCTION public.ew_kb_search(p_query text, p_limit integer) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_set_state(p_article uuid, p_expected_row_version integer, p_state text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF p_state NOT IN ('ARCHIVED', 'DISCARDED') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    UPDATE kb_articles
       SET state = p_state, published_version = NULL, needs_review = false, needs_review_reason = NULL
     WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article,
                           CASE p_state WHEN 'ARCHIVED' THEN 'ARTICLE_ARCHIVED' ELSE 'ARTICLE_DISCARDED' END,
                           NULL, NULL, NULL, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_kb_set_state(p_article uuid, p_expected_row_version integer, p_state text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_version_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    a kb_articles%ROWTYPE;
    c support_ai_calls%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = NEW.article_id AND user_id = NEW.user_id FOR UPDATE;
    IF NOT FOUND OR a.state = 'DISCARDED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    IF NEW.origin = 'AI' THEN
        SELECT * INTO c FROM support_ai_calls WHERE id = NEW.call_id;
        IF NOT FOUND OR c.kind <> 'ARTICLE_PROPOSAL' OR c.user_id <> NEW.user_id OR c.finished_at IS NOT NULL
           OR c.started_at <= now() - interval '5 minutes' OR a.latest_version <> 0 THEN
            RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_ai_version_needs_open_call';
        END IF;
    ELSIF NEW.call_id IS NOT NULL THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_ai_version_needs_open_call';
    END IF;
    NEW.version := a.latest_version + 1;
    NEW.created_at := now();
    UPDATE kb_articles
       SET latest_version = NEW.version,
           state = CASE WHEN a.state = 'PROPOSED' AND NEW.origin = 'EMPLOYEE' THEN 'DRAFT' ELSE a.state END
     WHERE id = NEW.article_id;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_kb_version_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_kb_version_update_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF NOT (OLD.call_id IS NOT NULL AND NEW.call_id IS NULL
            AND (NEW.article_id, NEW.version, NEW.user_id, NEW.title, NEW.issue, NEW.environment, NEW.resolution,
                 NEW.cause, NEW.origin, NEW.created_at)
                IS NOT DISTINCT FROM
                (OLD.article_id, OLD.version, OLD.user_id, OLD.title, OLD.issue, OLD.environment, OLD.resolution,
                 OLD.cause, OLD.origin, OLD.created_at)) THEN
        RAISE EXCEPTION 'append-only: %', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_kb_version_update_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_login_lookup(p_login bytea) RETURNS TABLE(user_id uuid, password_hash text)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT id, password_hash FROM users
     WHERE login_hmac = p_login AND is_active AND activated_at IS NOT NULL
$$;
ALTER FUNCTION public.ew_login_lookup(p_login bytea) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_my_display_name() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT display_name FROM users WHERE id = ew_current_user() AND is_active
$$;
ALTER FUNCTION public.ew_my_display_name() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_my_generation_limit() RETURNS integer
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT CASE WHEN ew_new_open_account(id) THEN 10 ELSE 40 END
      FROM users WHERE id = ew_current_user() AND is_active
$$;
ALTER FUNCTION public.ew_my_generation_limit() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_my_passkeys() RETURNS TABLE(credential_id bytea, transports text[])
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT p.credential_id, p.transports FROM passkeys p
     WHERE p.user_id = ew_current_user()
     ORDER BY p.created_at, p.id
$$;
ALTER FUNCTION public.ew_my_passkeys() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_my_profession() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT profession FROM users WHERE id = ew_current_user() AND is_active
$$;
ALTER FUNCTION public.ew_my_profession() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_my_terms_version() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT terms_version FROM users WHERE id = ew_current_user() AND is_active
$$;
ALTER FUNCTION public.ew_my_terms_version() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_my_ui_size() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT ui_size FROM users WHERE id = ew_current_user() AND is_active
$$;
ALTER FUNCTION public.ew_my_ui_size() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_new_open_account(p_user uuid) RETURNS boolean
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT coalesce((SELECT open_registered AND created_at > now() - interval '7 days'
                       FROM users WHERE id = p_user), false)
$$;
ALTER FUNCTION public.ew_new_open_account(p_user uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_open_registration_blocker() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT ew_registration_blocker('OPEN')
$$;
ALTER FUNCTION public.ew_open_registration_blocker() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_open_session(p_user uuid, p_token bytea) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user AND is_active AND activated_at IS NOT NULL) THEN
        RAISE EXCEPTION 'session' USING ERRCODE = 'check_violation', CONSTRAINT = 'session_needs_active_user';
    END IF;
    INSERT INTO sessions (user_id, token_hash, expires_at)
    VALUES (p_user, p_token, now() + interval '30 days');
END
$$;
ALTER FUNCTION public.ew_open_session(p_user uuid, p_token bytea) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint, p_transports text[]) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_current_user();
    added uuid;
BEGIN
    -- قفلٌ على صفّ الحساب: إضافتان متزامنتان لا تتجاوزان السقف معاً.
    PERFORM 1 FROM users WHERE id = uid AND is_active AND activated_at IS NOT NULL FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (SELECT count(*) FROM passkeys WHERE user_id = uid) >= 10 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'passkey_cap';
    END IF;
    INSERT INTO passkeys (user_id, credential_id, public_key, sign_count, transports)
    VALUES (uid, p_credential, p_public_key, p_sign_count, p_transports)
    ON CONFLICT (credential_id) DO NOTHING
    RETURNING id INTO added;
    RETURN added IS NOT NULL;
END
$$;
ALTER FUNCTION public.ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint, p_transports text[]) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_passkey_challenge(p_challenge bytea, p_purpose text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid;
BEGIN
    IF p_purpose = 'ADD' THEN
        uid := ew_current_user();
        PERFORM 1 FROM users WHERE id = uid AND is_active AND activated_at IS NOT NULL;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF (SELECT count(*) FROM passkeys WHERE user_id = uid) >= 10 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'passkey_cap';
        END IF;
    END IF;
    INSERT INTO passkey_challenges (challenge_hash, purpose, user_id, expires_at)
    VALUES (p_challenge, p_purpose, uid, now() + interval '5 minutes');
END
$$;
ALTER FUNCTION public.ew_passkey_challenge(p_challenge bytea, p_purpose text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_passkey_lookup(p_credential bytea) RETURNS TABLE(user_id uuid, public_key bytea, sign_count bigint)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT p.user_id, p.public_key, p.sign_count
      FROM passkeys p JOIN users u ON u.id = p.user_id
     WHERE p.credential_id = p_credential AND u.is_active AND u.activated_at IS NOT NULL
$$;
ALTER FUNCTION public.ew_passkey_lookup(p_credential bytea) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_passkey_signed_in(p_credential bytea, p_sign_count bigint) RETURNS uuid
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    UPDATE passkeys p SET sign_count = p_sign_count, last_used_at = now()
      FROM users u
     WHERE p.credential_id = p_credential AND u.id = p.user_id
       AND u.is_active AND u.activated_at IS NOT NULL
       AND (p_sign_count > p.sign_count OR (p_sign_count = 0 AND p.sign_count = 0))
    RETURNING p.user_id
$$;
ALTER FUNCTION public.ew_passkey_signed_in(p_credential bytea, p_sign_count bigint) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_passkey_take_challenge(p_challenge bytea, p_purpose text) RETURNS boolean
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    WITH taken AS (
        UPDATE passkey_challenges SET used_at = now()
         WHERE challenge_hash = p_challenge AND purpose = p_purpose
           AND used_at IS NULL AND expires_at > now()
           AND user_id IS NOT DISTINCT FROM (CASE WHEN p_purpose = 'ADD' THEN ew_current_user() END)
        RETURNING 1
    )
    SELECT EXISTS (SELECT 1 FROM taken)
$$;
ALTER FUNCTION public.ew_passkey_take_challenge(p_challenge bytea, p_purpose text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_purge_image_on_cancel() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    DELETE FROM campaign_images WHERE campaign_id = NEW.id;
    RETURN NULL;
END
$$;
ALTER FUNCTION public.ew_purge_image_on_cancel() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) RETURNS TABLE(new_user uuid, outcome text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid     uuid;
    code    signup_codes%ROWTYPE;
    blocker text;
BEGIN
    SELECT * INTO code FROM signup_codes WHERE code_hash = p_code FOR UPDATE;
    IF NOT FOUND OR code.used_at IS NOT NULL OR code.expires_at <= now() OR code.taken_count >= 3 THEN
        RETURN QUERY SELECT NULL::uuid, 'CODE'::text;
        RETURN;
    END IF;
    IF p_name IS NULL THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_name';
    END IF;
    IF p_birth IS NULL OR p_birth > ew_riyadh_today() THEN
        RAISE EXCEPTION 'birth' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_birth_date';
    END IF;
    IF p_terms_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    IF p_size IS NULL THEN
        RAISE EXCEPTION 'size' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_ui_size';
    END IF;
    -- قفلٌ واحد للطريقين: تسجيلان متزامنان لا يريان العدّ نفسه فيمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('CODE');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       ui_size, self_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession,
            p_size, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        UPDATE signup_codes SET taken_count = taken_count + 1 WHERE code_hash = p_code;
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    UPDATE signup_codes SET used_at = now(), user_id = uid WHERE code_hash = p_code;
    INSERT INTO registration_ledger (via, outcome) VALUES ('CODE', 'OK');
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;
ALTER FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_register_open(p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) RETURNS TABLE(new_user uuid, outcome text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid     uuid;
    blocker text;
BEGIN
    IF p_name IS NULL THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_name';
    END IF;
    IF p_birth IS NULL OR p_birth > ew_riyadh_today() THEN
        RAISE EXCEPTION 'birth' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_birth_date';
    END IF;
    IF p_terms_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    IF p_size IS NULL THEN
        RAISE EXCEPTION 'size' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_ui_size';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('OPEN');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       ui_size, self_registered, open_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession,
            p_size, true, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'TAKEN');
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'OK');
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;
ALTER FUNCTION public.ew_register_open(p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_registration_blocker(p_via text) RETURNS text
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT CASE
        WHEN count(*) FILTER (WHERE outcome = 'OK') >= 200 THEN 'registration_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE via = 'OPEN' AND outcome = 'OK') >= 150
            THEN 'registration_open_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE via = 'OPEN' AND outcome = 'TAKEN') >= 60
            THEN 'registration_open_paused'
    END
      FROM registration_ledger
     WHERE occurred_at > now() - interval '24 hours'
$$;
ALTER FUNCTION public.ew_registration_blocker(p_via text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_resolve_session(p_token bytea) RETURNS uuid
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT s.user_id FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.token_hash = p_token AND s.revoked_at IS NULL AND s.expires_at > now()
       AND u.is_active
$$;
ALTER FUNCTION public.ew_resolve_session(p_token bytea) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_revoke_session(p_token bytea) RETURNS void
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    UPDATE sessions SET revoked_at = now() WHERE token_hash = p_token AND revoked_at IS NULL
$$;
ALTER FUNCTION public.ew_revoke_session(p_token bytea) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_riyadh_today() RETURNS date
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT (now() AT TIME ZONE 'Asia/Riyadh')::date
$$;
ALTER FUNCTION public.ew_riyadh_today() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_set_my_ui_size(p_size text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF p_size IS NULL THEN
        RAISE EXCEPTION 'size' USING ERRCODE = 'check_violation', CONSTRAINT = 'ui_size_known';
    END IF;
    UPDATE users SET ui_size = p_size WHERE id = ew_current_user() AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
END
$$;
ALTER FUNCTION public.ew_set_my_ui_size(p_size text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_signup_code_usable(p_code bytea) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT EXISTS (SELECT 1 FROM signup_codes
                    WHERE code_hash = p_code AND used_at IS NULL AND expires_at > now() AND taken_count < 3)
$$;
ALTER FUNCTION public.ew_signup_code_usable(p_code bytea) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_accept_notice(p_version text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
BEGIN
    UPDATE support_settings
       SET notice_version = p_version, notice_accepted_at = now(), updated_at = now()
     WHERE user_id = uid AND notice_version IS DISTINCT FROM p_version;
END
$$;
ALTER FUNCTION public.ew_support_accept_notice(p_version text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ack_flag(p_flag uuid, p_action text, p_reason text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    f   support_flags%ROWTYPE;
BEGIN
    SELECT * INTO f FROM support_flags WHERE id = p_flag AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'no_data_found';
    END IF;
    IF f.state <> 'OPEN' OR p_action NOT IN ('HEEDED', 'DISMISSED')
       OR (p_action = 'DISMISSED') <> (p_reason IS NOT NULL) THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_immutable';
    END IF;
    UPDATE support_flags SET state = p_action, dismiss_reason = p_reason WHERE id = p_flag;
    PERFORM ew_support_log(uid, f.ticket_id, f.article_id,
                           CASE p_action WHEN 'HEEDED' THEN 'FLAG_HEEDED' ELSE 'FLAG_DISMISSED' END,
                           coalesce(p_reason, f.code), NULL, f.reply_id, p_flag, NULL);
END
$$;
ALTER FUNCTION public.ew_support_ack_flag(p_flag uuid, p_action text, p_reason text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_add_message(p_ticket uuid, p_expected_row_version integer, p_author text, p_body text, p_masked smallint, p_client_token uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
    mid uuid;
BEGIN
    SELECT id INTO mid FROM support_messages WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN mid;
    END IF;
    IF p_author NOT IN ('CUSTOMER', 'NOTE') THEN
        RAISE EXCEPTION 'author' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_message_author';
    END IF;
    PERFORM ew_support_require_notice(uid);
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    INSERT INTO support_messages (ticket_id, user_id, author, body, masked_count, client_token)
    VALUES (p_ticket, uid, p_author, p_body, p_masked, p_client_token)
    RETURNING id INTO mid;
    IF p_author = 'CUSTOMER' THEN
        UPDATE support_tickets
           SET status = CASE WHEN t.status IN ('PENDING', 'RESOLVED') THEN 'OPEN' ELSE t.status END
         WHERE id = p_ticket;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'CUSTOMER_MESSAGE_ADDED', NULL, NULL, NULL, NULL, NULL);
    ELSE
        UPDATE support_tickets SET status = t.status WHERE id = p_ticket;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'NOTE_ADDED', NULL, NULL, NULL, NULL, NULL);
    END IF;
    RETURN mid;
END
$$;
ALTER FUNCTION public.ew_support_add_message(p_ticket uuid, p_expected_row_version integer, p_author text, p_body text, p_masked smallint, p_client_token uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ai_open(p_uid uuid, p_kind text, p_ticket uuid, p_reply uuid, p_article uuid, p_version smallint, p_message uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    lim   support_ai_limits%ROWTYPE;
    fresh boolean;
    call  uuid;
BEGIN
    PERFORM ew_support_require_notice(p_uid);
    SELECT * INTO lim FROM support_ai_limits WHERE kind = p_kind;
    IF EXISTS (SELECT 1 FROM support_ai_calls
                WHERE user_id = p_uid AND finished_at IS NULL AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_in_progress';
    END IF;
    IF (SELECT count(*) FROM support_ai_calls
         WHERE user_id = p_uid AND kind = p_kind AND started_at > now() - interval '10 minutes') >= lim.per_user_10min THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_rate';
    END IF;
    fresh := ew_new_open_account(p_uid);
    IF (SELECT count(*) FROM support_ai_calls
         WHERE user_id = p_uid AND kind = p_kind AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours')
       >= (CASE WHEN fresh THEN lim.per_new_user_day ELSE lim.per_user_day END) THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation',
            CONSTRAINT = CASE WHEN fresh THEN 'support_ai_new_account_daily_cap' ELSE 'support_ai_daily_cap' END;
    END IF;
    -- القفل العام نفسه الذي يأخذه ew_begin_generation: السقف واحدٌ للأدوات كلها.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM support_ai_calls
         WHERE kind = p_kind AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= lim.app_day THEN
        RAISE EXCEPTION 'app' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_app_cap';
    END IF;
    IF ew_ai_spend(false) >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF fresh AND ew_ai_spend(true) >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    INSERT INTO support_ai_calls (user_id, kind, ticket_id, reply_id, article_id, article_version,
                                  based_on_message_id, new_account)
    VALUES (p_uid, p_kind, p_ticket, p_reply, p_article, p_version, p_message, fresh)
    RETURNING id INTO call;
    RETURN call;
END
$$;
ALTER FUNCTION public.ew_support_ai_open(p_uid uuid, p_kind text, p_ticket uuid, p_reply uuid, p_article uuid, p_version smallint, p_message uuid) OWNER TO eyework_owner;
SET default_tablespace = '';
SET default_table_access_method = heap;
CREATE TABLE public.support_ai_calls (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    kind text NOT NULL,
    ticket_id uuid,
    reply_id uuid,
    article_id uuid,
    article_version smallint,
    based_on_message_id uuid,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    outcome text,
    input_tokens integer,
    output_tokens integer,
    served_model text,
    prompt_version text,
    api_request_id text,
    new_account boolean DEFAULT false NOT NULL,
    CONSTRAINT support_ai_calls_api_request_id_check CHECK (((api_request_id IS NULL) OR (char_length(api_request_id) <= 128))),
    CONSTRAINT support_ai_calls_input_tokens_check CHECK ((input_tokens >= 0)),
    CONSTRAINT support_ai_calls_output_tokens_check CHECK ((output_tokens >= 0)),
    CONSTRAINT support_ai_calls_prompt_version_check CHECK (((prompt_version IS NULL) OR (prompt_version ~ '^[a-z0-9.-]{1,32}$'::text))),
    CONSTRAINT support_ai_calls_served_model_check CHECK (((served_model IS NULL) OR (served_model ~ '^claude-[a-z0-9.-]{1,57}$'::text))),
    CONSTRAINT support_ai_finished_iff_outcome CHECK (((finished_at IS NULL) = (outcome IS NULL))),
    CONSTRAINT support_ai_outcome CHECK ((outcome = ANY (ARRAY['OK'::text, 'CANNOT_ANSWER'::text, 'NOT_SUPPORT'::text, 'REFUSED'::text, 'OUTPUT_INVALID'::text, 'DISCARDED'::text, 'UPSTREAM_BUSY'::text, 'UPSTREAM_UNREACHABLE'::text, 'UPSTREAM_TIMEOUT'::text, 'UPSTREAM_ERROR'::text]))),
    CONSTRAINT support_ai_target CHECK ((((kind = ANY (ARRAY['DRAFT'::text, 'ARTICLE_PROPOSAL'::text])) AND (reply_id IS NULL) AND (article_id IS NULL)) OR ((kind = 'REPLY_REVIEW'::text) AND (article_id IS NULL)) OR ((kind = 'ARTICLE_REVIEW'::text) AND (reply_id IS NULL) AND (ticket_id IS NULL))))
);
ALTER TABLE ONLY public.support_ai_calls FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_ai_calls OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ai_settle(p_uid uuid, p_call uuid, p_kind text, p_outcome text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text, p_needs_lease boolean) RETURNS public.support_ai_calls
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    c support_ai_calls%ROWTYPE;
BEGIN
    SELECT * INTO c FROM support_ai_calls WHERE id = p_call AND user_id = p_uid FOR UPDATE;
    IF NOT FOUND OR c.kind <> p_kind OR c.finished_at IS NOT NULL
       OR (p_needs_lease AND c.started_at <= now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_call_not_open';
    END IF;
    UPDATE support_ai_calls
       SET finished_at = now(), outcome = p_outcome, input_tokens = p_input, output_tokens = p_output,
           served_model = p_model, prompt_version = p_prompt_version, api_request_id = p_request_id
     WHERE id = p_call
    RETURNING * INTO c;
    RETURN c;
END
$$;
ALTER FUNCTION public.ew_support_ai_settle(p_uid uuid, p_call uuid, p_kind text, p_outcome text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text, p_needs_lease boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ai_tombstone() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, new_account)
        VALUES (OLD.started_at, OLD.outcome, OLD.new_account);
    END IF;
    RETURN OLD;
END
$$;
ALTER FUNCTION public.ew_support_ai_tombstone() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_begin_draft(p_ticket uuid, p_expected_row_version integer) RETURNS TABLE(call_id uuid, based_on_message_id uuid)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid    uuid := ew_support_me(true);
    t      support_tickets%ROWTYPE;
    latest uuid;
    call   uuid;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    SELECT id INTO latest FROM support_messages
     WHERE ticket_id = p_ticket AND author = 'CUSTOMER' ORDER BY created_at DESC, id DESC LIMIT 1;
    IF latest IS NULL THEN
        RAISE EXCEPTION 'message' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_needs_message';
    END IF;
    IF (SELECT count(*) FROM support_ai_calls
         WHERE ticket_id = p_ticket AND kind = 'DRAFT' AND started_at > now() - interval '24 hours') >= 8 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_draft_cap';
    END IF;
    call := ew_support_ai_open(uid, 'DRAFT', p_ticket, NULL, NULL, NULL, latest);
    PERFORM ew_support_log(uid, p_ticket, NULL, 'DRAFT_REQUESTED', NULL, NULL, NULL, NULL, NULL);
    RETURN QUERY SELECT call, latest;
END
$$;
ALTER FUNCTION public.ew_support_begin_draft(p_ticket uuid, p_expected_row_version integer) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_begin_review(p_reply uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(true);
    r    support_replies%ROWTYPE;
    t    support_tickets%ROWTYPE;
    call uuid;
BEGIN
    SELECT * INTO r FROM support_replies WHERE id = p_reply AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, r.ticket_id, NULL);
    IF r.state <> 'READY' OR r.review NOT IN ('PENDING', 'FAILED') THEN
        RAISE EXCEPTION 'review' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_review_not_pending';
    END IF;
    call := ew_support_ai_open(uid, 'REPLY_REVIEW', r.ticket_id, p_reply, NULL, NULL, NULL);
    UPDATE support_replies SET review = 'RUNNING', review_started_at = now() WHERE id = p_reply;
    RETURN call;
END
$$;
ALTER FUNCTION public.ew_support_begin_review(p_reply uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_citation_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    v support_drafts%ROWTYPE;
    a kb_articles%ROWTYPE;
    k kb_versions%ROWTYPE;
BEGIN
    SELECT * INTO v FROM support_drafts WHERE id = NEW.draft_id AND user_id = NEW.user_id;
    IF NOT FOUND OR v.created_at <> now() THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_needs_new_draft';
    END IF;
    SELECT * INTO a FROM kb_articles WHERE id = NEW.article_id AND user_id = NEW.user_id;
    IF NOT FOUND OR a.state <> 'PUBLISHED' OR a.published_version <> NEW.article_version THEN
        RAISE EXCEPTION 'kb' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_not_published';
    END IF;
    SELECT * INTO k FROM kb_versions WHERE article_id = NEW.article_id AND version = NEW.article_version;
    IF strpos(ew_kb_norm(k.title || ' ' || k.issue || ' ' || coalesce(k.environment, '') || ' '
                         || k.resolution || ' ' || coalesce(k.cause, '')),
              ew_kb_norm(NEW.quote)) = 0 THEN
        RAISE EXCEPTION 'quote' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_not_verbatim';
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_citation_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_close_due() RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    n   integer;
    m   integer;
BEGIN
    -- خارج الجلسة كي لا يُحسب الإغلاق الآلي نشاطاً للموظف ولا يُنسب إليه.
    PERFORM set_config('eyework.user_id', '', true);
    UPDATE support_tickets SET status = 'CLOSED', close_reason = 'AFTER_RESOLVED'
     WHERE user_id = uid AND status = 'RESOLVED' AND resolved_at < now() - interval '4 days';
    GET DIAGNOSTICS n = ROW_COUNT;
    UPDATE support_tickets SET status = 'CLOSED', close_reason = 'IDLE'
     WHERE user_id = uid AND status <> 'CLOSED' AND last_activity_at < now() - interval '90 days';
    GET DIAGNOSTICS m = ROW_COUNT;
    -- ردٌّ جُهّز أو نُسخ ولم يؤكَّد على تذكرةٍ أُغلقت لا يبقى حيّاً.
    UPDATE support_replies r SET state = 'WITHDRAWN', withdrawn_at = now()
      FROM support_tickets t
     WHERE t.id = r.ticket_id AND t.user_id = uid AND t.status = 'CLOSED' AND r.state IN ('READY', 'RELEASED');
    PERFORM set_config('eyework.user_id', uid::text, true);
    RETURN n + m;
END
$$;
ALTER FUNCTION public.ew_support_close_due() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_confirm_reply(p_reply uuid, p_sent boolean) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    r    support_replies%ROWTYPE;
    t    support_tickets%ROWTYPE;
    next text;
BEGIN
    SELECT * INTO r FROM support_replies WHERE id = p_reply AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, r.ticket_id, NULL);
    IF r.state NOT IN ('READY', 'RELEASED') OR (p_sent AND r.state <> 'RELEASED') THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_transition';
    END IF;
    IF NOT p_sent THEN
        UPDATE support_replies SET state = 'WITHDRAWN', withdrawn_at = now() WHERE id = p_reply;
        UPDATE support_tickets SET status = t.status WHERE id = r.ticket_id;
        PERFORM ew_support_log(uid, r.ticket_id, NULL, 'REPLY_WITHDRAWN', NULL, r.draft_id, p_reply, NULL, NULL);
        RETURN;
    END IF;
    UPDATE support_replies SET state = 'SENT', sent_at = now() WHERE id = p_reply;
    INSERT INTO support_messages (ticket_id, user_id, author, body, reply_id)
    VALUES (r.ticket_id, uid, 'AGENT', r.body, p_reply);
    next := CASE
        WHEN r.kind = 'ANSWER' THEN 'RESOLVED'
        WHEN t.status = 'ESCALATED' THEN 'ESCALATED'
        WHEN r.kind = 'ASK_INFO' THEN 'PENDING'
        ELSE 'OPEN' END;
    UPDATE support_tickets
       SET status = next,
           resolution = CASE WHEN next = 'RESOLVED' THEN coalesce(t.resolution, 'REPLIED') ELSE NULL END,
           first_replied_at = coalesce(t.first_replied_at, now())
     WHERE id = r.ticket_id;
    UPDATE kb_articles a SET reuse_count = a.reuse_count + 1
      FROM (SELECT DISTINCT article_id FROM support_draft_citations WHERE draft_id = r.draft_id) c
     WHERE a.id = c.article_id AND a.user_id = uid;
    PERFORM ew_support_log(uid, r.ticket_id, NULL, 'REPLY_SENT', r.kind, r.draft_id, p_reply, NULL, NULL);
    IF next = 'RESOLVED' AND t.status <> 'RESOLVED' THEN
        PERFORM ew_support_log(uid, r.ticket_id, NULL, 'RESOLVED', 'REPLIED', NULL, p_reply, NULL, NULL);
    END IF;
END
$$;
ALTER FUNCTION public.ew_support_confirm_reply(p_reply uuid, p_sent boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_contact_free(t text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT t !~ '[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+'
       AND t !~ '([0-9٠-٩۰-۹][ -]?){8}[0-9٠-٩۰-۹]'
$$;
ALTER FUNCTION public.ew_support_contact_free(t text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_create_ticket(p_client_token uuid, p_channel text, p_priority text, p_category text, p_customer_label text, p_subject text, p_body text, p_masked smallint) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    tid uuid;
BEGIN
    SELECT id INTO tid FROM support_tickets WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN tid;
    END IF;
    PERFORM ew_support_require_notice(uid);
    INSERT INTO support_tickets (user_id, client_token, channel, priority, category, customer_label, subject)
    VALUES (uid, p_client_token, p_channel, coalesce(p_priority, 'NORMAL'), p_category, p_customer_label, p_subject)
    RETURNING id INTO tid;
    INSERT INTO support_messages (ticket_id, user_id, author, body, masked_count, client_token)
    VALUES (tid, uid, 'CUSTOMER', p_body, p_masked, p_client_token);
    PERFORM ew_support_log(uid, tid, NULL, 'TICKET_CREATED', p_channel, NULL, NULL, NULL, NULL);
    RETURN tid;
END
$$;
ALTER FUNCTION public.ew_support_create_ticket(p_client_token uuid, p_channel text, p_priority text, p_category text, p_customer_label text, p_subject text, p_body text, p_masked smallint) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_draft_grounded() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF NEW.reply_kind = 'ANSWER'
       AND EXISTS (SELECT 1 FROM support_drafts WHERE id = NEW.id)
       AND NOT EXISTS (SELECT 1 FROM support_draft_citations WHERE draft_id = NEW.id) THEN
        RAISE EXCEPTION 'grounded' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_answer_needs_citation';
    END IF;
    RETURN NULL;
END
$$;
ALTER FUNCTION public.ew_support_draft_grounded() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_draft_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    c      support_ai_calls%ROWTYPE;
    latest uuid;
BEGIN
    SELECT * INTO c FROM support_ai_calls WHERE id = NEW.call_id FOR UPDATE;
    IF NOT FOUND OR c.kind <> 'DRAFT' OR c.finished_at IS NOT NULL OR c.user_id <> NEW.user_id
       OR c.ticket_id IS DISTINCT FROM NEW.ticket_id OR c.started_at <= now() - interval '5 minutes'
       OR c.based_on_message_id IS DISTINCT FROM NEW.based_on_message_id THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_needs_open_call';
    END IF;
    SELECT id INTO latest FROM support_messages
     WHERE ticket_id = NEW.ticket_id AND author = 'CUSTOMER' ORDER BY created_at DESC, id DESC LIMIT 1;
    IF latest IS DISTINCT FROM NEW.based_on_message_id THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_stale';
    END IF;
    NEW.seq := (SELECT coalesce(max(seq), 0) + 1 FROM support_drafts WHERE ticket_id = NEW.ticket_id);
    NEW.suggested_priority := ew_support_priority_for(NEW.impact, NEW.urgency, NEW.security_concern);
    NEW.rejected_at := NULL;
    NEW.reject_reason := NULL;
    NEW.reject_note := NULL;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_draft_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_draft_update_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF OLD.rejected_at IS NOT NULL OR NEW.rejected_at IS NULL
       OR (NEW.id, NEW.ticket_id, NEW.user_id, NEW.based_on_message_id, NEW.seq, NEW.result, NEW.reply_kind,
           NEW.body, NEW.subject, NEW.note_to_employee, NEW.suggested_category, NEW.impact, NEW.urgency,
           NEW.security_concern, NEW.suggested_priority, NEW.escalate_suggestion, NEW.language, NEW.presets,
           NEW.hint, NEW.redraft_of, NEW.served_model, NEW.prompt_version, NEW.created_at)
          IS DISTINCT FROM
          (OLD.id, OLD.ticket_id, OLD.user_id, OLD.based_on_message_id, OLD.seq, OLD.result, OLD.reply_kind,
           OLD.body, OLD.subject, OLD.note_to_employee, OLD.suggested_category, OLD.impact, OLD.urgency,
           OLD.security_concern, OLD.suggested_priority, OLD.escalate_suggestion, OLD.language, OLD.presets,
           OLD.hint, OLD.redraft_of, OLD.served_model, OLD.prompt_version, OLD.created_at) THEN
        -- ON DELETE SET NULL على call_id وحده مسموح: محو سجلّ الاستدعاء بعد أيامه.
        IF NOT (OLD.call_id IS NOT NULL AND NEW.call_id IS NULL
                AND NEW.rejected_at IS NOT DISTINCT FROM OLD.rejected_at
                AND NEW.reject_reason IS NOT DISTINCT FROM OLD.reject_reason
                AND NEW.reject_note IS NOT DISTINCT FROM OLD.reject_note
                AND (NEW.id, NEW.body, NEW.result) IS NOT DISTINCT FROM (OLD.id, OLD.body, OLD.result)) THEN
            RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_immutable';
        END IF;
    END IF;
    IF NEW.call_id IS DISTINCT FROM OLD.call_id AND NEW.call_id IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_immutable';
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_draft_update_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_escalate(p_ticket uuid, p_expected_row_version integer, p_target text, p_note text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
    eid uuid;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status NOT IN ('NEW', 'OPEN', 'PENDING') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    INSERT INTO support_escalations (ticket_id, user_id, target, note) VALUES (p_ticket, uid, p_target, p_note)
    RETURNING id INTO eid;
    UPDATE support_tickets SET status = 'ESCALATED', escalation_target = p_target WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'ESCALATED', p_target, NULL, NULL, NULL, NULL);
    RETURN eid;
END
$$;
ALTER FUNCTION public.ew_support_escalate(p_ticket uuid, p_expected_row_version integer, p_target text, p_note text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_finish_call(p_call uuid, p_outcome text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    c   support_ai_calls%ROWTYPE;
BEGIN
    SELECT * INTO c FROM support_ai_calls WHERE id = p_call AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_call_not_open';
    END IF;
    -- نتيجةٌ لها أثرٌ تُكتب بدالّة أثرها. واقتراح مقالةٍ لا تكفي له التذكرة نتيجةٌ بلا أثر.
    IF p_outcome = 'OK' OR (p_outcome IN ('CANNOT_ANSWER', 'NOT_SUPPORT') AND c.kind <> 'ARTICLE_PROPOSAL') THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_outcome_needs_record';
    END IF;
    c := ew_support_ai_settle(uid, p_call, c.kind, p_outcome, p_input, p_output, p_model, p_prompt_version,
                              p_request_id, false);
    IF c.kind = 'DRAFT' AND c.ticket_id IS NOT NULL THEN
        PERFORM ew_support_log(uid, c.ticket_id, NULL, 'DRAFT_FAILED', p_outcome, NULL, NULL, NULL, 'ASSISTANT');
    ELSIF c.kind = 'REPLY_REVIEW' THEN
        UPDATE support_replies SET review = 'FAILED', review_started_at = NULL
         WHERE id = c.reply_id AND user_id = uid AND review = 'RUNNING';
        IF c.ticket_id IS NOT NULL THEN
            PERFORM ew_support_log(uid, c.ticket_id, NULL, 'REVIEW_FAILED', p_outcome, NULL, c.reply_id, NULL,
                                   'ASSISTANT');
        END IF;
    ELSIF c.kind = 'ARTICLE_PROPOSAL' AND c.ticket_id IS NOT NULL THEN
        PERFORM ew_support_log(uid, c.ticket_id, NULL, 'ARTICLE_PROPOSAL_FAILED', p_outcome, NULL, NULL, NULL,
                               'ASSISTANT');
    END IF;
END
$$;
ALTER FUNCTION public.ew_support_finish_call(p_call uuid, p_outcome text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_flag_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    source_text text;
BEGIN
    IF NEW.reply_id IS NOT NULL THEN
        SELECT body INTO source_text FROM support_replies
         WHERE id = NEW.reply_id AND ticket_id = NEW.ticket_id AND user_id = NEW.user_id AND state = 'READY';
        IF NOT FOUND THEN
            RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_target_state';
        END IF;
    ELSIF NEW.article_id IS NOT NULL THEN
        SELECT title || ' ' || issue || ' ' || coalesce(environment, '') || ' ' || resolution || ' '
               || coalesce(cause, '')
          INTO source_text FROM kb_versions
         WHERE article_id = NEW.article_id AND version = NEW.article_version AND user_id = NEW.user_id;
    END IF;
    IF NEW.evidence IS NOT NULL AND (source_text IS NULL
                                     OR strpos(ew_kb_norm(source_text), ew_kb_norm(NEW.evidence)) = 0) THEN
        RAISE EXCEPTION 'evidence' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_evidence_verbatim';
    END IF;
    IF (NEW.source = 'AI') <> (NEW.call_id IS NOT NULL) THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_source_call';
    END IF;
    NEW.created_at := now();
    IF NEW.state = 'OPEN' THEN
        NEW.resolved_at := NULL;
    ELSE
        NEW.resolved_at := now();
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_flag_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_flag_update_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF (NEW.id, NEW.user_id, NEW.ticket_id, NEW.reply_id, NEW.article_id, NEW.article_version, NEW.source,
        NEW.code, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.user_id, OLD.ticket_id, OLD.reply_id, OLD.article_id, OLD.article_version, OLD.source,
        OLD.code, OLD.created_at)
       OR (NEW.related_article_id IS DISTINCT FROM OLD.related_article_id AND NEW.related_article_id IS NOT NULL)
       OR (NEW.call_id IS DISTINCT FROM OLD.call_id AND NEW.call_id IS NOT NULL)
       OR (NEW.evidence IS DISTINCT FROM OLD.evidence AND NEW.evidence IS NOT NULL)
       OR (NEW.state <> OLD.state AND OLD.state <> 'OPEN') THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_immutable';
    END IF;
    IF NEW.state <> OLD.state THEN
        NEW.resolved_at := now();
    ELSE
        NEW.resolved_at := OLD.resolved_at;
        NEW.dismiss_reason := OLD.dismiss_reason;
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_flag_update_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_follow_up(p_closed uuid, p_client_token uuid, p_body text, p_masked smallint) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    old support_tickets%ROWTYPE;
    tid uuid;
BEGIN
    SELECT id INTO tid FROM support_tickets WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN tid;
    END IF;
    SELECT * INTO old FROM support_tickets WHERE id = p_closed AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket' USING ERRCODE = 'no_data_found';
    END IF;
    IF old.status <> 'CLOSED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_follow_up_needs_closed';
    END IF;
    PERFORM ew_support_require_notice(uid);
    INSERT INTO support_tickets (user_id, client_token, channel, priority, category, customer_label, subject,
                                 follow_up_of)
    VALUES (uid, p_client_token, old.channel, old.priority, old.category, old.customer_label, old.subject, p_closed)
    RETURNING id INTO tid;
    INSERT INTO support_messages (ticket_id, user_id, author, body, masked_count, client_token)
    VALUES (tid, uid, 'CUSTOMER', p_body, p_masked, p_client_token);
    PERFORM ew_support_log(uid, tid, NULL, 'FOLLOW_UP_CREATED', NULL, NULL, NULL, NULL, NULL);
    RETURN tid;
END
$$;
ALTER FUNCTION public.ew_support_follow_up(p_closed uuid, p_client_token uuid, p_body text, p_masked smallint) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_kb_clean(t text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $_$
    SELECT t !~ '(^|[^0-9٠-٩])[12١٢][0-9٠-٩]{9}([^0-9٠-٩]|$)'
       AND t !~ '([0-9٠-٩][ -]?){12}[0-9٠-٩]'
       AND t !~* 'SA[0-9]{2} ?[0-9]{4}'
$_$;
ALTER FUNCTION public.ew_support_kb_clean(t text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_log(p_uid uuid, p_ticket uuid, p_article uuid, p_event text, p_detail text, p_draft uuid, p_reply uuid, p_flag uuid, p_actor text) RETURNS void
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    INSERT INTO support_events (user_id, ticket_id, article_id, event, detail, draft_id, reply_id, flag_id, actor)
    VALUES (p_uid, p_ticket, p_article, p_event, p_detail, p_draft, p_reply, p_flag, coalesce(p_actor, 'EMPLOYEE'))
$$;
ALTER FUNCTION public.ew_support_log(p_uid uuid, p_ticket uuid, p_article uuid, p_event text, p_detail text, p_draft uuid, p_reply uuid, p_flag uuid, p_actor text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_me(p_for_update boolean) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    IF p_for_update THEN
        PERFORM 1 FROM users WHERE id = uid AND is_active AND profession = 'SUPPORT' FOR UPDATE;
    ELSE
        PERFORM 1 FROM users WHERE id = uid AND is_active AND profession = 'SUPPORT' FOR SHARE;
    END IF;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    INSERT INTO support_settings (user_id) VALUES (uid) ON CONFLICT (user_id) DO NOTHING;
    RETURN uid;
END
$$;
ALTER FUNCTION public.ew_support_me(p_for_update boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_message_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    t support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO t FROM support_tickets WHERE id = NEW.ticket_id AND user_id = NEW.user_id;
    IF NOT FOUND OR t.status = 'CLOSED' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    IF (SELECT count(*) FROM support_messages WHERE ticket_id = NEW.ticket_id) >= 60 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_message_cap';
    END IF;
    IF NEW.author <> 'AGENT' AND (SELECT count(*) FROM support_messages
                                   WHERE user_id = NEW.user_id AND author <> 'AGENT'
                                     AND created_at > now() - interval '24 hours')
                                 >= (CASE WHEN ew_new_open_account(NEW.user_id) THEN 60 ELSE 400 END) THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_daily_message_cap';
    END IF;
    IF NEW.author = 'AGENT' AND NOT EXISTS (SELECT 1 FROM support_replies
                                             WHERE id = NEW.reply_id AND ticket_id = NEW.ticket_id
                                               AND state = 'SENT' AND body = NEW.body) THEN
        RAISE EXCEPTION 'agent' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_agent_message_needs_sent_reply';
    END IF;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_message_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_my_ai_usage() RETURNS TABLE(kind text, per_day integer, used_today bigint)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT l.kind,
           CASE WHEN ew_new_open_account(u.id) THEN l.per_new_user_day ELSE l.per_user_day END,
           (SELECT count(*) FROM support_ai_calls c
             WHERE c.user_id = u.id AND c.kind = l.kind AND ew_is_billable(c.outcome)
               AND c.started_at > now() - interval '24 hours')
      FROM users u CROSS JOIN support_ai_limits l
     WHERE u.id = ew_current_user() AND u.is_active AND u.profession = 'SUPPORT'
     ORDER BY l.kind
$$;
ALTER FUNCTION public.ew_support_my_ai_usage() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_prepare_reply(p_ticket uuid, p_expected_row_version integer, p_client_token uuid, p_draft uuid, p_kind text, p_template boolean, p_core text, p_body text, p_rule_flags jsonb) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    t    support_tickets%ROWTYPE;
    rid  uuid;
    f    jsonb;
    flag uuid;
BEGIN
    SELECT id INTO rid FROM support_replies WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN rid;
    END IF;
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    INSERT INTO support_replies (ticket_id, user_id, draft_id, kind, origin, core, body, client_token)
    VALUES (p_ticket, uid, p_draft, p_kind,
            CASE WHEN p_draft IS NOT NULL THEN 'EDITED' WHEN p_template THEN 'TEMPLATE' ELSE 'MANUAL' END,
            p_core, p_body, p_client_token)
    RETURNING id INTO rid;
    UPDATE support_tickets SET status = t.status WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'REPLY_PREPARED',
                           (SELECT origin FROM support_replies WHERE id = rid), p_draft, rid, NULL, NULL);
    IF p_rule_flags IS NOT NULL THEN
        IF jsonb_typeof(p_rule_flags) <> 'array' OR jsonb_array_length(p_rule_flags) > 8 THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
        END IF;
        FOR f IN SELECT value FROM jsonb_array_elements(p_rule_flags) LOOP
            IF f ->> 'code' NOT IN ('PROMISE', 'ASKS_SECRET', 'NO_QUESTION', 'LINK_NOT_IN_KB', 'LANGUAGE_MISMATCH') THEN
                RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
            END IF;
            INSERT INTO support_flags (user_id, ticket_id, reply_id, source, code, evidence)
            VALUES (uid, p_ticket, rid, 'RULE', f ->> 'code', f ->> 'evidence')
            RETURNING id INTO flag;
            PERFORM ew_support_log(uid, p_ticket, NULL, 'FLAG_RAISED', f ->> 'code', NULL, rid, flag, 'SYSTEM');
        END LOOP;
    END IF;
    RETURN rid;
END
$$;
ALTER FUNCTION public.ew_support_prepare_reply(p_ticket uuid, p_expected_row_version integer, p_client_token uuid, p_draft uuid, p_kind text, p_template boolean, p_core text, p_body text, p_rule_flags jsonb) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_priority_for(p_impact text, p_urgency text, p_security boolean) RETURNS text
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT CASE
        WHEN p_impact = 'WIDESPREAD' AND p_urgency = 'STOPPED' THEN 'URGENT'
        WHEN p_security OR p_urgency = 'STOPPED'
             OR (p_impact = 'WIDESPREAD' AND p_urgency = 'DEGRADED') THEN 'HIGH'
        WHEN p_urgency = 'DEGRADED' OR p_impact = 'WIDESPREAD' THEN 'NORMAL'
        ELSE 'LOW'
    END
$$;
ALTER FUNCTION public.ew_support_priority_for(p_impact text, p_urgency text, p_security boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_priority_rank(p text) RETURNS integer
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT CASE p WHEN 'URGENT' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'NORMAL' THEN 2 WHEN 'LOW' THEN 1 END
$$;
ALTER FUNCTION public.ew_support_priority_rank(p text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_record_draft(p_call uuid, p_result text, p_reply_kind text, p_body text, p_subject text, p_note text, p_category text, p_impact text, p_urgency text, p_security boolean, p_escalate text, p_language text, p_presets text[], p_hint text, p_redraft_of uuid, p_citations jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    c   support_ai_calls%ROWTYPE;
    did uuid;
    i   integer := 0;
    q   jsonb;
BEGIN
    SELECT * INTO c FROM support_ai_calls WHERE id = p_call AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ai_call_not_open';
    END IF;
    INSERT INTO support_drafts (ticket_id, user_id, call_id, based_on_message_id, result, reply_kind, body, subject,
                                note_to_employee, suggested_category, impact, urgency, security_concern,
                                escalate_suggestion, language, presets, hint, redraft_of, served_model,
                                prompt_version)
    VALUES (c.ticket_id, uid, p_call, c.based_on_message_id, p_result, p_reply_kind, p_body, p_subject, p_note,
            p_category, p_impact, p_urgency, p_security, p_escalate, p_language, coalesce(p_presets, '{}'),
            p_hint, p_redraft_of, p_model, p_prompt_version)
    RETURNING id INTO did;
    IF p_citations IS NOT NULL THEN
        IF jsonb_typeof(p_citations) <> 'array' OR jsonb_array_length(p_citations) > 3 THEN
            RAISE EXCEPTION 'citations' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_count';
        END IF;
        FOR q IN SELECT value FROM jsonb_array_elements(p_citations) LOOP
            i := i + 1;
            INSERT INTO support_draft_citations (draft_id, user_id, position, article_id, article_version, quote)
            VALUES (did, uid, i, (q ->> 'article_id')::uuid, (q ->> 'version')::smallint, q ->> 'quote');
        END LOOP;
    END IF;
    PERFORM ew_support_ai_settle(uid, p_call, 'DRAFT',
                                 CASE p_result WHEN 'DRAFT' THEN 'OK' ELSE p_result END,
                                 p_input, p_output, p_model, p_prompt_version, p_request_id, true);
    PERFORM ew_support_log(uid, c.ticket_id, NULL, 'DRAFT_PROPOSED', p_result, did, NULL, NULL, 'ASSISTANT');
    RETURN did;
END
$$;
ALTER FUNCTION public.ew_support_record_draft(p_call uuid, p_result text, p_reply_kind text, p_body text, p_subject text, p_note text, p_category text, p_impact text, p_urgency text, p_security boolean, p_escalate text, p_language text, p_presets text[], p_hint text, p_redraft_of uuid, p_citations jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    c    support_ai_calls%ROWTYPE;
    f    jsonb;
    flag uuid;
BEGIN
    c := ew_support_ai_settle(uid, p_call, 'REPLY_REVIEW', 'OK', p_input, p_output, p_model, p_prompt_version,
                              p_request_id, true);
    UPDATE support_replies SET review = 'DONE', review_started_at = NULL
     WHERE id = c.reply_id AND user_id = uid AND review = 'RUNNING' AND state = 'READY';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'review' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_review_not_pending';
    END IF;
    IF jsonb_typeof(p_flags) <> 'array' OR jsonb_array_length(p_flags) > 4 THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
    END IF;
    FOR f IN SELECT value FROM jsonb_array_elements(p_flags) LOOP
        IF f ->> 'code' NOT IN ('UNSUPPORTED_CLAIM', 'CONTRADICTS_ARTICLE', 'UNAUTHORIZED_PROMISE',
                                'DOES_NOT_ADDRESS', 'KIND_MISMATCH', 'TONE', 'ASKS_SECRET') THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
        END IF;
        INSERT INTO support_flags (user_id, ticket_id, reply_id, source, code, evidence, related_article_id, call_id)
        VALUES (uid, c.ticket_id, c.reply_id, 'AI', f ->> 'code', f ->> 'evidence',
                (f ->> 'related_article_id')::uuid, p_call)
        RETURNING id INTO flag;
        PERFORM ew_support_log(uid, c.ticket_id, NULL, 'FLAG_RAISED', f ->> 'code', NULL, c.reply_id, flag,
                               'ASSISTANT');
    END LOOP;
    PERFORM ew_support_log(uid, c.ticket_id, NULL, 'REVIEW_DONE', NULL, NULL, c.reply_id, NULL, 'ASSISTANT');
END
$$;
ALTER FUNCTION public.ew_support_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_reject_draft(p_draft uuid, p_reason text, p_note text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    d   support_drafts%ROWTYPE;
    t   support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO d FROM support_drafts WHERE id = p_draft AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, d.ticket_id, NULL);
    IF d.rejected_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_immutable';
    END IF;
    IF EXISTS (SELECT 1 FROM support_replies WHERE draft_id = p_draft AND state IN ('READY', 'RELEASED', 'SENT')) THEN
        RAISE EXCEPTION 'used' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_in_use';
    END IF;
    UPDATE support_drafts SET rejected_at = now(), reject_reason = p_reason, reject_note = p_note WHERE id = p_draft;
    IF p_reason IN ('WRONG_INFO', 'OUTDATED_ARTICLE') THEN
        UPDATE kb_articles a
           SET needs_review = true,
               needs_review_reason = CASE p_reason WHEN 'WRONG_INFO' THEN 'DRAFT_WRONG_INFO' ELSE 'DRAFT_OUTDATED' END
          FROM support_draft_citations c
         WHERE c.draft_id = p_draft AND a.id = c.article_id AND a.state = 'PUBLISHED' AND NOT a.needs_review;
    END IF;
    PERFORM ew_support_log(uid, d.ticket_id, NULL, 'DRAFT_REJECTED', p_reason, p_draft, NULL, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_support_reject_draft(p_draft uuid, p_reason text, p_note text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_release_reply(p_reply uuid, p_via text, p_body_sha256 bytea, p_skip_review boolean) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    r   support_replies%ROWTYPE;
    t   support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO r FROM support_replies WHERE id = p_reply AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, r.ticket_id, NULL);
    IF r.state <> 'READY' THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_transition';
    END IF;
    IF r.body_sha256 <> p_body_sha256 THEN
        RAISE EXCEPTION 'hash' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_hash_mismatch';
    END IF;
    IF EXISTS (SELECT 1 FROM support_flags WHERE reply_id = p_reply AND state = 'OPEN') THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flags_open';
    END IF;
    IF r.review = 'PENDING' OR (r.review = 'RUNNING' AND r.review_started_at > now() - interval '5 minutes') THEN
        IF NOT coalesce(p_skip_review, false) THEN
            RAISE EXCEPTION 'review' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_review_waiting';
        END IF;
        UPDATE support_replies SET review = 'SKIPPED', review_started_at = NULL WHERE id = p_reply;
        PERFORM ew_support_log(uid, r.ticket_id, NULL, 'REVIEW_SKIPPED', NULL, NULL, p_reply, NULL, NULL);
    ELSIF r.review = 'RUNNING' THEN
        UPDATE support_replies SET review = 'FAILED', review_started_at = NULL WHERE id = p_reply;
    END IF;
    UPDATE support_replies SET state = 'RELEASED', release_via = p_via, released_at = now() WHERE id = p_reply;
    UPDATE support_tickets SET status = t.status WHERE id = r.ticket_id;
    PERFORM ew_support_log(uid, r.ticket_id, NULL, 'REPLY_RELEASED', p_via, r.draft_id, p_reply, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_support_release_reply(p_reply uuid, p_via text, p_body_sha256 bytea, p_skip_review boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_reopen(p_ticket uuid, p_expected_row_version integer) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status <> 'RESOLVED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    UPDATE support_tickets SET status = 'OPEN' WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'REOPENED', NULL, NULL, NULL, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_support_reopen(p_ticket uuid, p_expected_row_version integer) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_reply_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    t support_tickets%ROWTYPE;
    d support_drafts%ROWTYPE;
BEGIN
    SELECT * INTO t FROM support_tickets WHERE id = NEW.ticket_id AND user_id = NEW.user_id;
    IF NOT FOUND OR t.status = 'CLOSED' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    IF NEW.kind = 'ANSWER' AND t.status = 'ESCALATED' THEN
        RAISE EXCEPTION 'escalated' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_escalation_open';
    END IF;
    IF NEW.draft_id IS NOT NULL THEN
        SELECT * INTO d FROM support_drafts WHERE id = NEW.draft_id AND ticket_id = NEW.ticket_id;
        IF NOT FOUND OR d.rejected_at IS NOT NULL OR d.body IS NULL
           OR d.seq <> (SELECT max(seq) FROM support_drafts WHERE ticket_id = NEW.ticket_id) THEN
            RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_draft_not_current';
        END IF;
        NEW.origin := CASE WHEN NEW.core = d.body AND NEW.kind = d.reply_kind THEN 'AS_IS' ELSE 'EDITED' END;
    ELSIF NEW.origin NOT IN ('MANUAL', 'TEMPLATE') THEN
        RAISE EXCEPTION 'origin' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_origin_draft';
    END IF;
    NEW.review := CASE WHEN NEW.origin IN ('AS_IS', 'TEMPLATE') THEN 'NOT_NEEDED' ELSE 'PENDING' END;
    NEW.body_sha256 := sha256(convert_to(NEW.body, 'UTF8'));
    NEW.state := 'READY';
    NEW.release_via := NULL;
    NEW.review_started_at := NULL;
    NEW.released_at := NULL;
    NEW.sent_at := NULL;
    NEW.withdrawn_at := NULL;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_reply_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_reply_update_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF (NEW.id, NEW.ticket_id, NEW.user_id, NEW.draft_id, NEW.kind, NEW.origin, NEW.core, NEW.body,
        NEW.body_sha256, NEW.client_token, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.ticket_id, OLD.user_id, OLD.draft_id, OLD.kind, OLD.origin, OLD.core, OLD.body,
        OLD.body_sha256, OLD.client_token, OLD.created_at) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_immutable';
    END IF;
    IF NEW.state <> OLD.state AND NOT (
           (OLD.state = 'READY' AND NEW.state IN ('RELEASED', 'WITHDRAWN'))
        OR (OLD.state = 'RELEASED' AND NEW.state IN ('SENT', 'WITHDRAWN'))) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_transition';
    END IF;
    IF NEW.review <> OLD.review AND NOT (
           (OLD.review = 'PENDING' AND NEW.review IN ('RUNNING', 'SKIPPED'))
        OR (OLD.review = 'RUNNING' AND NEW.review IN ('DONE', 'FAILED', 'SKIPPED'))
        OR (OLD.review = 'FAILED' AND NEW.review IN ('RUNNING', 'SKIPPED'))) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_transition';
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_reply_update_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_require_notice(p_uid uuid) RETURNS void
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM support_settings WHERE user_id = p_uid AND notice_version IS NOT NULL) THEN
        RAISE EXCEPTION 'notice' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_notice_required';
    END IF;
END
$$;
ALTER FUNCTION public.ew_support_require_notice(p_uid uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_resolve(p_ticket uuid, p_expected_row_version integer, p_resolution text, p_confirmed boolean) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    t    support_tickets%ROWTYPE;
    last text;
    flag uuid;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status NOT IN ('NEW', 'OPEN', 'PENDING')
       OR p_resolution NOT IN ('BY_PHONE', 'IN_PERSON', 'DUPLICATE', 'NOT_SUPPORT', 'NO_RESPONSE')
       OR (p_resolution = 'NO_RESPONSE' AND t.status <> 'PENDING') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF EXISTS (SELECT 1 FROM support_replies WHERE ticket_id = p_ticket AND state IN ('READY', 'RELEASED')) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_live_reply_exists';
    END IF;
    SELECT author INTO last FROM support_messages
     WHERE ticket_id = p_ticket AND author IN ('CUSTOMER', 'AGENT') ORDER BY created_at DESC, id DESC LIMIT 1;
    IF last = 'CUSTOMER' AND p_resolution IN ('NO_RESPONSE') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF last = 'CUSTOMER' AND p_resolution NOT IN ('BY_PHONE', 'IN_PERSON', 'DUPLICATE', 'NOT_SUPPORT')
       OR (last = 'CUSTOMER' AND p_resolution IN ('DUPLICATE', 'NOT_SUPPORT') AND NOT coalesce(p_confirmed, false)) THEN
        RAISE EXCEPTION 'unanswered' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_resolve_unanswered';
    END IF;
    IF last = 'CUSTOMER' AND p_resolution IN ('DUPLICATE', 'NOT_SUPPORT') THEN
        INSERT INTO support_flags (user_id, ticket_id, source, code, state, dismiss_reason)
        VALUES (uid, p_ticket, 'RULE', 'RESOLVE_UNANSWERED', 'DISMISSED', 'CONFIRMED')
        RETURNING id INTO flag;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'FLAG_DISMISSED', 'CONFIRMED', NULL, NULL, flag, NULL);
    END IF;
    UPDATE support_tickets
       SET status = 'RESOLVED', resolution = p_resolution,
           first_replied_at = CASE WHEN p_resolution IN ('BY_PHONE', 'IN_PERSON')
                                   THEN coalesce(t.first_replied_at, now()) ELSE t.first_replied_at END
     WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'RESOLVED', p_resolution, NULL, NULL, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_support_resolve(p_ticket uuid, p_expected_row_version integer, p_resolution text, p_confirmed boolean) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_return_escalation(p_ticket uuid, p_expected_row_version integer, p_note text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status <> 'ESCALATED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF EXISTS (SELECT 1 FROM support_replies WHERE ticket_id = p_ticket AND state IN ('READY', 'RELEASED')) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_live_reply_exists';
    END IF;
    UPDATE support_escalations SET returned_at = now(), return_note = p_note
     WHERE ticket_id = p_ticket AND returned_at IS NULL;
    UPDATE support_tickets SET status = 'OPEN' WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'ESCALATION_RETURNED', t.escalation_target, NULL, NULL, NULL, NULL);
END
$$;
ALTER FUNCTION public.ew_support_return_escalation(p_ticket uuid, p_expected_row_version integer, p_note text) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_save_settings(p_signature text, p_targets jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_support_me(false);
    p   text;
BEGIN
    UPDATE support_settings SET signature = p_signature, updated_at = now() WHERE user_id = uid;
    IF p_targets IS NOT NULL THEN
        IF jsonb_typeof(p_targets) <> 'object' THEN
            RAISE EXCEPTION 'targets' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_sla_first';
        END IF;
        FOR p IN SELECT jsonb_object_keys(p_targets) LOOP
            IF jsonb_typeof(p_targets -> p) <> 'array' OR jsonb_array_length(p_targets -> p) <> 2 THEN
                RAISE EXCEPTION 'targets' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_sla_first';
            END IF;
            UPDATE support_sla_targets
               SET first_reply_minutes = (p_targets -> p ->> 0)::integer,
                   resolve_minutes = (p_targets -> p ->> 1)::integer
             WHERE user_id = uid AND priority = p;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'targets' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_sla_priority';
            END IF;
        END LOOP;
    END IF;
END
$$;
ALTER FUNCTION public.ew_support_save_settings(p_signature text, p_targets jsonb) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_set_ticket(p_ticket uuid, p_expected_row_version integer, p_category text, p_priority text, p_subject text, p_from_draft uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid       uuid := ew_support_me(false);
    t         support_tickets%ROWTYPE;
    d         support_drafts%ROWTYPE;
    suggested text;
    flag      uuid;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF p_from_draft IS NOT NULL THEN
        SELECT * INTO d FROM support_drafts WHERE id = p_from_draft AND ticket_id = p_ticket AND user_id = uid;
        IF NOT FOUND OR p_category IS DISTINCT FROM d.suggested_category
           OR p_priority IS DISTINCT FROM d.suggested_priority THEN
            RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_suggestion_mismatch';
        END IF;
    END IF;
    UPDATE support_tickets
       SET category = p_category, priority = p_priority, subject = p_subject
     WHERE id = p_ticket;
    IF p_category IS DISTINCT FROM t.category OR p_priority <> t.priority THEN
        PERFORM ew_support_log(uid, p_ticket, NULL, 'CLASSIFIED',
                               CASE WHEN p_from_draft IS NULL THEN 'MANUAL' ELSE 'ACCEPTED_SUGGESTION' END,
                               p_from_draft, NULL, NULL, NULL);
    END IF;
    IF p_subject IS DISTINCT FROM t.subject THEN
        PERFORM ew_support_log(uid, p_ticket, NULL, 'SUBJECT_SET', NULL, NULL, NULL, NULL, NULL);
    END IF;
    SELECT suggested_priority INTO suggested FROM support_drafts
     WHERE ticket_id = p_ticket ORDER BY seq DESC LIMIT 1;
    IF suggested IS NOT NULL AND p_priority <> t.priority
       AND ew_support_priority_rank(p_priority) < ew_support_priority_rank(suggested) THEN
        INSERT INTO support_flags (user_id, ticket_id, source, code)
        VALUES (uid, p_ticket, 'RULE', 'PRIORITY_BELOW_SUGGESTION')
        RETURNING id INTO flag;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'FLAG_RAISED', 'PRIORITY_BELOW_SUGGESTION', NULL, NULL, flag,
                               'SYSTEM');
    END IF;
END
$$;
ALTER FUNCTION public.ew_support_set_ticket(p_ticket uuid, p_expected_row_version integer, p_category text, p_priority text, p_subject text, p_from_draft uuid) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_settings_defaults() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO support_sla_targets (user_id, priority, first_reply_minutes, resolve_minutes) VALUES
        (NEW.user_id, 'URGENT',   60,  480),
        (NEW.user_id, 'HIGH',    240, 1440),
        (NEW.user_id, 'NORMAL',  480, 4320),
        (NEW.user_id, 'LOW',    1440, 7200);
    RETURN NULL;
END
$$;
ALTER FUNCTION public.ew_support_settings_defaults() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_text_ok(t text, p_multiline boolean) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT t = btrim(t, E' \n')
       AND t !~ '[\x01-\x09\x0B-\x1F\x7F]'
       AND (p_multiline OR strpos(t, E'\n') = 0)
       AND t !~ '[‎‏‪-‮⁦-⁩]'
$$;
ALTER FUNCTION public.ew_support_text_ok(t text, p_multiline boolean) OWNER TO eyework_owner;
CREATE TABLE public.support_tickets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    number integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'NEW'::text NOT NULL,
    priority text DEFAULT 'NORMAL'::text NOT NULL,
    category text,
    channel text NOT NULL,
    customer_label text,
    subject text,
    follow_up_of uuid,
    escalation_target text,
    resolution text,
    close_reason text,
    row_version integer DEFAULT 1 NOT NULL,
    client_token uuid NOT NULL,
    first_reply_due_at timestamp with time zone DEFAULT now() NOT NULL,
    first_replied_at timestamp with time zone,
    resolve_minutes integer DEFAULT 0 NOT NULL,
    wait_seconds integer DEFAULT 0 NOT NULL,
    clock_since timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_activity_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    closed_at timestamp with time zone,
    texts_purged_at timestamp with time zone,
    CONSTRAINT support_clock_runs CHECK (((status = ANY (ARRAY['NEW'::text, 'OPEN'::text, 'ESCALATED'::text])) = (clock_since IS NOT NULL))),
    CONSTRAINT support_close_reason CHECK (((close_reason IS NULL) OR (close_reason = ANY (ARRAY['AFTER_RESOLVED'::text, 'IDLE'::text, 'PROFESSION_CHANGED'::text])))),
    CONSTRAINT support_closed_iff_time CHECK ((((status = 'CLOSED'::text) = (closed_at IS NOT NULL)) AND ((status = 'CLOSED'::text) = (close_reason IS NOT NULL)))),
    CONSTRAINT support_customer_label_shape CHECK (((customer_label IS NULL) OR (((char_length(customer_label) >= 1) AND (char_length(customer_label) <= 30)) AND (customer_label ~ '^[ء-غف-يa-zA-Z0-9٠-٩]+( [ء-غف-يa-zA-Z0-9٠-٩]+)*$'::text) AND public.ew_support_contact_free(customer_label)))),
    CONSTRAINT support_escalated_has_target CHECK (((status = 'ESCALATED'::text) = (escalation_target IS NOT NULL))),
    CONSTRAINT support_escalation_target CHECK (((escalation_target IS NULL) OR (escalation_target = ANY (ARRAY['TIER2'::text, 'SUPERVISOR'::text, 'VENDOR'::text, 'FIELD_TECH'::text, 'OTHER_TEAM'::text])))),
    CONSTRAINT support_purge_after_close CHECK (((texts_purged_at IS NULL) OR (status = 'CLOSED'::text))),
    CONSTRAINT support_resolution CHECK (((resolution IS NULL) OR (resolution = ANY (ARRAY['REPLIED'::text, 'BY_PHONE'::text, 'IN_PERSON'::text, 'DUPLICATE'::text, 'NOT_SUPPORT'::text, 'NO_RESPONSE'::text])))),
    CONSTRAINT support_resolved_complete CHECK (((status <> 'RESOLVED'::text) OR ((resolved_at IS NOT NULL) AND (resolution IS NOT NULL)))),
    CONSTRAINT support_subject_shape CHECK (((subject IS NULL) OR (((char_length(subject) >= 3) AND (char_length(subject) <= 80)) AND public.ew_support_text_ok(subject, false) AND public.ew_support_contact_free(subject)))),
    CONSTRAINT support_ticket_category CHECK (((category IS NULL) OR (category = ANY (ARRAY['ACCOUNT'::text, 'SOFTWARE'::text, 'HARDWARE'::text, 'PRINTING'::text, 'NETWORK'::text, 'EMAIL'::text, 'INSTALL'::text, 'HOW_TO'::text, 'OTHER'::text])))),
    CONSTRAINT support_ticket_channel CHECK ((channel = ANY (ARRAY['MESSAGING'::text, 'EMAIL'::text, 'PHONE'::text, 'IN_PERSON'::text, 'WEB_FORM'::text, 'OTHER'::text]))),
    CONSTRAINT support_ticket_number CHECK ((number >= 1)),
    CONSTRAINT support_ticket_priority CHECK ((priority = ANY (ARRAY['URGENT'::text, 'HIGH'::text, 'NORMAL'::text, 'LOW'::text]))),
    CONSTRAINT support_ticket_status CHECK ((status = ANY (ARRAY['NEW'::text, 'OPEN'::text, 'PENDING'::text, 'ESCALATED'::text, 'RESOLVED'::text, 'CLOSED'::text]))),
    CONSTRAINT support_tickets_wait_seconds_check CHECK ((wait_seconds >= 0)),
    CONSTRAINT support_unresolved_clear CHECK (((status = ANY (ARRAY['RESOLVED'::text, 'CLOSED'::text])) OR ((resolved_at IS NULL) AND (resolution IS NULL))))
);
ALTER TABLE ONLY public.support_tickets FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_tickets OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ticket_for(p_uid uuid, p_ticket uuid, p_expected_row_version integer) RETURNS public.support_tickets
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    t support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO t FROM support_tickets WHERE id = p_ticket AND user_id = p_uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket' USING ERRCODE = 'no_data_found';
    END IF;
    IF p_expected_row_version IS NOT NULL AND t.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF t.status = 'CLOSED' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    RETURN t;
END
$$;
ALTER FUNCTION public.ew_support_ticket_for(p_uid uuid, p_ticket uuid, p_expected_row_version integer) OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ticket_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    n      integer;
    target support_sla_targets%ROWTYPE;
    fresh  boolean;
BEGIN
    -- FOR SHARE يقف أمام تغيير المهنة (admin set-profession يقفل الصفّ للتعديل).
    PERFORM 1 FROM users WHERE id = NEW.user_id AND is_active AND profession = 'SUPPORT' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    INSERT INTO support_settings (user_id) VALUES (NEW.user_id) ON CONFLICT (user_id) DO NOTHING;
    SELECT next_ticket_number INTO n FROM support_settings WHERE user_id = NEW.user_id FOR UPDATE;
    fresh := ew_new_open_account(NEW.user_id);
    IF (SELECT count(*) FROM support_tickets WHERE user_id = NEW.user_id AND status <> 'CLOSED')
       >= (CASE WHEN fresh THEN 30 ELSE 300 END) THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_open_ticket_cap';
    END IF;
    IF (SELECT count(*) FROM support_tickets
         WHERE user_id = NEW.user_id AND created_at > now() - interval '24 hours')
       >= (CASE WHEN fresh THEN 30 ELSE 200 END) THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_daily_ticket_cap';
    END IF;
    SELECT * INTO target FROM support_sla_targets WHERE user_id = NEW.user_id AND priority = NEW.priority;
    UPDATE support_settings SET next_ticket_number = n + 1, updated_at = now() WHERE user_id = NEW.user_id;
    NEW.number := n;
    NEW.status := 'NEW';
    NEW.row_version := 1;
    NEW.escalation_target := NULL;
    NEW.resolution := NULL;
    NEW.close_reason := NULL;
    NEW.created_at := now();
    NEW.updated_at := now();
    NEW.last_activity_at := now();
    NEW.first_reply_due_at := now() + make_interval(mins => target.first_reply_minutes);
    NEW.first_replied_at := NULL;
    NEW.resolve_minutes := target.resolve_minutes;
    NEW.wait_seconds := 0;
    NEW.clock_since := now();
    NEW.resolved_at := NULL;
    NEW.closed_at := NULL;
    NEW.texts_purged_at := NULL;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_ticket_insert_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ticket_status_event() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    INSERT INTO support_events (user_id, ticket_id, event, actor, from_status, to_status, detail)
    VALUES (NEW.user_id, NEW.id, 'STATUS_CHANGED',
            CASE WHEN ew_current_user() IS NULL THEN 'SYSTEM' ELSE 'EMPLOYEE' END,
            OLD.status, NEW.status, coalesce(NEW.close_reason, NEW.resolution));
    RETURN NULL;
END
$$;
ALTER FUNCTION public.ew_support_ticket_status_event() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_support_ticket_update_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    target support_sla_targets%ROWTYPE;
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.number <> OLD.number
       OR NEW.created_at <> OLD.created_at OR NEW.client_token <> OLD.client_token
       OR NEW.row_version <> OLD.row_version OR NEW.channel <> OLD.channel
       OR (NEW.follow_up_of IS DISTINCT FROM OLD.follow_up_of AND NEW.follow_up_of IS NOT NULL) THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_managed_columns';
    END IF;
    IF OLD.status = 'CLOSED' THEN
        IF NEW.status <> 'CLOSED' OR NEW.priority <> OLD.priority
           OR NEW.category IS DISTINCT FROM OLD.category
           OR NEW.escalation_target IS DISTINCT FROM OLD.escalation_target
           OR NEW.resolution IS DISTINCT FROM OLD.resolution
           OR NEW.close_reason IS DISTINCT FROM OLD.close_reason
           OR NEW.first_replied_at IS DISTINCT FROM OLD.first_replied_at
           OR (NEW.subject IS NOT NULL AND NEW.subject IS DISTINCT FROM OLD.subject)
           OR (NEW.customer_label IS NOT NULL AND NEW.customer_label IS DISTINCT FROM OLD.customer_label)
           OR (OLD.texts_purged_at IS NOT NULL AND NEW.texts_purged_at IS DISTINCT FROM OLD.texts_purged_at) THEN
            RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
        END IF;
        NEW.row_version := OLD.row_version + 1;
        NEW.updated_at := now();
        NEW.last_activity_at := OLD.last_activity_at;
        NEW.closed_at := OLD.closed_at;
        NEW.resolved_at := OLD.resolved_at;
        NEW.clock_since := OLD.clock_since;
        NEW.wait_seconds := OLD.wait_seconds;
        NEW.first_reply_due_at := OLD.first_reply_due_at;
        NEW.resolve_minutes := OLD.resolve_minutes;
        RETURN NEW;
    END IF;
    IF NEW.status <> OLD.status AND NOT EXISTS (
           SELECT 1 FROM support_ticket_transition WHERE from_status = OLD.status AND to_status = NEW.status) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF NEW.texts_purged_at IS DISTINCT FROM OLD.texts_purged_at THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_managed_columns';
    END IF;
    -- ساعة انتظار العميل: تجري في NEW وOPEN وESCALATED، وتقف في غيرها.
    NEW.clock_since := OLD.clock_since;
    NEW.wait_seconds := OLD.wait_seconds;
    IF NEW.status <> OLD.status THEN
        IF OLD.clock_since IS NOT NULL AND NEW.status NOT IN ('NEW', 'OPEN', 'ESCALATED') THEN
            NEW.wait_seconds := OLD.wait_seconds + floor(extract(epoch FROM now() - OLD.clock_since))::integer;
            NEW.clock_since := NULL;
        ELSIF OLD.clock_since IS NULL AND NEW.status IN ('NEW', 'OPEN', 'ESCALATED') THEN
            NEW.clock_since := now();
        END IF;
    END IF;
    NEW.resolved_at := CASE
        WHEN NEW.status = 'RESOLVED' AND OLD.status <> 'RESOLVED' THEN now()
        WHEN NEW.status IN ('RESOLVED', 'CLOSED') THEN OLD.resolved_at
        ELSE NULL END;
    IF NEW.status NOT IN ('RESOLVED', 'CLOSED') THEN
        NEW.resolution := NULL;
    ELSIF NEW.status = 'CLOSED' THEN
        NEW.resolution := OLD.resolution;
    END IF;
    NEW.closed_at := CASE WHEN NEW.status = 'CLOSED' THEN now() ELSE NULL END;
    IF NEW.status <> 'CLOSED' THEN
        NEW.close_reason := NULL;
    END IF;
    IF NEW.status <> 'ESCALATED' THEN
        NEW.escalation_target := NULL;
    END IF;
    -- أول ردٍّ يُكتب مرةً واحدة.
    IF OLD.first_replied_at IS NOT NULL THEN
        NEW.first_replied_at := OLD.first_replied_at;
    END IF;
    -- تغيير الأولوية يعيد حساب المواعيد من وقت الإنشاء، والردّ الأول إن لم يقع بعد.
    IF NEW.priority <> OLD.priority THEN
        SELECT * INTO target FROM support_sla_targets WHERE user_id = NEW.user_id AND priority = NEW.priority;
        NEW.first_reply_due_at := CASE WHEN NEW.first_replied_at IS NULL
                                       THEN OLD.created_at + make_interval(mins => target.first_reply_minutes)
                                       ELSE OLD.first_reply_due_at END;
        NEW.resolve_minutes := target.resolve_minutes;
    ELSE
        NEW.first_reply_due_at := OLD.first_reply_due_at;
        NEW.resolve_minutes := OLD.resolve_minutes;
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.last_activity_at := CASE WHEN ew_current_user() IS NULL THEN OLD.last_activity_at ELSE now() END;
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_support_ticket_update_guard() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_version_becomes_current() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    UPDATE campaigns SET current_version_id = NEW.id, status = 'COPY_PROPOSED'
     WHERE id = NEW.campaign_id;
    RETURN NULL;
END
$$;
ALTER FUNCTION public.ew_version_becomes_current() OWNER TO eyework_owner;
CREATE FUNCTION public.ew_version_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    a    generation_attempts%ROWTYPE;
    c    campaigns%ROWTYPE;
    base copy_versions%ROWTYPE;
BEGIN
    SELECT * INTO c FROM campaigns WHERE id = NEW.campaign_id FOR UPDATE;
    SELECT * INTO a FROM generation_attempts WHERE id = NEW.attempt_id FOR UPDATE;
    IF a.id IS NULL OR a.finished_at IS NOT NULL OR a.campaign_id <> NEW.campaign_id
       OR a.user_id <> NEW.user_id OR a.started_at <= now() - interval '5 minutes' THEN
        RAISE EXCEPTION 'attempt' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_needs_open_attempt';
    END IF;
    IF (a.kind = 'INITIAL' AND c.status <> 'DRAFT')
       OR (a.kind = 'EDIT' AND (c.status <> 'COPY_PROPOSED'
                                OR c.current_version_id IS DISTINCT FROM a.based_on_version_id)) THEN
        RAISE EXCEPTION 'sequence' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_sequence';
    END IF;
    IF a.image_sha256 IS DISTINCT FROM (SELECT sha256 FROM campaign_images WHERE campaign_id = NEW.campaign_id) THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_image_changed';
    END IF;
    NEW.based_on_version_id := a.based_on_version_id;
    NEW.image_sha256 := a.image_sha256;
    NEW.version := (SELECT coalesce(max(version), 0) + 1 FROM copy_versions WHERE campaign_id = NEW.campaign_id);
    IF NEW.based_on_version_id IS NOT NULL THEN
        SELECT * INTO base FROM copy_versions WHERE id = NEW.based_on_version_id;
        IF ('NEW_TITLE' = ANY (NEW.edit_presets)       AND NEW.description <> base.description)
           OR ('NEW_DESCRIPTION' = ANY (NEW.edit_presets) AND NEW.title <> base.title) THEN
            RAISE EXCEPTION 'sequence' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_sequence';
        END IF;
    END IF;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
ALTER FUNCTION public.ew_version_insert_guard() OWNER TO eyework_owner;
CREATE TABLE public.activation_tokens (
    token_hash bytea NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    CONSTRAINT activation_tokens_token_hash_check CHECK ((octet_length(token_hash) = 32)),
    CONSTRAINT activation_window CHECK (((expires_at > created_at) AND (expires_at <= (created_at + '72:00:00'::interval))))
);
ALTER TABLE ONLY public.activation_tokens FORCE ROW LEVEL SECURITY;
ALTER TABLE public.activation_tokens OWNER TO eyework_owner;
CREATE TABLE public.attempt_tombstones (
    started_at timestamp with time zone NOT NULL,
    outcome text,
    new_account boolean DEFAULT false NOT NULL
);
ALTER TABLE ONLY public.attempt_tombstones FORCE ROW LEVEL SECURITY;
ALTER TABLE public.attempt_tombstones OWNER TO eyework_owner;
CREATE TABLE public.campaign_images (
    campaign_id uuid NOT NULL,
    user_id uuid NOT NULL,
    jpeg bytea NOT NULL,
    width smallint NOT NULL,
    height smallint NOT NULL,
    sha256 bytea NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT campaign_images_height_check CHECK (((height >= 320) AND (height <= 1568))),
    CONSTRAINT campaign_images_sha256_check CHECK ((octet_length(sha256) = 32)),
    CONSTRAINT campaign_images_width_check CHECK (((width >= 320) AND (width <= 1568))),
    CONSTRAINT image_has_no_exif CHECK ((POSITION(('\x457869660000'::bytea) IN (jpeg)) = 0)),
    CONSTRAINT image_has_no_metadata CHECK (public.ew_jpeg_has_no_metadata(jpeg)),
    CONSTRAINT image_has_no_xmp CHECK ((POSITION(('\x687474703a2f2f6e732e61646f62652e636f6d2f7861702f'::bytea) IN (jpeg)) = 0)),
    CONSTRAINT image_is_jpeg CHECK ((SUBSTRING(jpeg FROM 1 FOR 3) = '\xffd8ff'::bytea)),
    CONSTRAINT image_size CHECK (((octet_length(jpeg) >= 1) AND (octet_length(jpeg) <= 3145728)))
);
ALTER TABLE ONLY public.campaign_images ALTER COLUMN jpeg SET STORAGE EXTERNAL;
ALTER TABLE ONLY public.campaign_images FORCE ROW LEVEL SECURITY;
ALTER TABLE public.campaign_images OWNER TO eyework_owner;
CREATE TABLE public.campaign_transition (
    from_status text NOT NULL,
    to_status text NOT NULL
);
ALTER TABLE public.campaign_transition OWNER TO eyework_owner;
CREATE TABLE public.campaigns (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    status text DEFAULT 'DRAFT'::text NOT NULL,
    row_version integer DEFAULT 1 NOT NULL,
    current_version_id uuid,
    approved_version_id uuid,
    budget_sar integer,
    days smallint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    approved_at timestamp with time zone,
    ready_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    CONSTRAINT approval_has_time CHECK (((approved_version_id IS NULL) = (approved_at IS NULL))),
    CONSTRAINT approval_matches_status CHECK (((status = 'CANCELLED'::text) OR ((status = ANY (ARRAY['COPY_APPROVED'::text, 'READY'::text])) = (approved_version_id IS NOT NULL)))),
    CONSTRAINT approved_is_current CHECK (((approved_version_id IS NULL) OR (approved_version_id = current_version_id))),
    CONSTRAINT budget_in_domain CHECK (((budget_sar IS NULL) OR public.ew_budget_allowed(budget_sar))),
    CONSTRAINT campaigns_status_check CHECK ((status = ANY (ARRAY['DRAFT'::text, 'COPY_PROPOSED'::text, 'COPY_APPROVED'::text, 'READY'::text, 'CANCELLED'::text]))),
    CONSTRAINT cancelled_iff_time CHECK (((status = 'CANCELLED'::text) = (cancelled_at IS NOT NULL))),
    CONSTRAINT copy_states_have_copy CHECK (((status <> ALL (ARRAY['COPY_PROPOSED'::text, 'COPY_APPROVED'::text, 'READY'::text])) OR (current_version_id IS NOT NULL))),
    CONSTRAINT days_in_range CHECK (((days IS NULL) OR ((days >= 1) AND (days <= 30)))),
    CONSTRAINT draft_has_no_copy CHECK (((status <> 'DRAFT'::text) OR (current_version_id IS NULL))),
    CONSTRAINT ready_is_complete CHECK (((status <> 'READY'::text) OR ((budget_sar IS NOT NULL) AND (days IS NOT NULL) AND (ready_at IS NOT NULL) AND (approved_version_id IS NOT NULL))))
);
ALTER TABLE ONLY public.campaigns FORCE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns OWNER TO eyework_owner;
CREATE TABLE public.copy_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    campaign_id uuid NOT NULL,
    user_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    image_sha256 bytea DEFAULT '\x'::bytea NOT NULL,
    version smallint DEFAULT 0 NOT NULL,
    based_on_version_id uuid,
    title text NOT NULL,
    description text NOT NULL,
    edit_presets text[] DEFAULT '{}'::text[] NOT NULL,
    edit_note text,
    warnings text[] DEFAULT '{}'::text[] NOT NULL,
    served_model text NOT NULL,
    prompt_version text NOT NULL,
    api_request_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    assistant_note text,
    CONSTRAINT assistant_note_shape CHECK (((assistant_note IS NULL) OR (((char_length(assistant_note) >= 1) AND (char_length(assistant_note) <= 120)) AND (strpos(assistant_note, chr(10)) = 0) AND (strpos(assistant_note, chr(13)) = 0)))),
    CONSTRAINT copy_versions_api_request_id_check CHECK ((char_length(api_request_id) <= 128)),
    CONSTRAINT copy_versions_description_check CHECK (((char_length(description) >= 40) AND (char_length(description) <= 240))),
    CONSTRAINT copy_versions_edit_note_check CHECK (((edit_note IS NULL) OR ((char_length(edit_note) >= 1) AND (char_length(edit_note) <= 200)))),
    CONSTRAINT copy_versions_edit_presets_check CHECK (((edit_presets <@ ARRAY['SHORTER'::text, 'SIMPLER'::text, 'MORE_FORMAL'::text, 'MORE_LIVELY'::text, 'NEW_TITLE'::text, 'NEW_DESCRIPTION'::text]) AND (cardinality(edit_presets) <= 3) AND (NOT (edit_presets @> ARRAY['MORE_FORMAL'::text, 'MORE_LIVELY'::text])) AND (NOT (edit_presets @> ARRAY['NEW_TITLE'::text, 'NEW_DESCRIPTION'::text])))),
    CONSTRAINT copy_versions_image_sha256_check CHECK ((octet_length(image_sha256) = 32)),
    CONSTRAINT copy_versions_prompt_version_check CHECK ((prompt_version ~ '^[a-z0-9.-]{1,32}$'::text)),
    CONSTRAINT copy_versions_served_model_check CHECK ((served_model ~ '^claude-[a-z0-9.-]{1,57}$'::text)),
    CONSTRAINT copy_versions_title_check CHECK ((((char_length(title) >= 8) AND (char_length(title) <= 60)) AND (strpos(title, chr(10)) = 0) AND (strpos(title, chr(13)) = 0))),
    CONSTRAINT copy_versions_warnings_check CHECK ((warnings <@ ARRAY['PRICE'::text, 'HEALTH_CLAIM'::text, 'SUPERLATIVE'::text])),
    CONSTRAINT edit_has_reason CHECK (((based_on_version_id IS NULL) = ((cardinality(edit_presets) = 0) AND (edit_note IS NULL)))),
    CONSTRAINT first_is_fresh CHECK (((version = 1) = (based_on_version_id IS NULL))),
    CONSTRAINT version_cap CHECK (((version >= 1) AND (version <= 10)))
);
ALTER TABLE ONLY public.copy_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.copy_versions OWNER TO eyework_owner;
CREATE TABLE public.generation_attempts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    campaign_id uuid NOT NULL,
    user_id uuid NOT NULL,
    kind text NOT NULL,
    based_on_version_id uuid,
    image_sha256 bytea NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    outcome text,
    input_tokens integer,
    output_tokens integer,
    new_account boolean DEFAULT false NOT NULL,
    CONSTRAINT finished_iff_outcome CHECK (((finished_at IS NULL) = (outcome IS NULL))),
    CONSTRAINT generation_attempts_image_sha256_check CHECK ((octet_length(image_sha256) = 32)),
    CONSTRAINT generation_attempts_input_tokens_check CHECK ((input_tokens >= 0)),
    CONSTRAINT generation_attempts_kind_check CHECK ((kind = ANY (ARRAY['INITIAL'::text, 'EDIT'::text]))),
    CONSTRAINT generation_attempts_outcome_check CHECK ((outcome = ANY (ARRAY['OK'::text, 'UNUSABLE_PHOTO'::text, 'REFUSED'::text, 'OUTPUT_INVALID'::text, 'DISCARDED'::text, 'UPSTREAM_BUSY'::text, 'UPSTREAM_UNREACHABLE'::text, 'UPSTREAM_TIMEOUT'::text, 'UPSTREAM_ERROR'::text]))),
    CONSTRAINT generation_attempts_output_tokens_check CHECK ((output_tokens >= 0)),
    CONSTRAINT kind_matches_base CHECK (((kind = 'INITIAL'::text) = (based_on_version_id IS NULL)))
);
ALTER TABLE ONLY public.generation_attempts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.generation_attempts OWNER TO eyework_owner;
CREATE TABLE public.kb_articles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    number integer DEFAULT 0 NOT NULL,
    state text DEFAULT 'DRAFT'::text NOT NULL,
    published_version smallint,
    latest_version smallint DEFAULT 0 NOT NULL,
    needs_review boolean DEFAULT false NOT NULL,
    needs_review_reason text,
    reuse_count integer DEFAULT 0 NOT NULL,
    source_ticket_id uuid,
    client_token uuid,
    row_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    published_at timestamp with time zone,
    archived_at timestamp with time zone,
    discarded_at timestamp with time zone,
    CONSTRAINT kb_archived_time CHECK (((state = 'ARCHIVED'::text) = (archived_at IS NOT NULL))),
    CONSTRAINT kb_article_number CHECK ((number >= 1)),
    CONSTRAINT kb_article_state CHECK ((state = ANY (ARRAY['PROPOSED'::text, 'DRAFT'::text, 'PUBLISHED'::text, 'ARCHIVED'::text, 'DISCARDED'::text]))),
    CONSTRAINT kb_articles_reuse_count_check CHECK ((reuse_count >= 0)),
    CONSTRAINT kb_discarded_time CHECK (((state = 'DISCARDED'::text) = (discarded_at IS NOT NULL))),
    CONSTRAINT kb_ever_published CHECK (((state = ANY (ARRAY['PUBLISHED'::text, 'ARCHIVED'::text])) = (published_at IS NOT NULL))),
    CONSTRAINT kb_published_has_version CHECK (((state = 'PUBLISHED'::text) = (published_version IS NOT NULL))),
    CONSTRAINT kb_review_iff_reason CHECK ((needs_review = (needs_review_reason IS NOT NULL))),
    CONSTRAINT kb_review_only_published CHECK (((NOT needs_review) OR (state = 'PUBLISHED'::text))),
    CONSTRAINT kb_review_reason CHECK (((needs_review_reason IS NULL) OR (needs_review_reason = ANY (ARRAY['DRAFT_WRONG_INFO'::text, 'DRAFT_OUTDATED'::text, 'EMPLOYEE'::text])))),
    CONSTRAINT kb_version_bound CHECK (((published_version IS NULL) OR (published_version <= latest_version)))
);
ALTER TABLE ONLY public.kb_articles FORCE ROW LEVEL SECURITY;
ALTER TABLE public.kb_articles OWNER TO eyework_owner;
CREATE TABLE public.kb_versions (
    article_id uuid NOT NULL,
    version smallint DEFAULT 0 NOT NULL,
    user_id uuid NOT NULL,
    title text NOT NULL,
    issue text NOT NULL,
    environment text,
    resolution text NOT NULL,
    cause text,
    origin text NOT NULL,
    call_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    search tsvector GENERATED ALWAYS AS (((setweight(to_tsvector('arabic'::regconfig, title), 'A'::"char") || setweight(to_tsvector('arabic'::regconfig, issue), 'B'::"char")) || setweight(to_tsvector('arabic'::regconfig, resolution), 'C'::"char"))) STORED,
    CONSTRAINT kb_version_cap CHECK (((version >= 1) AND (version <= 30))),
    CONSTRAINT kb_version_clean CHECK (public.ew_support_kb_clean(((((((((title || ' '::text) || issue) || ' '::text) || COALESCE(environment, ''::text)) || ' '::text) || resolution) || ' '::text) || COALESCE(cause, ''::text)))),
    CONSTRAINT kb_version_origin CHECK ((origin = ANY (ARRAY['EMPLOYEE'::text, 'AI'::text]))),
    CONSTRAINT kb_versions_cause_check CHECK (((cause IS NULL) OR (((char_length(cause) >= 3) AND (char_length(cause) <= 400)) AND public.ew_support_text_ok(cause, true)))),
    CONSTRAINT kb_versions_environment_check CHECK (((environment IS NULL) OR (((char_length(environment) >= 3) AND (char_length(environment) <= 300)) AND public.ew_support_text_ok(environment, true)))),
    CONSTRAINT kb_versions_issue_check CHECK ((((char_length(issue) >= 10) AND (char_length(issue) <= 400)) AND public.ew_support_text_ok(issue, true))),
    CONSTRAINT kb_versions_resolution_check CHECK ((((char_length(resolution) >= 20) AND (char_length(resolution) <= 4000)) AND public.ew_support_text_ok(resolution, true))),
    CONSTRAINT kb_versions_title_check CHECK ((((char_length(title) >= 4) AND (char_length(title) <= 80)) AND public.ew_support_text_ok(title, false)))
);
ALTER TABLE ONLY public.kb_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.kb_versions OWNER TO eyework_owner;
CREATE TABLE public.passkey_challenges (
    challenge_hash bytea NOT NULL,
    purpose text NOT NULL,
    user_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    CONSTRAINT passkey_challenge_owner CHECK (((purpose = 'ADD'::text) = (user_id IS NOT NULL))),
    CONSTRAINT passkey_challenge_purpose CHECK ((purpose = ANY (ARRAY['LOGIN'::text, 'ADD'::text]))),
    CONSTRAINT passkey_challenge_window CHECK (((expires_at > created_at) AND (expires_at <= (created_at + '00:05:00'::interval)))),
    CONSTRAINT passkey_challenges_challenge_hash_check CHECK ((octet_length(challenge_hash) = 32))
);
ALTER TABLE ONLY public.passkey_challenges FORCE ROW LEVEL SECURITY;
ALTER TABLE public.passkey_challenges OWNER TO eyework_owner;
CREATE TABLE public.passkeys (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    credential_id bytea NOT NULL,
    public_key bytea NOT NULL,
    sign_count bigint DEFAULT 0 NOT NULL,
    transports text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    CONSTRAINT passkey_credential_id_shape CHECK (((octet_length(credential_id) >= 1) AND (octet_length(credential_id) <= 1023))),
    CONSTRAINT passkey_public_key_shape CHECK (((octet_length(public_key) >= 1) AND (octet_length(public_key) <= 2048))),
    CONSTRAINT passkey_sign_count_range CHECK (((sign_count >= 0) AND (sign_count <= '4294967295'::bigint))),
    CONSTRAINT passkey_transports_known CHECK (((transports <@ ARRAY['usb'::text, 'nfc'::text, 'ble'::text, 'smart-card'::text, 'internal'::text, 'cable'::text, 'hybrid'::text]) AND (cardinality(transports) <= 7)))
);
ALTER TABLE ONLY public.passkeys FORCE ROW LEVEL SECURITY;
ALTER TABLE public.passkeys OWNER TO eyework_owner;
CREATE TABLE public.professions (
    code text NOT NULL,
    name_ar text NOT NULL,
    CONSTRAINT profession_code_shape CHECK ((code ~ '^[A-Z_]{3,20}$'::text)),
    CONSTRAINT profession_name_shape CHECK (((char_length(name_ar) >= 2) AND (char_length(name_ar) <= 40)))
);
ALTER TABLE ONLY public.professions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.professions OWNER TO eyework_owner;
CREATE TABLE public.registration_ledger (
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    via text NOT NULL,
    outcome text NOT NULL,
    CONSTRAINT registration_ledger_outcome CHECK ((outcome = ANY (ARRAY['OK'::text, 'TAKEN'::text]))),
    CONSTRAINT registration_ledger_taken_is_open CHECK (((outcome = 'OK'::text) OR (via = 'OPEN'::text))),
    CONSTRAINT registration_ledger_via CHECK ((via = ANY (ARRAY['CODE'::text, 'OPEN'::text])))
);
ALTER TABLE ONLY public.registration_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE public.registration_ledger OWNER TO eyework_owner;
CREATE TABLE public.sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    token_hash bytea NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT session_window CHECK (((expires_at > created_at) AND (expires_at <= (created_at + '30 days'::interval)))),
    CONSTRAINT sessions_token_hash_check CHECK ((octet_length(token_hash) = 32))
);
ALTER TABLE ONLY public.sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.sessions OWNER TO eyework_owner;
CREATE TABLE public.signup_codes (
    code_hash bytea NOT NULL,
    label text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    user_id uuid,
    taken_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT signup_codes_code_hash_check CHECK ((octet_length(code_hash) = 32)),
    CONSTRAINT signup_label_shape CHECK (((label IS NULL) OR (label ~ '^[A-Za-z0-9 _.-]{1,40}$'::text))),
    CONSTRAINT signup_taken_count CHECK (((taken_count >= 0) AND (taken_count <= 3))),
    CONSTRAINT signup_used_by CHECK (((user_id IS NULL) OR (used_at IS NOT NULL))),
    CONSTRAINT signup_window CHECK (((expires_at > created_at) AND (expires_at <= (created_at + '30 days'::interval))))
);
ALTER TABLE ONLY public.signup_codes FORCE ROW LEVEL SECURITY;
ALTER TABLE public.signup_codes OWNER TO eyework_owner;
CREATE TABLE public.support_ai_limits (
    kind text NOT NULL,
    per_user_day integer NOT NULL,
    per_new_user_day integer NOT NULL,
    per_user_10min integer NOT NULL,
    app_day integer NOT NULL,
    CONSTRAINT support_ai_kind CHECK ((kind = ANY (ARRAY['DRAFT'::text, 'REPLY_REVIEW'::text, 'ARTICLE_PROPOSAL'::text, 'ARTICLE_REVIEW'::text]))),
    CONSTRAINT support_ai_limits_app_day_check CHECK (((app_day >= 1) AND (app_day <= 2000))),
    CONSTRAINT support_ai_limits_per_new_user_day_check CHECK (((per_new_user_day >= 0) AND (per_new_user_day <= 200))),
    CONSTRAINT support_ai_limits_per_user_10min_check CHECK (((per_user_10min >= 1) AND (per_user_10min <= 50))),
    CONSTRAINT support_ai_limits_per_user_day_check CHECK (((per_user_day >= 1) AND (per_user_day <= 200))),
    CONSTRAINT support_ai_new_within_user CHECK ((per_new_user_day <= per_user_day))
);
ALTER TABLE ONLY public.support_ai_limits FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_ai_limits OWNER TO eyework_owner;
CREATE TABLE public.support_draft_citations (
    draft_id uuid NOT NULL,
    user_id uuid NOT NULL,
    "position" smallint NOT NULL,
    article_id uuid NOT NULL,
    article_version smallint NOT NULL,
    quote text NOT NULL,
    CONSTRAINT support_draft_citations_position_check CHECK ((("position" >= 1) AND ("position" <= 3))),
    CONSTRAINT support_draft_citations_quote_check CHECK ((((char_length(quote) >= 8) AND (char_length(quote) <= 300)) AND public.ew_support_text_ok(quote, true)))
);
ALTER TABLE ONLY public.support_draft_citations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_draft_citations OWNER TO eyework_owner;
CREATE TABLE public.support_drafts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ticket_id uuid NOT NULL,
    user_id uuid NOT NULL,
    call_id uuid,
    based_on_message_id uuid NOT NULL,
    seq smallint DEFAULT 0 NOT NULL,
    result text NOT NULL,
    reply_kind text,
    body text,
    subject text,
    note_to_employee text,
    suggested_category text NOT NULL,
    impact text NOT NULL,
    urgency text NOT NULL,
    security_concern boolean NOT NULL,
    suggested_priority text DEFAULT 'NORMAL'::text NOT NULL,
    escalate_suggestion text,
    language text NOT NULL,
    presets text[] DEFAULT '{}'::text[] NOT NULL,
    hint text,
    redraft_of uuid,
    rejected_at timestamp with time zone,
    reject_reason text,
    reject_note text,
    served_model text NOT NULL,
    prompt_version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT support_draft_body CHECK (((body IS NULL) OR (((char_length(body) >= 20) AND (char_length(body) <= 1200)) AND public.ew_support_text_ok(body, true) AND public.ew_support_kb_clean(body)))),
    CONSTRAINT support_draft_category CHECK ((suggested_category = ANY (ARRAY['ACCOUNT'::text, 'SOFTWARE'::text, 'HARDWARE'::text, 'PRINTING'::text, 'NETWORK'::text, 'EMAIL'::text, 'INSTALL'::text, 'HOW_TO'::text, 'OTHER'::text]))),
    CONSTRAINT support_draft_escalate CHECK (((escalate_suggestion IS NULL) OR (escalate_suggestion = ANY (ARRAY['TIER2'::text, 'SUPERVISOR'::text, 'VENDOR'::text, 'FIELD_TECH'::text, 'OTHER_TEAM'::text])))),
    CONSTRAINT support_draft_hint CHECK (((hint IS NULL) OR (((char_length(hint) >= 1) AND (char_length(hint) <= 200)) AND public.ew_support_text_ok(hint, false) AND public.ew_support_contact_free(hint)))),
    CONSTRAINT support_draft_impact CHECK ((impact = ANY (ARRAY['WIDESPREAD'::text, 'SINGLE'::text]))),
    CONSTRAINT support_draft_kind CHECK (((reply_kind IS NULL) OR (reply_kind = ANY (ARRAY['ANSWER'::text, 'ASK_INFO'::text, 'UPDATE'::text])))),
    CONSTRAINT support_draft_language CHECK ((language = ANY (ARRAY['AR'::text, 'EN'::text]))),
    CONSTRAINT support_draft_note CHECK (((note_to_employee IS NULL) OR (((char_length(note_to_employee) >= 1) AND (char_length(note_to_employee) <= 160)) AND public.ew_support_text_ok(note_to_employee, false)))),
    CONSTRAINT support_draft_presets CHECK (((presets <@ ARRAY['SHORTER'::text, 'SIMPLER'::text, 'MORE_FORMAL'::text, 'WARMER'::text, 'ASK_INFO'::text]) AND (cardinality(presets) <= 2) AND (NOT (presets @> ARRAY['MORE_FORMAL'::text, 'WARMER'::text])))),
    CONSTRAINT support_draft_priority CHECK ((suggested_priority = ANY (ARRAY['URGENT'::text, 'HIGH'::text, 'NORMAL'::text, 'LOW'::text]))),
    CONSTRAINT support_draft_reject_note CHECK (((reject_note IS NULL) OR (((char_length(reject_note) >= 1) AND (char_length(reject_note) <= 200)) AND public.ew_support_text_ok(reject_note, false) AND public.ew_support_contact_free(reject_note)))),
    CONSTRAINT support_draft_reject_reason CHECK (((reject_reason IS NULL) OR (reject_reason = ANY (ARRAY['WRONG_INFO'::text, 'NOT_IN_KB'::text, 'MISUNDERSTOOD'::text, 'TONE'::text, 'TOO_LONG'::text, 'INCOMPLETE'::text, 'OUTDATED_ARTICLE'::text, 'OTHER'::text])))),
    CONSTRAINT support_draft_rejection CHECK ((((rejected_at IS NULL) = (reject_reason IS NULL)) AND ((reject_note IS NULL) OR (reject_reason IS NOT NULL)))),
    CONSTRAINT support_draft_result CHECK ((result = ANY (ARRAY['DRAFT'::text, 'CANNOT_ANSWER'::text, 'NOT_SUPPORT'::text]))),
    CONSTRAINT support_draft_shape CHECK ((((result = 'DRAFT'::text) AND (reply_kind IS NOT NULL) AND (body IS NOT NULL)) OR ((result = 'CANNOT_ANSWER'::text) AND ((reply_kind IS NULL) = (body IS NULL)) AND (reply_kind IS DISTINCT FROM 'ANSWER'::text) AND (note_to_employee IS NOT NULL)) OR ((result = 'NOT_SUPPORT'::text) AND (reply_kind IS NULL) AND (body IS NULL) AND (note_to_employee IS NOT NULL)))),
    CONSTRAINT support_draft_subject CHECK (((subject IS NULL) OR (((char_length(subject) >= 3) AND (char_length(subject) <= 80)) AND public.ew_support_text_ok(subject, false) AND public.ew_support_contact_free(subject)))),
    CONSTRAINT support_draft_urgency CHECK ((urgency = ANY (ARRAY['STOPPED'::text, 'DEGRADED'::text, 'REQUEST'::text]))),
    CONSTRAINT support_drafts_prompt_version_check CHECK ((prompt_version ~ '^[a-z0-9.-]{1,32}$'::text)),
    CONSTRAINT support_drafts_served_model_check CHECK ((served_model ~ '^claude-[a-z0-9.-]{1,57}$'::text))
);
ALTER TABLE ONLY public.support_drafts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_drafts OWNER TO eyework_owner;
CREATE TABLE public.support_escalations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ticket_id uuid NOT NULL,
    user_id uuid NOT NULL,
    target text NOT NULL,
    note text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    returned_at timestamp with time zone,
    return_note text,
    CONSTRAINT support_escalation_note CHECK ((((char_length(note) >= 10) AND (char_length(note) <= 1000)) AND public.ew_support_text_ok(note, true) AND public.ew_support_contact_free(note))),
    CONSTRAINT support_escalation_return CHECK (((return_note IS NULL) OR (((char_length(return_note) >= 3) AND (char_length(return_note) <= 500)) AND public.ew_support_text_ok(return_note, true) AND public.ew_support_contact_free(return_note)))),
    CONSTRAINT support_escalation_return_time CHECK (((return_note IS NULL) OR (returned_at IS NOT NULL))),
    CONSTRAINT support_escalation_to CHECK ((target = ANY (ARRAY['TIER2'::text, 'SUPERVISOR'::text, 'VENDOR'::text, 'FIELD_TECH'::text, 'OTHER_TEAM'::text])))
);
ALTER TABLE ONLY public.support_escalations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_escalations OWNER TO eyework_owner;
CREATE TABLE public.support_events (
    id bigint NOT NULL,
    user_id uuid NOT NULL,
    ticket_id uuid,
    article_id uuid,
    event text NOT NULL,
    actor text DEFAULT 'EMPLOYEE'::text NOT NULL,
    from_status text,
    to_status text,
    detail text,
    draft_id uuid,
    reply_id uuid,
    flag_id uuid,
    at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT support_event_actor CHECK ((actor = ANY (ARRAY['EMPLOYEE'::text, 'ASSISTANT'::text, 'SYSTEM'::text]))),
    CONSTRAINT support_event_detail CHECK (((detail IS NULL) OR (detail ~ '^[A-Z0-9_]{2,40}$'::text))),
    CONSTRAINT support_event_kind CHECK ((event = ANY (ARRAY['TICKET_CREATED'::text, 'FOLLOW_UP_CREATED'::text, 'CUSTOMER_MESSAGE_ADDED'::text, 'NOTE_ADDED'::text, 'STATUS_CHANGED'::text, 'CLASSIFIED'::text, 'SUBJECT_SET'::text, 'DRAFT_REQUESTED'::text, 'DRAFT_PROPOSED'::text, 'DRAFT_FAILED'::text, 'DRAFT_REJECTED'::text, 'REPLY_PREPARED'::text, 'REVIEW_DONE'::text, 'REVIEW_FAILED'::text, 'REVIEW_SKIPPED'::text, 'FLAG_RAISED'::text, 'FLAG_HEEDED'::text, 'FLAG_DISMISSED'::text, 'REPLY_RELEASED'::text, 'REPLY_SENT'::text, 'REPLY_WITHDRAWN'::text, 'ESCALATED'::text, 'ESCALATION_RETURNED'::text, 'RESOLVED'::text, 'REOPENED'::text, 'TEXTS_PURGED'::text, 'ARTICLE_CREATED'::text, 'ARTICLE_PROPOSED'::text, 'ARTICLE_PROPOSAL_FAILED'::text, 'ARTICLE_VERSION_ADDED'::text, 'ARTICLE_PUBLISHED'::text, 'ARTICLE_ARCHIVED'::text, 'ARTICLE_DISCARDED'::text, 'ARTICLE_MARKED_REVIEW'::text, 'ARTICLE_REVIEW_CLEARED'::text]))),
    CONSTRAINT support_event_target CHECK (((ticket_id IS NOT NULL) OR (article_id IS NOT NULL)))
);
ALTER TABLE ONLY public.support_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_events OWNER TO eyework_owner;
ALTER TABLE public.support_events ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.support_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);
CREATE TABLE public.support_flags (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    ticket_id uuid,
    reply_id uuid,
    article_id uuid,
    article_version smallint,
    source text NOT NULL,
    code text NOT NULL,
    evidence text,
    related_article_id uuid,
    call_id uuid,
    state text DEFAULT 'OPEN'::text NOT NULL,
    dismiss_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    CONSTRAINT support_flag_code CHECK ((code = ANY (ARRAY['PROMISE'::text, 'ASKS_SECRET'::text, 'NO_QUESTION'::text, 'LINK_NOT_IN_KB'::text, 'LANGUAGE_MISMATCH'::text, 'RESOLVE_UNANSWERED'::text, 'PRIORITY_BELOW_SUGGESTION'::text, 'UNSUPPORTED_CLAIM'::text, 'CONTRADICTS_ARTICLE'::text, 'UNAUTHORIZED_PROMISE'::text, 'DOES_NOT_ADDRESS'::text, 'KIND_MISMATCH'::text, 'TONE'::text, 'PERSONAL_DATA'::text, 'UNSAFE_INSTRUCTION'::text, 'UNCLEAR_STEPS'::text]))),
    CONSTRAINT support_flag_dismiss CHECK (((dismiss_reason IS NULL) OR (dismiss_reason = ANY (ARRAY['FALSE_ALARM'::text, 'EMPLOYER_APPROVED'::text, 'KB_OUTDATED'::text, 'CONFIRMED'::text, 'OTHER'::text])))),
    CONSTRAINT support_flag_evidence CHECK (((evidence IS NULL) OR (((char_length(evidence) >= 2) AND (char_length(evidence) <= 200)) AND public.ew_support_text_ok(evidence, true)))),
    CONSTRAINT support_flag_resolution CHECK ((((state = 'OPEN'::text) = (resolved_at IS NULL)) AND ((state = 'DISMISSED'::text) = (dismiss_reason IS NOT NULL)))),
    CONSTRAINT support_flag_source CHECK ((source = ANY (ARRAY['RULE'::text, 'AI'::text]))),
    CONSTRAINT support_flag_state CHECK ((state = ANY (ARRAY['OPEN'::text, 'HEEDED'::text, 'DISMISSED'::text]))),
    CONSTRAINT support_flag_target CHECK ((((ticket_id IS NOT NULL) AND (article_id IS NULL) AND (article_version IS NULL)) OR ((ticket_id IS NULL) AND (reply_id IS NULL) AND (article_id IS NOT NULL) AND (article_version IS NOT NULL))))
);
ALTER TABLE ONLY public.support_flags FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_flags OWNER TO eyework_owner;
CREATE TABLE public.support_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ticket_id uuid NOT NULL,
    user_id uuid NOT NULL,
    author text NOT NULL,
    body text NOT NULL,
    reply_id uuid,
    masked_count smallint DEFAULT 0 NOT NULL,
    client_token uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT support_message_agent_reply CHECK (((author = 'AGENT'::text) = (reply_id IS NOT NULL))),
    CONSTRAINT support_message_agent_token CHECK (((author = 'AGENT'::text) = (client_token IS NULL))),
    CONSTRAINT support_message_author CHECK ((author = ANY (ARRAY['CUSTOMER'::text, 'AGENT'::text, 'NOTE'::text]))),
    CONSTRAINT support_message_body CHECK ((((char_length(body) >= 1) AND (char_length(body) <= 4000)) AND public.ew_support_text_ok(body, true))),
    CONSTRAINT support_message_contact_free CHECK (((author = 'AGENT'::text) OR public.ew_support_contact_free(body))),
    CONSTRAINT support_messages_masked_count_check CHECK (((masked_count >= 0) AND (masked_count <= 500)))
);
ALTER TABLE ONLY public.support_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_messages OWNER TO eyework_owner;
CREATE TABLE public.support_replies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ticket_id uuid NOT NULL,
    user_id uuid NOT NULL,
    draft_id uuid,
    kind text NOT NULL,
    origin text NOT NULL,
    core text NOT NULL,
    body text NOT NULL,
    body_sha256 bytea DEFAULT '\x'::bytea NOT NULL,
    state text DEFAULT 'READY'::text NOT NULL,
    review text DEFAULT 'NOT_NEEDED'::text NOT NULL,
    release_via text,
    client_token uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    review_started_at timestamp with time zone,
    released_at timestamp with time zone,
    sent_at timestamp with time zone,
    withdrawn_at timestamp with time zone,
    CONSTRAINT support_replies_body_sha256_check CHECK ((octet_length(body_sha256) = 32)),
    CONSTRAINT support_reply_body CHECK ((((char_length(body) >= 20) AND (char_length(body) <= 1500)) AND public.ew_support_text_ok(body, true) AND public.ew_support_kb_clean(body))),
    CONSTRAINT support_reply_contains_core CHECK ((strpos(body, core) > 0)),
    CONSTRAINT support_reply_core CHECK ((((char_length(core) >= 20) AND (char_length(core) <= 1200)) AND public.ew_support_text_ok(core, true))),
    CONSTRAINT support_reply_kind CHECK ((kind = ANY (ARRAY['ANSWER'::text, 'ASK_INFO'::text, 'UPDATE'::text]))),
    CONSTRAINT support_reply_origin CHECK ((origin = ANY (ARRAY['AS_IS'::text, 'EDITED'::text, 'MANUAL'::text, 'TEMPLATE'::text]))),
    CONSTRAINT support_reply_origin_draft CHECK (((origin = ANY (ARRAY['AS_IS'::text, 'EDITED'::text])) = (draft_id IS NOT NULL))),
    CONSTRAINT support_reply_review CHECK ((review = ANY (ARRAY['NOT_NEEDED'::text, 'PENDING'::text, 'RUNNING'::text, 'DONE'::text, 'FAILED'::text, 'SKIPPED'::text]))),
    CONSTRAINT support_reply_review_origin CHECK (((origin = ANY (ARRAY['AS_IS'::text, 'TEMPLATE'::text])) = (review = 'NOT_NEEDED'::text))),
    CONSTRAINT support_reply_running_time CHECK (((review = 'RUNNING'::text) = (review_started_at IS NOT NULL))),
    CONSTRAINT support_reply_state CHECK ((state = ANY (ARRAY['READY'::text, 'RELEASED'::text, 'SENT'::text, 'WITHDRAWN'::text]))),
    CONSTRAINT support_reply_state_times CHECK ((((state = 'READY'::text) AND (released_at IS NULL) AND (release_via IS NULL) AND (sent_at IS NULL) AND (withdrawn_at IS NULL)) OR ((state = 'RELEASED'::text) AND (released_at IS NOT NULL) AND (release_via IS NOT NULL) AND (sent_at IS NULL) AND (withdrawn_at IS NULL)) OR ((state = 'SENT'::text) AND (released_at IS NOT NULL) AND (release_via IS NOT NULL) AND (sent_at IS NOT NULL) AND (withdrawn_at IS NULL)) OR ((state = 'WITHDRAWN'::text) AND (withdrawn_at IS NOT NULL) AND (sent_at IS NULL)))),
    CONSTRAINT support_reply_via CHECK (((release_via IS NULL) OR (release_via = ANY (ARRAY['COPY'::text, 'SHARE'::text, 'SCRIPT'::text]))))
);
ALTER TABLE ONLY public.support_replies FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_replies OWNER TO eyework_owner;
CREATE TABLE public.support_settings (
    user_id uuid NOT NULL,
    signature text,
    notice_version text,
    notice_accepted_at timestamp with time zone,
    next_ticket_number integer DEFAULT 1 NOT NULL,
    next_article_number integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT support_notice_complete CHECK (((notice_version IS NULL) = (notice_accepted_at IS NULL))),
    CONSTRAINT support_notice_version_shape CHECK (((notice_version IS NULL) OR (notice_version ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'::text))),
    CONSTRAINT support_settings_next_article_number_check CHECK ((next_article_number >= 1)),
    CONSTRAINT support_settings_next_ticket_number_check CHECK ((next_ticket_number >= 1)),
    CONSTRAINT support_signature_shape CHECK (((signature IS NULL) OR (((char_length(signature) >= 2) AND (char_length(signature) <= 60)) AND public.ew_support_text_ok(signature, false) AND public.ew_support_contact_free(signature))))
);
ALTER TABLE ONLY public.support_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_settings OWNER TO eyework_owner;
CREATE TABLE public.support_sla_targets (
    user_id uuid NOT NULL,
    priority text NOT NULL,
    first_reply_minutes integer NOT NULL,
    resolve_minutes integer NOT NULL,
    CONSTRAINT support_sla_first CHECK ((first_reply_minutes = ANY (ARRAY[30, 60, 120, 240, 480, 1440]))),
    CONSTRAINT support_sla_order CHECK ((first_reply_minutes < resolve_minutes)),
    CONSTRAINT support_sla_priority CHECK ((priority = ANY (ARRAY['URGENT'::text, 'HIGH'::text, 'NORMAL'::text, 'LOW'::text]))),
    CONSTRAINT support_sla_resolve CHECK ((resolve_minutes = ANY (ARRAY[240, 480, 1440, 2880, 4320, 7200])))
);
ALTER TABLE ONLY public.support_sla_targets FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_sla_targets OWNER TO eyework_owner;
CREATE TABLE public.support_ticket_transition (
    from_status text NOT NULL,
    to_status text NOT NULL
);
ALTER TABLE ONLY public.support_ticket_transition FORCE ROW LEVEL SECURITY;
ALTER TABLE public.support_ticket_transition OWNER TO eyework_owner;
CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    login_hmac bytea NOT NULL,
    password_hash text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    activated_at timestamp with time zone,
    display_name text,
    profession text NOT NULL,
    birth_date date,
    self_registered boolean DEFAULT false NOT NULL,
    terms_version text,
    terms_accepted_at timestamp with time zone,
    open_registered boolean DEFAULT false NOT NULL,
    ui_size text,
    CONSTRAINT activated_iff_password CHECK (((activated_at IS NULL) = (password_hash IS NULL))),
    CONSTRAINT birth_date_range CHECK (((birth_date IS NULL) OR (birth_date >= '1900-01-01'::date))),
    CONSTRAINT display_name_shape CHECK (((display_name IS NULL) OR (((char_length(display_name) >= 1) AND (char_length(display_name) <= 30)) AND (display_name ~ '^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$'::text)))),
    CONSTRAINT open_registered_is_self_registered CHECK (((NOT open_registered) OR self_registered)),
    CONSTRAINT self_registered_accepted_terms CHECK (((NOT self_registered) OR (terms_version IS NOT NULL))),
    CONSTRAINT terms_complete CHECK (((terms_version IS NULL) = (terms_accepted_at IS NULL))),
    CONSTRAINT terms_version_shape CHECK (((terms_version IS NULL) OR (terms_version ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'::text))),
    CONSTRAINT ui_size_known CHECK ((ui_size = ANY (ARRAY['COMPACT'::text, 'GAZE'::text]))),
    CONSTRAINT users_login_hmac_check CHECK ((octet_length(login_hmac) = 32)),
    CONSTRAINT users_password_hash_check CHECK ((password_hash ~ '^scrypt\$[0-9a-f]{32}\$[0-9a-f]{128}$'::text))
);
ALTER TABLE ONLY public.users FORCE ROW LEVEL SECURITY;
ALTER TABLE public.users OWNER TO eyework_owner;
ALTER TABLE ONLY public.activation_tokens
    ADD CONSTRAINT activation_tokens_pkey PRIMARY KEY (token_hash);
ALTER TABLE ONLY public.campaign_images
    ADD CONSTRAINT campaign_images_pkey PRIMARY KEY (campaign_id);
ALTER TABLE ONLY public.campaign_transition
    ADD CONSTRAINT campaign_transition_pkey PRIMARY KEY (from_status, to_status);
ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_id_user_id_key UNIQUE (id, user_id);
ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_attempt_id_key UNIQUE (attempt_id);
ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_id_key UNIQUE (campaign_id, id);
ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_version_key UNIQUE (campaign_id, version);
ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.generation_attempts
    ADD CONSTRAINT generation_attempts_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.kb_articles
    ADD CONSTRAINT kb_articles_id_user_id_key UNIQUE (id, user_id);
ALTER TABLE ONLY public.kb_articles
    ADD CONSTRAINT kb_articles_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.kb_articles
    ADD CONSTRAINT kb_articles_user_id_client_token_key UNIQUE (user_id, client_token);
ALTER TABLE ONLY public.kb_articles
    ADD CONSTRAINT kb_articles_user_id_number_key UNIQUE (user_id, number);
ALTER TABLE ONLY public.kb_versions
    ADD CONSTRAINT kb_versions_pkey PRIMARY KEY (article_id, version);
ALTER TABLE ONLY public.passkey_challenges
    ADD CONSTRAINT passkey_challenges_pkey PRIMARY KEY (challenge_hash);
ALTER TABLE ONLY public.passkeys
    ADD CONSTRAINT passkeys_credential_id_key UNIQUE (credential_id);
ALTER TABLE ONLY public.passkeys
    ADD CONSTRAINT passkeys_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.professions
    ADD CONSTRAINT professions_pkey PRIMARY KEY (code);
ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_token_hash_key UNIQUE (token_hash);
ALTER TABLE ONLY public.signup_codes
    ADD CONSTRAINT signup_codes_pkey PRIMARY KEY (code_hash);
ALTER TABLE ONLY public.support_ai_calls
    ADD CONSTRAINT support_ai_calls_id_user_id_key UNIQUE (id, user_id);
ALTER TABLE ONLY public.support_ai_calls
    ADD CONSTRAINT support_ai_calls_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_ai_limits
    ADD CONSTRAINT support_ai_limits_pkey PRIMARY KEY (kind);
ALTER TABLE ONLY public.support_draft_citations
    ADD CONSTRAINT support_draft_citations_pkey PRIMARY KEY (draft_id, "position");
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_call_id_key UNIQUE (call_id);
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_id_user_id_key UNIQUE (id, user_id);
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_ticket_id_id_key UNIQUE (ticket_id, id);
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_ticket_id_seq_key UNIQUE (ticket_id, seq);
ALTER TABLE ONLY public.support_escalations
    ADD CONSTRAINT support_escalations_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_events
    ADD CONSTRAINT support_events_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_id_user_id_key UNIQUE (id, user_id);
ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_reply_id_key UNIQUE (reply_id);
ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_ticket_id_id_key UNIQUE (ticket_id, id);
ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_user_id_client_token_key UNIQUE (user_id, client_token);
ALTER TABLE ONLY public.support_replies
    ADD CONSTRAINT support_replies_id_user_id_key UNIQUE (id, user_id);
ALTER TABLE ONLY public.support_replies
    ADD CONSTRAINT support_replies_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_replies
    ADD CONSTRAINT support_replies_user_id_client_token_key UNIQUE (user_id, client_token);
ALTER TABLE ONLY public.support_settings
    ADD CONSTRAINT support_settings_pkey PRIMARY KEY (user_id);
ALTER TABLE ONLY public.support_sla_targets
    ADD CONSTRAINT support_sla_targets_pkey PRIMARY KEY (user_id, priority);
ALTER TABLE ONLY public.support_ticket_transition
    ADD CONSTRAINT support_ticket_transition_pkey PRIMARY KEY (from_status, to_status);
ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_id_user_id_key UNIQUE (id, user_id);
ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_user_id_client_token_key UNIQUE (user_id, client_token);
ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_user_id_number_key UNIQUE (user_id, number);
ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_login_hmac_key UNIQUE (login_hmac);
ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);
CREATE UNIQUE INDEX activation_one_open ON public.activation_tokens USING btree (user_id) WHERE (used_at IS NULL);
CREATE INDEX attempt_tombstones_time ON public.attempt_tombstones USING btree (started_at);
CREATE INDEX attempts_campaign ON public.generation_attempts USING btree (campaign_id);
CREATE INDEX attempts_time ON public.generation_attempts USING btree (started_at DESC);
CREATE INDEX attempts_user_time ON public.generation_attempts USING btree (user_id, started_at DESC);
CREATE INDEX campaigns_user_recent ON public.campaigns USING btree (user_id, updated_at DESC);
CREATE INDEX kb_articles_user_state ON public.kb_articles USING btree (user_id, state, updated_at DESC);
CREATE INDEX kb_versions_search ON public.kb_versions USING gin (search);
CREATE INDEX passkey_challenges_expiry_idx ON public.passkey_challenges USING btree (expires_at);
CREATE INDEX passkeys_user_idx ON public.passkeys USING btree (user_id);
CREATE INDEX registration_ledger_time ON public.registration_ledger USING btree (occurred_at);
CREATE INDEX sessions_user_idx ON public.sessions USING btree (user_id) WHERE (revoked_at IS NULL);
CREATE INDEX support_ai_calls_kind_time ON public.support_ai_calls USING btree (kind, started_at DESC);
CREATE INDEX support_ai_calls_time ON public.support_ai_calls USING btree (started_at DESC);
CREATE INDEX support_ai_calls_user_time ON public.support_ai_calls USING btree (user_id, started_at DESC);
CREATE INDEX support_citations_article ON public.support_draft_citations USING btree (article_id);
CREATE INDEX support_drafts_user_rejected ON public.support_drafts USING btree (user_id, rejected_at DESC) WHERE (rejected_at IS NOT NULL);
CREATE INDEX support_events_article ON public.support_events USING btree (article_id, id) WHERE (article_id IS NOT NULL);
CREATE INDEX support_events_ticket ON public.support_events USING btree (ticket_id, id) WHERE (ticket_id IS NOT NULL);
CREATE INDEX support_events_user_time ON public.support_events USING btree (user_id, at DESC);
CREATE INDEX support_flags_article ON public.support_flags USING btree (article_id, article_version) WHERE (article_id IS NOT NULL);
CREATE INDEX support_flags_reply ON public.support_flags USING btree (reply_id) WHERE (reply_id IS NOT NULL);
CREATE INDEX support_flags_ticket ON public.support_flags USING btree (ticket_id) WHERE (ticket_id IS NOT NULL);
CREATE INDEX support_messages_ticket ON public.support_messages USING btree (ticket_id, created_at);
CREATE INDEX support_messages_user_time ON public.support_messages USING btree (user_id, created_at DESC) WHERE (author <> 'AGENT'::text);
CREATE UNIQUE INDEX support_one_live_reply ON public.support_replies USING btree (ticket_id) WHERE (state = ANY (ARRAY['READY'::text, 'RELEASED'::text]));
CREATE UNIQUE INDEX support_one_open_escalation ON public.support_escalations USING btree (ticket_id) WHERE (returned_at IS NULL);
CREATE INDEX support_replies_released ON public.support_replies USING btree (user_id, released_at) WHERE (state = 'RELEASED'::text);
CREATE INDEX support_tickets_closed ON public.support_tickets USING btree (closed_at) WHERE (status = 'CLOSED'::text);
CREATE INDEX support_tickets_idle ON public.support_tickets USING btree (last_activity_at) WHERE (status <> 'CLOSED'::text);
CREATE INDEX support_tickets_queue ON public.support_tickets USING btree (user_id, status, first_reply_due_at);
CREATE INDEX support_tickets_recent ON public.support_tickets USING btree (user_id, updated_at DESC);
CREATE INDEX support_tickets_resolved ON public.support_tickets USING btree (resolved_at) WHERE (status = 'RESOLVED'::text);
CREATE TRIGGER trg_attempt_settle BEFORE UPDATE ON public.generation_attempts FOR EACH ROW EXECUTE FUNCTION public.ew_attempt_settle_once();
CREATE TRIGGER trg_attempt_tombstone BEFORE DELETE ON public.generation_attempts FOR EACH ROW EXECUTE FUNCTION public.ew_attempt_tombstone();
CREATE TRIGGER trg_campaign_guard BEFORE UPDATE ON public.campaigns FOR EACH ROW EXECUTE FUNCTION public.ew_campaign_guard();
CREATE TRIGGER trg_campaign_insert BEFORE INSERT ON public.campaigns FOR EACH ROW EXECUTE FUNCTION public.ew_campaign_insert_guard();
CREATE TRIGGER trg_image_guard BEFORE INSERT OR UPDATE ON public.campaign_images FOR EACH ROW EXECUTE FUNCTION public.ew_image_guard();
CREATE TRIGGER trg_image_touch BEFORE UPDATE ON public.campaign_images FOR EACH ROW EXECUTE FUNCTION public.ew_image_touch();
CREATE TRIGGER trg_kb_article_insert BEFORE INSERT ON public.kb_articles FOR EACH ROW EXECUTE FUNCTION public.ew_kb_article_insert_guard();
CREATE TRIGGER trg_kb_article_update BEFORE UPDATE ON public.kb_articles FOR EACH ROW EXECUTE FUNCTION public.ew_kb_article_update_guard();
CREATE TRIGGER trg_kb_version_insert BEFORE INSERT ON public.kb_versions FOR EACH ROW EXECUTE FUNCTION public.ew_kb_version_insert_guard();
CREATE TRIGGER trg_kb_versions_append_only BEFORE UPDATE ON public.kb_versions FOR EACH ROW EXECUTE FUNCTION public.ew_kb_version_update_guard();
CREATE TRIGGER trg_purge_image AFTER UPDATE OF status ON public.campaigns FOR EACH ROW WHEN ((new.status = 'CANCELLED'::text)) EXECUTE FUNCTION public.ew_purge_image_on_cancel();
CREATE TRIGGER trg_support_ai_settle BEFORE UPDATE ON public.support_ai_calls FOR EACH ROW EXECUTE FUNCTION public.ew_attempt_settle_once();
CREATE TRIGGER trg_support_ai_tombstone BEFORE DELETE ON public.support_ai_calls FOR EACH ROW EXECUTE FUNCTION public.ew_support_ai_tombstone();
CREATE TRIGGER trg_support_citation BEFORE INSERT ON public.support_draft_citations FOR EACH ROW EXECUTE FUNCTION public.ew_support_citation_guard();
CREATE TRIGGER trg_support_citations_append_only BEFORE UPDATE ON public.support_draft_citations FOR EACH ROW EXECUTE FUNCTION public.ew_forbid_update();
CREATE CONSTRAINT TRIGGER trg_support_draft_grounded AFTER INSERT ON public.support_drafts DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.ew_support_draft_grounded();
CREATE TRIGGER trg_support_draft_insert BEFORE INSERT ON public.support_drafts FOR EACH ROW EXECUTE FUNCTION public.ew_support_draft_insert_guard();
CREATE TRIGGER trg_support_draft_update BEFORE UPDATE ON public.support_drafts FOR EACH ROW EXECUTE FUNCTION public.ew_support_draft_update_guard();
CREATE TRIGGER trg_support_events_append_only BEFORE UPDATE ON public.support_events FOR EACH ROW EXECUTE FUNCTION public.ew_forbid_update();
CREATE TRIGGER trg_support_flag_insert BEFORE INSERT ON public.support_flags FOR EACH ROW EXECUTE FUNCTION public.ew_support_flag_insert_guard();
CREATE TRIGGER trg_support_flag_update BEFORE UPDATE ON public.support_flags FOR EACH ROW EXECUTE FUNCTION public.ew_support_flag_update_guard();
CREATE TRIGGER trg_support_message_insert BEFORE INSERT ON public.support_messages FOR EACH ROW EXECUTE FUNCTION public.ew_support_message_insert_guard();
CREATE TRIGGER trg_support_messages_append_only BEFORE UPDATE ON public.support_messages FOR EACH ROW EXECUTE FUNCTION public.ew_forbid_update();
CREATE TRIGGER trg_support_reply_insert BEFORE INSERT ON public.support_replies FOR EACH ROW EXECUTE FUNCTION public.ew_support_reply_insert_guard();
CREATE TRIGGER trg_support_reply_update BEFORE UPDATE ON public.support_replies FOR EACH ROW EXECUTE FUNCTION public.ew_support_reply_update_guard();
CREATE TRIGGER trg_support_settings_defaults AFTER INSERT ON public.support_settings FOR EACH ROW EXECUTE FUNCTION public.ew_support_settings_defaults();
CREATE TRIGGER trg_support_ticket_insert BEFORE INSERT ON public.support_tickets FOR EACH ROW EXECUTE FUNCTION public.ew_support_ticket_insert_guard();
CREATE TRIGGER trg_support_ticket_status_event AFTER UPDATE OF status ON public.support_tickets FOR EACH ROW WHEN ((new.status IS DISTINCT FROM old.status)) EXECUTE FUNCTION public.ew_support_ticket_status_event();
CREATE TRIGGER trg_support_ticket_update BEFORE UPDATE ON public.support_tickets FOR EACH ROW EXECUTE FUNCTION public.ew_support_ticket_update_guard();
CREATE TRIGGER trg_version_current AFTER INSERT ON public.copy_versions FOR EACH ROW EXECUTE FUNCTION public.ew_version_becomes_current();
CREATE TRIGGER trg_version_insert BEFORE INSERT ON public.copy_versions FOR EACH ROW EXECUTE FUNCTION public.ew_version_insert_guard();
CREATE TRIGGER trg_versions_append_only BEFORE UPDATE ON public.copy_versions FOR EACH ROW EXECUTE FUNCTION public.ew_forbid_update();
ALTER TABLE ONLY public.activation_tokens
    ADD CONSTRAINT activation_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT approved_version_belongs FOREIGN KEY (id, approved_version_id) REFERENCES public.copy_versions(campaign_id, id);
ALTER TABLE ONLY public.generation_attempts
    ADD CONSTRAINT attempt_base_belongs FOREIGN KEY (campaign_id, based_on_version_id) REFERENCES public.copy_versions(campaign_id, id);
ALTER TABLE ONLY public.campaign_images
    ADD CONSTRAINT campaign_images_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.campaigns(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_attempt_id_fkey FOREIGN KEY (attempt_id) REFERENCES public.generation_attempts(id);
ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_based_on_version_id_fkey FOREIGN KEY (campaign_id, based_on_version_id) REFERENCES public.copy_versions(campaign_id, id);
ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.campaigns(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT current_version_belongs FOREIGN KEY (id, current_version_id) REFERENCES public.copy_versions(campaign_id, id);
ALTER TABLE ONLY public.generation_attempts
    ADD CONSTRAINT generation_attempts_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.campaigns(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.kb_articles
    ADD CONSTRAINT kb_articles_source_ticket_id_user_id_fkey FOREIGN KEY (source_ticket_id, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE SET NULL (source_ticket_id);
ALTER TABLE ONLY public.kb_articles
    ADD CONSTRAINT kb_articles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.kb_versions
    ADD CONSTRAINT kb_versions_article_id_user_id_fkey FOREIGN KEY (article_id, user_id) REFERENCES public.kb_articles(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.kb_versions
    ADD CONSTRAINT kb_versions_call_id_fkey FOREIGN KEY (call_id) REFERENCES public.support_ai_calls(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.passkey_challenges
    ADD CONSTRAINT passkey_challenges_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.passkeys
    ADD CONSTRAINT passkeys_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.signup_codes
    ADD CONSTRAINT signup_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.support_ai_calls
    ADD CONSTRAINT support_ai_calls_kind_fkey FOREIGN KEY (kind) REFERENCES public.support_ai_limits(kind) ON DELETE RESTRICT;
ALTER TABLE ONLY public.support_ai_calls
    ADD CONSTRAINT support_ai_calls_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_draft_citations
    ADD CONSTRAINT support_draft_citations_article_id_article_version_fkey FOREIGN KEY (article_id, article_version) REFERENCES public.kb_versions(article_id, version) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_draft_citations
    ADD CONSTRAINT support_draft_citations_article_id_user_id_fkey FOREIGN KEY (article_id, user_id) REFERENCES public.kb_articles(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_draft_citations
    ADD CONSTRAINT support_draft_citations_draft_id_user_id_fkey FOREIGN KEY (draft_id, user_id) REFERENCES public.support_drafts(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_call_id_fkey FOREIGN KEY (call_id) REFERENCES public.support_ai_calls(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_ticket_id_based_on_message_id_fkey FOREIGN KEY (ticket_id, based_on_message_id) REFERENCES public.support_messages(ticket_id, id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_ticket_id_redraft_of_fkey FOREIGN KEY (ticket_id, redraft_of) REFERENCES public.support_drafts(ticket_id, id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_drafts
    ADD CONSTRAINT support_drafts_ticket_id_user_id_fkey FOREIGN KEY (ticket_id, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_escalations
    ADD CONSTRAINT support_escalations_ticket_id_user_id_fkey FOREIGN KEY (ticket_id, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_events
    ADD CONSTRAINT support_events_article_id_user_id_fkey FOREIGN KEY (article_id, user_id) REFERENCES public.kb_articles(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_events
    ADD CONSTRAINT support_events_ticket_id_user_id_fkey FOREIGN KEY (ticket_id, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_events
    ADD CONSTRAINT support_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_article_id_article_version_fkey FOREIGN KEY (article_id, article_version) REFERENCES public.kb_versions(article_id, version) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_article_id_user_id_fkey FOREIGN KEY (article_id, user_id) REFERENCES public.kb_articles(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_call_id_fkey FOREIGN KEY (call_id) REFERENCES public.support_ai_calls(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_related_article_id_user_id_fkey FOREIGN KEY (related_article_id, user_id) REFERENCES public.kb_articles(id, user_id) ON DELETE SET NULL (related_article_id);
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_reply_id_user_id_fkey FOREIGN KEY (reply_id, user_id) REFERENCES public.support_replies(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_ticket_id_user_id_fkey FOREIGN KEY (ticket_id, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_flags
    ADD CONSTRAINT support_flags_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_message_reply_fk FOREIGN KEY (reply_id) REFERENCES public.support_replies(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_ticket_id_user_id_fkey FOREIGN KEY (ticket_id, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_replies
    ADD CONSTRAINT support_replies_ticket_id_draft_id_fkey FOREIGN KEY (ticket_id, draft_id) REFERENCES public.support_drafts(ticket_id, id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_replies
    ADD CONSTRAINT support_replies_ticket_id_user_id_fkey FOREIGN KEY (ticket_id, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_settings
    ADD CONSTRAINT support_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_sla_targets
    ADD CONSTRAINT support_sla_targets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.support_settings(user_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_follow_up_of_user_id_fkey FOREIGN KEY (follow_up_of, user_id) REFERENCES public.support_tickets(id, user_id) ON DELETE SET NULL (follow_up_of);
ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_profession_fkey FOREIGN KEY (profession) REFERENCES public.professions(code) ON DELETE RESTRICT;
CREATE POLICY activation_owner_access ON public.activation_tokens TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.activation_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attempt_tombstones ENABLE ROW LEVEL SECURITY;
CREATE POLICY attempt_tombstones_owner_access ON public.attempt_tombstones TO eyework_owner USING (true) WITH CHECK (true);
CREATE POLICY attempts_own ON public.generation_attempts TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));
CREATE POLICY attempts_owner_access ON public.generation_attempts TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.campaign_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
CREATE POLICY campaigns_own ON public.campaigns TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));
CREATE POLICY campaigns_owner_access ON public.campaigns TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.copy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generation_attempts ENABLE ROW LEVEL SECURITY;
CREATE POLICY images_own ON public.campaign_images TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));
CREATE POLICY images_owner_access ON public.campaign_images TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.kb_articles ENABLE ROW LEVEL SECURITY;
CREATE POLICY kb_articles_own ON public.kb_articles FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY kb_articles_owner_access ON public.kb_articles TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.kb_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY kb_versions_own ON public.kb_versions FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY kb_versions_owner_access ON public.kb_versions TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.passkey_challenges ENABLE ROW LEVEL SECURITY;
CREATE POLICY passkey_challenges_owner_access ON public.passkey_challenges TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.passkeys ENABLE ROW LEVEL SECURITY;
CREATE POLICY passkeys_owner_access ON public.passkeys TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.professions ENABLE ROW LEVEL SECURITY;
CREATE POLICY professions_owner_access ON public.professions TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.registration_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY registration_ledger_owner_access ON public.registration_ledger TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY sessions_owner_access ON public.sessions TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.signup_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY signup_codes_owner_access ON public.signup_codes TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_ai_calls ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_ai_calls_own ON public.support_ai_calls FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_ai_calls_owner_access ON public.support_ai_calls TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_ai_limits ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_ai_limits_owner_access ON public.support_ai_limits TO eyework_owner USING (true) WITH CHECK (true);
CREATE POLICY support_citations_own ON public.support_draft_citations FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_citations_owner_access ON public.support_draft_citations TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_draft_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.support_drafts ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_drafts_own ON public.support_drafts FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_drafts_owner_access ON public.support_drafts TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_escalations ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_escalations_own ON public.support_escalations FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_escalations_owner_access ON public.support_escalations TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_events_own ON public.support_events FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_events_owner_access ON public.support_events TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_flags ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_flags_own ON public.support_flags FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_flags_owner_access ON public.support_flags TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_messages_own ON public.support_messages FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_messages_owner_access ON public.support_messages TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_replies ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_replies_own ON public.support_replies FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_replies_owner_access ON public.support_replies TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_settings_own ON public.support_settings FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_settings_owner_access ON public.support_settings TO eyework_owner USING (true) WITH CHECK (true);
CREATE POLICY support_sla_own ON public.support_sla_targets FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_sla_owner_access ON public.support_sla_targets TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.support_sla_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.support_ticket_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY;
CREATE POLICY support_tickets_own ON public.support_tickets FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));
CREATE POLICY support_tickets_owner_access ON public.support_tickets TO eyework_owner USING (true) WITH CHECK (true);
CREATE POLICY support_transition_owner_access ON public.support_ticket_transition TO eyework_owner USING (true) WITH CHECK (true);
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_owner_access ON public.users TO eyework_owner USING (true) WITH CHECK (true);
CREATE POLICY versions_own ON public.copy_versions TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));
CREATE POLICY versions_owner_access ON public.copy_versions TO eyework_owner USING (true) WITH CHECK (true);
REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_accept_terms(p_version text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_accept_terms(p_version text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_ai_spend(p_new_only boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_attempt_settle_once() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_attempt_tombstone() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_begin_generation(p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_begin_generation(p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_budget_allowed(v integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_budget_allowed(v integer) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_campaign_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_campaign_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_current_user() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_current_user() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_delete_me() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_delete_me() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_finish_generation(p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_finish_generation(p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_forbid_update() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_image_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_image_touch() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_is_billable(o text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_is_billable(o text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_jpeg_has_no_metadata(b bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_jpeg_has_no_metadata(b bytea) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_add_version(p_article uuid, p_expected_row_version integer, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_add_version(p_article uuid, p_expected_row_version integer, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_article_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_kb_article_update_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_kb_begin_proposal(p_ticket uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_begin_proposal(p_ticket uuid) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_begin_review(p_article uuid, p_version smallint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_begin_review(p_article uuid, p_version smallint) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_create(p_client_token uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_source_ticket uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_create(p_client_token uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_source_ticket uuid) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_mark_review(p_article uuid, p_expected_row_version integer, p_needs boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_mark_review(p_article uuid, p_expected_row_version integer, p_needs boolean) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_norm(t text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_norm(t text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_publish(p_article uuid, p_expected_row_version integer, p_version smallint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_publish(p_article uuid, p_expected_row_version integer, p_version smallint) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_record_proposal(p_call uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_record_proposal(p_call uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_search(p_query text, p_limit integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_search(p_query text, p_limit integer) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_set_state(p_article uuid, p_expected_row_version integer, p_state text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_kb_set_state(p_article uuid, p_expected_row_version integer, p_state text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_kb_version_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_kb_version_update_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_login_lookup(p_login bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_login_lookup(p_login bytea) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_my_display_name() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_display_name() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_my_generation_limit() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_generation_limit() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_my_passkeys() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_passkeys() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_my_profession() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_profession() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_my_terms_version() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_terms_version() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_my_ui_size() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_ui_size() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_new_open_account(p_user uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_open_registration_blocker() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_open_registration_blocker() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_open_session(p_user uuid, p_token bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_open_session(p_user uuid, p_token bytea) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint, p_transports text[]) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint, p_transports text[]) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_passkey_challenge(p_challenge bytea, p_purpose text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_challenge(p_challenge bytea, p_purpose text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_passkey_lookup(p_credential bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_lookup(p_credential bytea) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_passkey_signed_in(p_credential bytea, p_sign_count bigint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_signed_in(p_credential bytea, p_sign_count bigint) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_passkey_take_challenge(p_challenge bytea, p_purpose text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_take_challenge(p_challenge bytea, p_purpose text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_purge_image_on_cancel() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_register_open(p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_register_open(p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_registration_blocker(p_via text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_resolve_session(p_token bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_resolve_session(p_token bytea) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_revoke_session(p_token bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_revoke_session(p_token bytea) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_riyadh_today() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_set_my_ui_size(p_size text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_set_my_ui_size(p_size text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_signup_code_usable(p_code bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_signup_code_usable(p_code bytea) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_accept_notice(p_version text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_accept_notice(p_version text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_ack_flag(p_flag uuid, p_action text, p_reason text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_ack_flag(p_flag uuid, p_action text, p_reason text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_add_message(p_ticket uuid, p_expected_row_version integer, p_author text, p_body text, p_masked smallint, p_client_token uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_add_message(p_ticket uuid, p_expected_row_version integer, p_author text, p_body text, p_masked smallint, p_client_token uuid) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_ai_open(p_uid uuid, p_kind text, p_ticket uuid, p_reply uuid, p_article uuid, p_version smallint, p_message uuid) FROM PUBLIC;
GRANT SELECT ON TABLE public.support_ai_calls TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_ai_settle(p_uid uuid, p_call uuid, p_kind text, p_outcome text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text, p_needs_lease boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_ai_tombstone() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_begin_draft(p_ticket uuid, p_expected_row_version integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_begin_draft(p_ticket uuid, p_expected_row_version integer) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_begin_review(p_reply uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_begin_review(p_reply uuid) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_citation_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_close_due() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_close_due() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_confirm_reply(p_reply uuid, p_sent boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_confirm_reply(p_reply uuid, p_sent boolean) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_contact_free(t text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_contact_free(t text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_create_ticket(p_client_token uuid, p_channel text, p_priority text, p_category text, p_customer_label text, p_subject text, p_body text, p_masked smallint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_create_ticket(p_client_token uuid, p_channel text, p_priority text, p_category text, p_customer_label text, p_subject text, p_body text, p_masked smallint) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_draft_grounded() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_draft_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_draft_update_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_escalate(p_ticket uuid, p_expected_row_version integer, p_target text, p_note text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_escalate(p_ticket uuid, p_expected_row_version integer, p_target text, p_note text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_finish_call(p_call uuid, p_outcome text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_finish_call(p_call uuid, p_outcome text, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_flag_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_flag_update_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_follow_up(p_closed uuid, p_client_token uuid, p_body text, p_masked smallint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_follow_up(p_closed uuid, p_client_token uuid, p_body text, p_masked smallint) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_kb_clean(t text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_kb_clean(t text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_log(p_uid uuid, p_ticket uuid, p_article uuid, p_event text, p_detail text, p_draft uuid, p_reply uuid, p_flag uuid, p_actor text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_me(p_for_update boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_message_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_my_ai_usage() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_my_ai_usage() TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_prepare_reply(p_ticket uuid, p_expected_row_version integer, p_client_token uuid, p_draft uuid, p_kind text, p_template boolean, p_core text, p_body text, p_rule_flags jsonb) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_prepare_reply(p_ticket uuid, p_expected_row_version integer, p_client_token uuid, p_draft uuid, p_kind text, p_template boolean, p_core text, p_body text, p_rule_flags jsonb) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_priority_for(p_impact text, p_urgency text, p_security boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_priority_for(p_impact text, p_urgency text, p_security boolean) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_priority_rank(p text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_priority_rank(p text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_record_draft(p_call uuid, p_result text, p_reply_kind text, p_body text, p_subject text, p_note text, p_category text, p_impact text, p_urgency text, p_security boolean, p_escalate text, p_language text, p_presets text[], p_hint text, p_redraft_of uuid, p_citations jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_record_draft(p_call uuid, p_result text, p_reply_kind text, p_body text, p_subject text, p_note text, p_category text, p_impact text, p_urgency text, p_security boolean, p_escalate text, p_language text, p_presets text[], p_hint text, p_redraft_of uuid, p_citations jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_record_review(p_call uuid, p_flags jsonb, p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_reject_draft(p_draft uuid, p_reason text, p_note text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_reject_draft(p_draft uuid, p_reason text, p_note text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_release_reply(p_reply uuid, p_via text, p_body_sha256 bytea, p_skip_review boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_release_reply(p_reply uuid, p_via text, p_body_sha256 bytea, p_skip_review boolean) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_reopen(p_ticket uuid, p_expected_row_version integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_reopen(p_ticket uuid, p_expected_row_version integer) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_reply_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_reply_update_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_require_notice(p_uid uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_resolve(p_ticket uuid, p_expected_row_version integer, p_resolution text, p_confirmed boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_resolve(p_ticket uuid, p_expected_row_version integer, p_resolution text, p_confirmed boolean) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_return_escalation(p_ticket uuid, p_expected_row_version integer, p_note text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_return_escalation(p_ticket uuid, p_expected_row_version integer, p_note text) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_save_settings(p_signature text, p_targets jsonb) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_save_settings(p_signature text, p_targets jsonb) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_set_ticket(p_ticket uuid, p_expected_row_version integer, p_category text, p_priority text, p_subject text, p_from_draft uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_set_ticket(p_ticket uuid, p_expected_row_version integer, p_category text, p_priority text, p_subject text, p_from_draft uuid) TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_settings_defaults() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_text_ok(t text, p_multiline boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_support_text_ok(t text, p_multiline boolean) TO eyework_app;
GRANT SELECT ON TABLE public.support_tickets TO eyework_app;
REVOKE ALL ON FUNCTION public.ew_support_ticket_for(p_uid uuid, p_ticket uuid, p_expected_row_version integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_ticket_insert_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_ticket_status_event() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_support_ticket_update_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_version_becomes_current() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.ew_version_insert_guard() FROM PUBLIC;
GRANT SELECT ON TABLE public.campaign_images TO eyework_app;
GRANT INSERT(campaign_id) ON TABLE public.campaign_images TO eyework_app;
GRANT INSERT(user_id) ON TABLE public.campaign_images TO eyework_app;
GRANT INSERT(jpeg),UPDATE(jpeg) ON TABLE public.campaign_images TO eyework_app;
GRANT INSERT(width),UPDATE(width) ON TABLE public.campaign_images TO eyework_app;
GRANT INSERT(height),UPDATE(height) ON TABLE public.campaign_images TO eyework_app;
GRANT INSERT(sha256),UPDATE(sha256) ON TABLE public.campaign_images TO eyework_app;
GRANT SELECT ON TABLE public.campaign_transition TO eyework_app;
GRANT SELECT ON TABLE public.campaigns TO eyework_app;
GRANT INSERT(user_id) ON TABLE public.campaigns TO eyework_app;
GRANT UPDATE(status) ON TABLE public.campaigns TO eyework_app;
GRANT UPDATE(current_version_id) ON TABLE public.campaigns TO eyework_app;
GRANT UPDATE(budget_sar) ON TABLE public.campaigns TO eyework_app;
GRANT UPDATE(days) ON TABLE public.campaigns TO eyework_app;
GRANT SELECT ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(campaign_id) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(user_id) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(attempt_id) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(title) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(description) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(edit_presets) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(edit_note) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(warnings) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(served_model) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(prompt_version) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(api_request_id) ON TABLE public.copy_versions TO eyework_app;
GRANT INSERT(assistant_note) ON TABLE public.copy_versions TO eyework_app;
GRANT SELECT ON TABLE public.generation_attempts TO eyework_app;
GRANT SELECT ON TABLE public.kb_articles TO eyework_app;
GRANT SELECT ON TABLE public.kb_versions TO eyework_app;
GRANT SELECT ON TABLE public.support_draft_citations TO eyework_app;
GRANT SELECT ON TABLE public.support_drafts TO eyework_app;
GRANT SELECT ON TABLE public.support_escalations TO eyework_app;
GRANT SELECT ON TABLE public.support_events TO eyework_app;
GRANT SELECT ON TABLE public.support_flags TO eyework_app;
GRANT SELECT ON TABLE public.support_messages TO eyework_app;
GRANT SELECT ON TABLE public.support_replies TO eyework_app;
GRANT SELECT ON TABLE public.support_settings TO eyework_app;
GRANT SELECT ON TABLE public.support_sla_targets TO eyework_app;
