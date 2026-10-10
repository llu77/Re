--
-- PostgreSQL database dump
--


-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

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

--
-- Name: ew_accept_terms(text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_activate(bytea, bytea, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_ai_spend(boolean); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_ai_spend(p_new_only boolean) RETURNS bigint
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT (SELECT count(*) FROM generation_attempts
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM mkt_review_calls
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM attempt_tombstones
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
$$;


ALTER FUNCTION public.ew_ai_spend(p_new_only boolean) OWNER TO eyework_owner;

--
-- Name: ew_attempt_settle_once(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_attempt_tombstone(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_begin_generation(uuid, text, integer, uuid); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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
    fresh := ew_new_open_account(uid);
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE user_id = uid AND ew_is_billable(outcome)
                     AND started_at > now() - interval '24 hours') >= 10 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_account_cap';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF ew_ai_spend(false) >= 2000 THEN  -- ★
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF fresh AND ew_ai_spend(true) >= 400 THEN  -- ★
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

--
-- Name: ew_budget_allowed(integer); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_budget_allowed(v integer) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT (v BETWEEN 50 AND 1000 AND v % 50 = 0) OR (v BETWEEN 1250 AND 5000 AND v % 250 = 0)
$$;


ALTER FUNCTION public.ew_budget_allowed(v integer) OWNER TO eyework_owner;

--
-- Name: ew_campaign_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_campaign_insert_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_current_user(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_current_user() RETURNS uuid
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT nullif(current_setting('eyework.user_id', true), '')::uuid
$$;


ALTER FUNCTION public.ew_current_user() OWNER TO eyework_owner;

--
-- Name: ew_delete_me(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_finish_generation(uuid, text, integer, integer); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_forbid_update(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_forbid_update() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    RAISE EXCEPTION 'append-only: %', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
END
$$;


ALTER FUNCTION public.ew_forbid_update() OWNER TO eyework_owner;

--
-- Name: ew_image_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_image_touch(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_is_billable(text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_is_billable(o text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT o IS NULL OR o NOT IN ('UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE', 'UPSTREAM_ERROR')
$$;


ALTER FUNCTION public.ew_is_billable(o text) OWNER TO eyework_owner;

--
-- Name: ew_jpeg_has_no_metadata(bytea); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_jpeg_has_no_metadata(b bytea) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT bool_and(position(set_byte('\xff00'::bytea, 1, m) IN b) = 0)
      FROM unnest(ARRAY[225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 254]) AS m
$$;


ALTER FUNCTION public.ew_jpeg_has_no_metadata(b bytea) OWNER TO eyework_owner;

--
-- Name: ew_login_lookup(bytea); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_login_lookup(p_login bytea) RETURNS TABLE(user_id uuid, password_hash text)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT id, password_hash FROM users
     WHERE login_hmac = p_login AND is_active AND activated_at IS NOT NULL
$$;


ALTER FUNCTION public.ew_login_lookup(p_login bytea) OWNER TO eyework_owner;

--
-- Name: ew_mkt_allocations_check(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_allocations_check() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF (SELECT coalesce(sum(allocated_halalas), 0) FROM mkt_campaign_channels WHERE campaign_id = NEW.campaign_id)
       > (SELECT budget_halalas FROM mkt_campaigns WHERE id = NEW.campaign_id) THEN
        RAISE EXCEPTION 'budget' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_allocations_over_budget';
    END IF;
    RETURN NULL;
END
$$;


ALTER FUNCTION public.ew_mkt_allocations_check() OWNER TO eyework_owner;

--
-- Name: ew_mkt_campaign_create(text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_campaign_create(p_name text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_mkt_require();
    cid uuid;
BEGIN
    INSERT INTO mkt_campaigns (user_id, name) VALUES (uid, p_name) RETURNING id INTO cid;
    RETURN cid;
END
$$;


ALTER FUNCTION public.ew_mkt_campaign_create(p_name text) OWNER TO eyework_owner;

--
-- Name: ew_mkt_campaign_flags(uuid); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_campaign_flags(p_campaign uuid) RETURNS TABLE(flag_key text, code text, detail jsonb)
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid   uuid := ew_current_user();
    c     mkt_campaigns%ROWTYPE;
    spent bigint;
BEGIN
    SELECT * INTO c FROM mkt_campaigns WHERE id = p_campaign AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF c.kpi_metric IS NULL THEN
        RETURN QUERY SELECT 'NO_KPI'::text, 'NO_KPI'::text, jsonb_build_object('goal', c.goal);
    END IF;
    RETURN QUERY
        SELECT 'CHANNEL_PLANNED_OVER_ALLOCATION:' || ch.channel, 'CHANNEL_PLANNED_OVER_ALLOCATION'::text,
               jsonb_build_object('channel', ch.channel, 'planned', p.planned, 'allocated', ch.allocated_halalas)
          FROM mkt_campaign_channels ch
          CROSS JOIN LATERAL (SELECT coalesce(sum(planned_spend_halalas), 0) AS planned FROM mkt_items
                               WHERE campaign_id = ch.campaign_id AND channel = ch.channel
                                 AND status <> 'CANCELLED') p
         WHERE ch.campaign_id = c.id AND p.planned > ch.allocated_halalas
         ORDER BY ch.channel;
    RETURN QUERY
        SELECT 'CHANNEL_SPEND_OVER_ALLOCATION:' || ch.channel, 'CHANNEL_SPEND_OVER_ALLOCATION'::text,
               jsonb_build_object('channel', ch.channel, 'spent', s.spent, 'allocated', ch.allocated_halalas)
          FROM mkt_campaign_channels ch
          CROSS JOIN LATERAL (SELECT coalesce(sum(spend_halalas), 0) AS spent FROM mkt_results
                               WHERE campaign_id = ch.campaign_id AND channel = ch.channel) s
         WHERE ch.campaign_id = c.id AND s.spent > ch.allocated_halalas
         ORDER BY ch.channel;
    SELECT coalesce(sum(spend_halalas), 0) INTO spent FROM mkt_results WHERE campaign_id = c.id;
    IF spent > c.budget_halalas THEN
        RETURN QUERY SELECT 'TOTAL_SPEND_OVER_BUDGET'::text, 'TOTAL_SPEND_OVER_BUDGET'::text,
                            jsonb_build_object('spent', spent, 'budget', c.budget_halalas);
    END IF;
    IF c.starts_on IS NOT NULL THEN
        RETURN QUERY
            SELECT 'ITEM_OUTSIDE_CAMPAIGN:' || i.id::text, 'ITEM_OUTSIDE_CAMPAIGN'::text,
                   jsonb_build_object('item', i.id, 'channel', i.channel, 'publish_on', i.publish_on,
                                      'starts_on', c.starts_on, 'ends_on', c.ends_on)
              FROM mkt_items i
             WHERE i.campaign_id = c.id AND i.status IN ('DRAFT', 'APPROVED')
               AND (i.publish_on < c.starts_on OR i.publish_on > c.ends_on)
             ORDER BY i.publish_on, i.id
             LIMIT 20;
    END IF;
END
$$;


ALTER FUNCTION public.ew_mkt_campaign_flags(p_campaign uuid) OWNER TO eyework_owner;

--
-- Name: ew_mkt_campaign_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_campaign_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    allocated bigint;
BEGIN
    IF OLD.status = 'CANCELLED' THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_is_final';
    END IF;
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_managed_columns';
    END IF;
    IF NEW.status <> OLD.status AND NOT EXISTS (
           SELECT 1 FROM mkt_campaign_transition WHERE from_status = OLD.status AND to_status = NEW.status) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_transition';
    END IF;
    -- الخطة تتغيّر في التخطيط وحده: ما اعتُمد هو ما رآه صاحبه.
    IF ROW(NEW.name, NEW.brief, NEW.goal, NEW.kpi_metric, NEW.kpi_target, NEW.audience, NEW.budget_halalas,
           NEW.starts_on, NEW.ends_on)
       IS DISTINCT FROM ROW(OLD.name, OLD.brief, OLD.goal, OLD.kpi_metric, OLD.kpi_target, OLD.audience,
                            OLD.budget_halalas, OLD.starts_on, OLD.ends_on) THEN
        IF NOT (OLD.status = 'PLANNING' AND NEW.status = 'PLANNING') THEN
            RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
        END IF;
        IF NEW.starts_on IS DISTINCT FROM OLD.starts_on AND NEW.starts_on > ew_riyadh_today() + 730 THEN
            RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_dates_range';
        END IF;
    END IF;
    IF NEW.budget_halalas < OLD.budget_halalas THEN
        SELECT coalesce(sum(allocated_halalas), 0) INTO allocated FROM mkt_campaign_channels WHERE campaign_id = NEW.id;
        IF allocated > NEW.budget_halalas THEN
            RAISE EXCEPTION 'budget' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_allocations_over_budget';
        END IF;
    END IF;
    -- النتائج المُدخلة تبقى داخل الحملة: لا تُقصّ المواعيد من تحتها.
    IF ROW(NEW.starts_on, NEW.ends_on) IS DISTINCT FROM ROW(OLD.starts_on, OLD.ends_on) AND EXISTS (
           SELECT 1 FROM mkt_results r WHERE r.campaign_id = NEW.id
              AND (NEW.starts_on IS NULL OR NEW.ends_on IS NULL
                   OR r.period_start < NEW.starts_on OR r.period_end > NEW.ends_on)) THEN
        RAISE EXCEPTION 'dates' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_dates_exclude_results';
    END IF;
    IF NEW.status = 'APPROVED' AND OLD.status <> 'APPROVED'
       AND NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = NEW.id) THEN
        RAISE EXCEPTION 'incomplete' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_incomplete';
    END IF;

    -- أعمدةٌ يكتبها المحفّز وحده.
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.approved_at := CASE WHEN NEW.status = 'APPROVED'
                            THEN CASE WHEN OLD.status = 'APPROVED' THEN OLD.approved_at ELSE now() END END;
    NEW.approved_with_flags := CASE
        WHEN NEW.status = 'APPROVED' AND OLD.status = 'APPROVED' THEN OLD.approved_with_flags
        WHEN NEW.status = 'APPROVED' THEN NEW.approved_with_flags
        ELSE '{}'::text[] END;
    NEW.cancelled_at := CASE WHEN NEW.status = 'CANCELLED' THEN now() END;
    RETURN NEW;
END
$$;


ALTER FUNCTION public.ew_mkt_campaign_guard() OWNER TO eyework_owner;

--
-- Name: ew_mkt_campaign_insert_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_campaign_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
    IF NEW.status <> 'PLANNING' OR NEW.row_version <> 1 OR NEW.approved_at IS NOT NULL
       OR NEW.cancelled_at IS NOT NULL OR cardinality(NEW.approved_with_flags) <> 0 THEN
        RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_starts_planning';
    END IF;
    PERFORM 1 FROM users WHERE id = NEW.user_id AND is_active AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'mkt_needs_marketing';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.mkt.campaigns.' || NEW.user_id::text, 0));
    IF (SELECT count(*) FROM mkt_campaigns WHERE user_id = NEW.user_id AND status <> 'CANCELLED') >= 50 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_cap';
    END IF;
    IF NEW.starts_on > ew_riyadh_today() + 730 THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_dates_range';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;


ALTER FUNCTION public.ew_mkt_campaign_insert_guard() OWNER TO eyework_owner;

--
-- Name: ew_mkt_campaign_save(uuid, integer, text, text, text, text, bigint, text, bigint, date, date); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_campaign_save(p_campaign uuid, p_expected_row_version integer, p_name text, p_brief text, p_goal text, p_kpi_metric text, p_kpi_target bigint, p_audience text, p_budget_halalas bigint, p_starts_on date, p_ends_on date) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_mkt_require();
    c   mkt_campaigns%ROWTYPE;
    rv  integer;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, p_expected_row_version);
    IF c.status <> 'PLANNING' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
    END IF;
    UPDATE mkt_campaigns
       SET name = p_name, brief = p_brief, goal = p_goal, kpi_metric = p_kpi_metric, kpi_target = p_kpi_target,
           audience = p_audience, budget_halalas = p_budget_halalas, starts_on = p_starts_on, ends_on = p_ends_on
     WHERE id = p_campaign
    RETURNING row_version INTO rv;
    RETURN rv;
END
$$;


ALTER FUNCTION public.ew_mkt_campaign_save(p_campaign uuid, p_expected_row_version integer, p_name text, p_brief text, p_goal text, p_kpi_metric text, p_kpi_target bigint, p_audience text, p_budget_halalas bigint, p_starts_on date, p_ends_on date) OWNER TO eyework_owner;

--
-- Name: ew_mkt_campaign_transition(uuid, integer, text, text[]); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_campaign_transition(p_campaign uuid, p_expected_row_version integer, p_to text, p_acknowledged text[]) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    c    mkt_campaigns%ROWTYPE;
    keys text[];
    rv   integer;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, p_expected_row_version);
    IF p_to = 'APPROVED' AND c.status = 'PLANNING' THEN
        IF c.goal IS NULL OR c.starts_on IS NULL OR c.ends_on IS NULL
           OR NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = c.id) THEN
            RAISE EXCEPTION 'incomplete' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_incomplete';
        END IF;
        keys := ARRAY(SELECT f.flag_key FROM ew_mkt_campaign_flags(c.id) f);
        IF NOT ew_mkt_same_keys(keys, p_acknowledged) THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_flags_changed';
        END IF;
        UPDATE mkt_campaigns SET status = 'APPROVED', approved_with_flags = keys
         WHERE id = c.id RETURNING row_version INTO rv;
    ELSIF p_to = 'PLANNING' AND c.status = 'APPROVED' THEN
        UPDATE mkt_campaigns SET status = 'PLANNING' WHERE id = c.id RETURNING row_version INTO rv;
    ELSIF p_to = 'CANCELLED' AND c.status IN ('PLANNING', 'APPROVED') THEN
        UPDATE mkt_items SET status = 'CANCELLED' WHERE campaign_id = c.id AND status IN ('DRAFT', 'APPROVED');
        UPDATE mkt_campaigns SET status = 'CANCELLED' WHERE id = c.id RETURNING row_version INTO rv;
    ELSE
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_transition';
    END IF;
    RETURN rv;
END
$$;


ALTER FUNCTION public.ew_mkt_campaign_transition(p_campaign uuid, p_expected_row_version integer, p_to text, p_acknowledged text[]) OWNER TO eyework_owner;

--
-- Name: ew_mkt_channel_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_channel_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    st text;
BEGIN
    SELECT status INTO st FROM mkt_campaigns WHERE id = coalesce(NEW.campaign_id, OLD.campaign_id) FOR UPDATE;
    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF st <> 'PLANNING' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.campaign_id <> OLD.campaign_id OR NEW.user_id <> OLD.user_id
                             OR NEW.channel <> OLD.channel) THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_managed';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM mkt_items WHERE campaign_id = OLD.campaign_id AND channel = OLD.channel
                                              AND status <> 'CANCELLED') THEN
            RAISE EXCEPTION 'in use' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_in_use';
        END IF;
        IF EXISTS (SELECT 1 FROM mkt_results WHERE campaign_id = OLD.campaign_id AND channel = OLD.channel) THEN
            RAISE EXCEPTION 'results' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_has_results';
        END IF;
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$;


ALTER FUNCTION public.ew_mkt_channel_guard() OWNER TO eyework_owner;

--
-- Name: ew_mkt_channel_known(text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_channel_known(c text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT c IN ('INSTAGRAM', 'X', 'SNAPCHAT', 'TIKTOK', 'WHATSAPP', 'YOUTUBE', 'GOOGLE_ADS', 'OTHER')
$$;


ALTER FUNCTION public.ew_mkt_channel_known(c text) OWNER TO eyework_owner;

--
-- Name: ew_mkt_item_create(uuid, text, date, time without time zone, text, text[], bigint, uuid); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_item_create(p_campaign uuid, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint, p_source_campaign uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid   uuid := ew_mkt_require();
    title text;
    descr text;
    iid   uuid;
BEGIN
    PERFORM 1 FROM mkt_campaigns WHERE id = p_campaign AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = p_campaign AND channel = p_channel) THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    IF p_source_campaign IS NOT NULL THEN
        SELECT v.title, v.description INTO title, descr
          FROM campaigns a JOIN copy_versions v ON v.id = a.approved_version_id
         WHERE a.id = p_source_campaign AND a.user_id = uid AND a.status = 'READY';
        IF NOT FOUND THEN
            RAISE EXCEPTION 'source' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_source_not_ready';
        END IF;
        IF p_body IS DISTINCT FROM title || E'\n' || descr THEN
            RAISE EXCEPTION 'source' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_source_body';
        END IF;
    END IF;
    INSERT INTO mkt_items (campaign_id, user_id, channel, publish_on, publish_at, body, copy_warnings,
                           planned_spend_halalas, source_campaign_id)
    VALUES (p_campaign, uid, p_channel, p_publish_on, p_publish_at, p_body, coalesce(p_copy_warnings, '{}'),
            p_planned_spend_halalas, p_source_campaign)
    RETURNING id INTO iid;
    RETURN iid;
END
$$;


ALTER FUNCTION public.ew_mkt_item_create(p_campaign uuid, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint, p_source_campaign uuid) OWNER TO eyework_owner;

--
-- Name: ew_mkt_item_flags(uuid); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_item_flags(p_item uuid) RETURNS TABLE(flag_key text, code text, detail jsonb)
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid     uuid := ew_current_user();
    i       mkt_items%ROWTYPE;
    c       mkt_campaigns%ROWTYPE;
    alloc   bigint;
    planned bigint;
BEGIN
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    SELECT * INTO c FROM mkt_campaigns WHERE id = i.campaign_id;

    RETURN QUERY SELECT w, w, '{}'::jsonb FROM unnest(i.copy_warnings) AS w ORDER BY w;

    IF c.starts_on IS NOT NULL AND (i.publish_on < c.starts_on OR i.publish_on > c.ends_on) THEN
        RETURN QUERY SELECT 'ITEM_OUTSIDE_CAMPAIGN'::text, 'ITEM_OUTSIDE_CAMPAIGN'::text,
                            jsonb_build_object('publish_on', i.publish_on, 'starts_on', c.starts_on,
                                               'ends_on', c.ends_on);
    END IF;
    IF i.status = 'DRAFT' AND i.publish_on < ew_riyadh_today() THEN
        RETURN QUERY SELECT 'ITEM_DATE_PASSED'::text, 'ITEM_DATE_PASSED'::text,
                            jsonb_build_object('publish_on', i.publish_on);
    END IF;
    IF i.publish_at IS NOT NULL AND i.status IN ('DRAFT', 'APPROVED') THEN
        RETURN QUERY
            SELECT 'SLOT_CLASH:' || o.id::text, 'SLOT_CLASH'::text,
                   jsonb_build_object('other_item', o.id, 'campaign_name', oc.name, 'channel', o.channel,
                                      'publish_on', o.publish_on, 'publish_at', to_char(o.publish_at, 'HH24:MI'))
              FROM mkt_items o JOIN mkt_campaigns oc ON oc.id = o.campaign_id
             WHERE o.user_id = uid AND o.id <> i.id AND o.channel = i.channel AND o.publish_on = i.publish_on
               AND o.status <> 'CANCELLED' AND o.publish_at IS NOT NULL
               AND abs(extract(epoch FROM (o.publish_at - i.publish_at))) < 3600
             ORDER BY o.publish_at, o.id
             LIMIT 3;
    END IF;
    IF coalesce(i.planned_spend_halalas, 0) > 0 AND i.status IN ('DRAFT', 'APPROVED') THEN
        SELECT allocated_halalas INTO alloc FROM mkt_campaign_channels
         WHERE campaign_id = i.campaign_id AND channel = i.channel;
        SELECT coalesce(sum(planned_spend_halalas), 0) INTO planned FROM mkt_items
         WHERE campaign_id = i.campaign_id AND channel = i.channel AND status <> 'CANCELLED';
        IF planned > alloc THEN
            RETURN QUERY SELECT 'CHANNEL_PLANNED_OVER_ALLOCATION:' || i.channel,
                                'CHANNEL_PLANNED_OVER_ALLOCATION'::text,
                                jsonb_build_object('channel', i.channel, 'planned', planned, 'allocated', alloc);
        END IF;
    END IF;
    RETURN QUERY
        SELECT 'CLAIM_NEEDS_PROOF:' || f.ordinal::text, 'CLAIM_NEEDS_PROOF'::text,
               jsonb_build_object('kind', f.kind, 'quote', f.quote, 'reason', f.reason)
          FROM mkt_ai_flags f
         WHERE f.item_id = i.id AND f.body_digest = i.body_digest
         ORDER BY f.ordinal;
END
$$;


ALTER FUNCTION public.ew_mkt_item_flags(p_item uuid) OWNER TO eyework_owner;

--
-- Name: ew_mkt_item_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_item_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    st text;
    content_changed boolean;
BEGIN
    -- إعلان المنتج حُذف (الكنس أو حذف الحساب): يُفرَغ مرجعه وحده، ولا شيء غيره.
    IF NEW.source_campaign_id IS NULL AND OLD.source_campaign_id IS NOT NULL THEN
        IF ROW(NEW.id, NEW.campaign_id, NEW.user_id, NEW.channel, NEW.status, NEW.row_version, NEW.publish_on,
               NEW.publish_at, NEW.body, NEW.body_digest, NEW.copy_warnings, NEW.planned_spend_halalas,
               NEW.ai_reviewed_digest, NEW.approved_at, NEW.published_at, NEW.cancelled_at, NEW.approved_with_flags,
               NEW.created_at, NEW.updated_at)
           IS DISTINCT FROM ROW(OLD.id, OLD.campaign_id, OLD.user_id, OLD.channel, OLD.status, OLD.row_version,
               OLD.publish_on, OLD.publish_at, OLD.body, OLD.body_digest, OLD.copy_warnings, OLD.planned_spend_halalas,
               OLD.ai_reviewed_digest, OLD.approved_at, OLD.published_at, OLD.cancelled_at, OLD.approved_with_flags,
               OLD.created_at, OLD.updated_at) THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_managed_columns';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('PUBLISHED', 'CANCELLED') THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_final';
    END IF;
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.campaign_id <> OLD.campaign_id
       OR NEW.created_at <> OLD.created_at OR NEW.row_version <> OLD.row_version
       OR NEW.source_campaign_id IS DISTINCT FROM OLD.source_campaign_id
       OR NEW.body_digest <> OLD.body_digest THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_managed_columns';
    END IF;
    content_changed := ROW(NEW.channel, NEW.publish_on, NEW.publish_at, NEW.body, NEW.planned_spend_halalas,
                           NEW.copy_warnings)
                       IS DISTINCT FROM ROW(OLD.channel, OLD.publish_on, OLD.publish_at, OLD.body,
                                            OLD.planned_spend_halalas, OLD.copy_warnings);

    -- اكتمال المراجعة وحده: لا يغيّر المحتوى ولا رقم الصفّ، ولا يكون إلا للنصّ الحالي.
    IF NOT content_changed AND NEW.status = OLD.status
       AND NEW.ai_reviewed_digest IS DISTINCT FROM OLD.ai_reviewed_digest THEN
        IF NEW.ai_reviewed_digest IS DISTINCT FROM OLD.body_digest OR OLD.status <> 'DRAFT'
           OR ROW(NEW.approved_at, NEW.published_at, NEW.cancelled_at, NEW.approved_with_flags, NEW.updated_at)
              IS DISTINCT FROM ROW(OLD.approved_at, OLD.published_at, OLD.cancelled_at, OLD.approved_with_flags,
                                   OLD.updated_at) THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_managed_columns';
        END IF;
        RETURN NEW;
    END IF;

    IF content_changed AND NOT (OLD.status = 'DRAFT' AND NEW.status = 'DRAFT') THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_fixed';
    END IF;
    IF NEW.status <> OLD.status AND NOT EXISTS (
           SELECT 1 FROM mkt_item_transition WHERE from_status = OLD.status AND to_status = NEW.status) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_transition';
    END IF;
    -- لا محتوى يُعتمد ولا يُنشر وخطّته في التخطيط. FOR SHARE يقف أمام إعادة الخطة إلى التخطيط.
    IF NEW.status IN ('APPROVED', 'PUBLISHED') AND NEW.status <> OLD.status THEN
        SELECT status INTO st FROM mkt_campaigns WHERE id = NEW.campaign_id FOR SHARE;
        IF st IS DISTINCT FROM 'APPROVED' THEN
            RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_not_approved';
        END IF;
    END IF;
    IF NEW.status = 'PUBLISHED' AND OLD.status <> 'PUBLISHED' THEN
        IF NEW.published_at IS NULL OR NEW.published_at > now() OR NEW.published_at < now() - interval '30 days' THEN
            RAISE EXCEPTION 'published' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_published_at_range';
        END IF;
    ELSE
        NEW.published_at := OLD.published_at;
    END IF;
    IF content_changed THEN
        IF NEW.publish_on IS DISTINCT FROM OLD.publish_on AND NEW.publish_on > ew_riyadh_today() + 730 THEN
            RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_date_range';
        END IF;
        NEW.body_digest := sha256(convert_to(NEW.channel || E'\n' || NEW.body, 'UTF8'));
        IF NEW.body_digest <> OLD.body_digest THEN
            DELETE FROM mkt_ai_flags WHERE item_id = NEW.id;
            NEW.ai_reviewed_digest := NULL;
        ELSE
            NEW.ai_reviewed_digest := OLD.ai_reviewed_digest;
        END IF;
    ELSE
        NEW.ai_reviewed_digest := OLD.ai_reviewed_digest;
    END IF;

    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.approved_at := CASE WHEN NEW.status IN ('APPROVED', 'PUBLISHED')
                            THEN coalesce(OLD.approved_at, now()) END;
    NEW.approved_with_flags := CASE
        WHEN NEW.status IN ('APPROVED', 'PUBLISHED') AND OLD.status IN ('APPROVED', 'PUBLISHED')
            THEN OLD.approved_with_flags
        WHEN NEW.status = 'APPROVED' THEN NEW.approved_with_flags
        ELSE '{}'::text[] END;
    NEW.cancelled_at := CASE WHEN NEW.status = 'CANCELLED' THEN now() END;
    RETURN NEW;
END
$$;


ALTER FUNCTION public.ew_mkt_item_guard() OWNER TO eyework_owner;

--
-- Name: ew_mkt_item_insert_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_item_insert_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    st text;
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.approved_at IS NOT NULL OR NEW.published_at IS NOT NULL
       OR NEW.cancelled_at IS NOT NULL OR cardinality(NEW.approved_with_flags) <> 0
       OR NEW.ai_reviewed_digest IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_starts_draft';
    END IF;
    SELECT status INTO st FROM mkt_campaigns WHERE id = NEW.campaign_id FOR UPDATE;
    IF st IS NULL OR st = 'CANCELLED' THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_is_final';
    END IF;
    IF (SELECT count(*) FROM mkt_items WHERE campaign_id = NEW.campaign_id) >= 300 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_cap';
    END IF;
    IF NEW.publish_on > ew_riyadh_today() + 730 THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_date_range';
    END IF;
    NEW.body_digest := sha256(convert_to(NEW.channel || E'\n' || NEW.body, 'UTF8'));
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;


ALTER FUNCTION public.ew_mkt_item_insert_guard() OWNER TO eyework_owner;

--
-- Name: ew_mkt_item_save(uuid, integer, text, date, time without time zone, text, text[], bigint); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_item_save(p_item uuid, p_expected_row_version integer, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_mkt_require();
    i   mkt_items%ROWTYPE;
    rv  integer;
BEGIN
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    -- الحملة أولاً ثم المنشور، بالترتيب نفسه في كل دالّة: لا قفل متقاطع.
    PERFORM 1 FROM mkt_campaigns WHERE id = i.campaign_id FOR SHARE;
    SELECT * INTO i FROM mkt_items WHERE id = p_item FOR UPDATE;
    IF i.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
    END IF;
    IF i.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_fixed';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = i.campaign_id AND channel = p_channel) THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    UPDATE mkt_items
       SET channel = p_channel, publish_on = p_publish_on, publish_at = p_publish_at, body = p_body,
           copy_warnings = coalesce(p_copy_warnings, '{}'), planned_spend_halalas = p_planned_spend_halalas
     WHERE id = p_item
    RETURNING row_version INTO rv;
    RETURN rv;
END
$$;


ALTER FUNCTION public.ew_mkt_item_save(p_item uuid, p_expected_row_version integer, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint) OWNER TO eyework_owner;

--
-- Name: ew_mkt_item_transition(uuid, integer, text, text[], timestamp with time zone); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_item_transition(p_item uuid, p_expected_row_version integer, p_to text, p_acknowledged text[], p_published_at timestamp with time zone) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    i    mkt_items%ROWTYPE;
    keys text[];
    rv   integer;
BEGIN
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    PERFORM 1 FROM mkt_campaigns WHERE id = i.campaign_id FOR SHARE;
    SELECT * INTO i FROM mkt_items WHERE id = p_item FOR UPDATE;
    IF i.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
    END IF;
    IF p_to = 'APPROVED' AND i.status = 'DRAFT' THEN
        keys := ARRAY(SELECT f.flag_key FROM ew_mkt_item_flags(p_item) f);
        IF NOT ew_mkt_same_keys(keys, p_acknowledged) THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_flags_changed';
        END IF;
        UPDATE mkt_items SET status = 'APPROVED', approved_with_flags = keys
         WHERE id = p_item RETURNING row_version INTO rv;
    ELSIF p_to = 'DRAFT' AND i.status = 'APPROVED' THEN
        UPDATE mkt_items SET status = 'DRAFT' WHERE id = p_item RETURNING row_version INTO rv;
    ELSIF p_to = 'PUBLISHED' AND i.status = 'APPROVED' THEN
        UPDATE mkt_items SET status = 'PUBLISHED', published_at = coalesce(p_published_at, now())
         WHERE id = p_item RETURNING row_version INTO rv;
    ELSIF p_to = 'CANCELLED' AND i.status IN ('DRAFT', 'APPROVED') THEN
        UPDATE mkt_items SET status = 'CANCELLED' WHERE id = p_item RETURNING row_version INTO rv;
    ELSE
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_transition';
    END IF;
    RETURN rv;
END
$$;


ALTER FUNCTION public.ew_mkt_item_transition(p_item uuid, p_expected_row_version integer, p_to text, p_acknowledged text[], p_published_at timestamp with time zone) OWNER TO eyework_owner;

--
-- Name: ew_mkt_kpi_fits(text, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_kpi_fits(p_goal text, p_kpi text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT CASE p_goal
        WHEN 'AWARENESS' THEN p_kpi = 'IMPRESSIONS'
        WHEN 'TRAFFIC'   THEN p_kpi = 'CLICKS'
        WHEN 'LEADS'     THEN p_kpi IN ('LEADS', 'COST_PER_LEAD')
        WHEN 'SALES'     THEN p_kpi IN ('ORDERS', 'REVENUE', 'COST_PER_ORDER')
        ELSE false
    END
$$;


ALTER FUNCTION public.ew_mkt_kpi_fits(p_goal text, p_kpi text) OWNER TO eyework_owner;

--
-- Name: ew_mkt_text_ok(text, boolean); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_text_ok(t text, p_multiline boolean) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT t = btrim(t, E' \n')
       AND t !~ '[\x01-\x09\x0B-\x1F\x7F-\x9F]'
       AND (p_multiline OR strpos(t, E'\n') = 0)
       AND t !~ '[‎‏‪-‮⁦-⁩]'
       AND t IS NFC NORMALIZED
$$;


ALTER FUNCTION public.ew_mkt_text_ok(t text, p_multiline boolean) OWNER TO eyework_owner;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: mkt_campaigns; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_campaigns (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    status text DEFAULT 'PLANNING'::text NOT NULL,
    row_version integer DEFAULT 1 NOT NULL,
    name text NOT NULL,
    brief text,
    goal text,
    kpi_metric text,
    kpi_target bigint,
    audience text,
    budget_halalas bigint DEFAULT 0 NOT NULL,
    starts_on date,
    ends_on date,
    approved_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    approved_with_flags text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT mkt_approved_complete CHECK (((status <> 'APPROVED'::text) OR ((goal IS NOT NULL) AND (starts_on IS NOT NULL) AND (ends_on IS NOT NULL)))),
    CONSTRAINT mkt_approved_iff_time CHECK (((status = 'APPROVED'::text) = (approved_at IS NOT NULL))),
    CONSTRAINT mkt_budget_range CHECK (((budget_halalas >= 0) AND (budget_halalas <= '10000000000'::bigint))),
    CONSTRAINT mkt_campaign_audience CHECK (((audience IS NULL) OR (((char_length(audience) >= 1) AND (char_length(audience) <= 200)) AND public.ew_mkt_text_ok(audience, false)))),
    CONSTRAINT mkt_campaign_brief CHECK (((brief IS NULL) OR (((char_length(brief) >= 1) AND (char_length(brief) <= 500)) AND public.ew_mkt_text_ok(brief, true)))),
    CONSTRAINT mkt_campaign_goal CHECK (((goal IS NULL) OR (goal = ANY (ARRAY['AWARENESS'::text, 'TRAFFIC'::text, 'LEADS'::text, 'SALES'::text])))),
    CONSTRAINT mkt_campaign_name CHECK ((((char_length(name) >= 2) AND (char_length(name) <= 60)) AND public.ew_mkt_text_ok(name, false))),
    CONSTRAINT mkt_campaign_status CHECK ((status = ANY (ARRAY['PLANNING'::text, 'APPROVED'::text, 'CANCELLED'::text]))),
    CONSTRAINT mkt_cancelled_iff_time CHECK (((status = 'CANCELLED'::text) = (cancelled_at IS NOT NULL))),
    CONSTRAINT mkt_dates_floor CHECK (((starts_on IS NULL) OR (starts_on >= '2020-01-01'::date))),
    CONSTRAINT mkt_dates_order CHECK (((starts_on IS NULL) OR (ends_on IS NULL) OR (ends_on >= starts_on))),
    CONSTRAINT mkt_dates_span CHECK (((starts_on IS NULL) OR (ends_on IS NULL) OR ((ends_on - starts_on) <= 365))),
    CONSTRAINT mkt_kpi_complete CHECK (((kpi_metric IS NULL) = (kpi_target IS NULL))),
    CONSTRAINT mkt_kpi_fits_goal CHECK (((kpi_metric IS NULL) OR public.ew_mkt_kpi_fits(goal, kpi_metric))),
    CONSTRAINT mkt_kpi_target_range CHECK (((kpi_target IS NULL) OR ((kpi_target >= 1) AND (kpi_target <= '1000000000000'::bigint))))
);

ALTER TABLE ONLY public.mkt_campaigns FORCE ROW LEVEL SECURITY;


ALTER TABLE public.mkt_campaigns OWNER TO eyework_owner;

--
-- Name: ew_mkt_lock_campaign(uuid, uuid, integer); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_lock_campaign(p_uid uuid, p_campaign uuid, p_expected_row_version integer) RETURNS public.mkt_campaigns
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    c mkt_campaigns%ROWTYPE;
BEGIN
    SELECT * INTO c FROM mkt_campaigns WHERE id = p_campaign AND user_id = p_uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF p_expected_row_version IS NOT NULL AND c.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
    END IF;
    RETURN c;
END
$$;


ALTER FUNCTION public.ew_mkt_lock_campaign(p_uid uuid, p_campaign uuid, p_expected_row_version integer) OWNER TO eyework_owner;

--
-- Name: ew_mkt_require(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_require() RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'mkt_needs_marketing';
    END IF;
    RETURN uid;
END
$$;


ALTER FUNCTION public.ew_mkt_require() OWNER TO eyework_owner;

--
-- Name: ew_mkt_results_flags(uuid, text, uuid, bigint); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_results_flags(p_campaign uuid, p_channel text, p_result uuid, p_spend bigint) RETURNS TABLE(flag_key text, code text, detail jsonb)
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid        uuid := ew_current_user();
    c          mkt_campaigns%ROWTYPE;
    alloc      bigint;
    spent_ch   bigint;
    spent_all  bigint;
BEGIN
    SELECT * INTO c FROM mkt_campaigns WHERE id = p_campaign AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF coalesce(p_spend, 0) = 0 THEN
        RETURN;
    END IF;
    SELECT allocated_halalas INTO alloc FROM mkt_campaign_channels WHERE campaign_id = c.id AND channel = p_channel;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    SELECT coalesce(sum(spend_halalas), 0) INTO spent_ch FROM mkt_results
     WHERE campaign_id = c.id AND channel = p_channel AND id IS DISTINCT FROM p_result;
    SELECT coalesce(sum(spend_halalas), 0) INTO spent_all FROM mkt_results
     WHERE campaign_id = c.id AND id IS DISTINCT FROM p_result;
    spent_ch := spent_ch + p_spend;
    spent_all := spent_all + p_spend;
    IF spent_ch > alloc THEN
        RETURN QUERY SELECT 'CHANNEL_SPEND_OVER_ALLOCATION:' || p_channel, 'CHANNEL_SPEND_OVER_ALLOCATION'::text,
                            jsonb_build_object('channel', p_channel, 'spent', spent_ch, 'allocated', alloc,
                                               'entry', p_spend);
    END IF;
    IF spent_all > c.budget_halalas THEN
        RETURN QUERY SELECT 'TOTAL_SPEND_OVER_BUDGET'::text, 'TOTAL_SPEND_OVER_BUDGET'::text,
                            jsonb_build_object('spent', spent_all, 'budget', c.budget_halalas, 'entry', p_spend);
    END IF;
END
$$;


ALTER FUNCTION public.ew_mkt_results_flags(p_campaign uuid, p_channel text, p_result uuid, p_spend bigint) OWNER TO eyework_owner;

--
-- Name: ew_mkt_results_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_results_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    c mkt_campaigns%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.campaign_id <> OLD.campaign_id
                             OR NEW.channel <> OLD.channel OR NEW.created_at <> OLD.created_at
                             OR NEW.row_version <> OLD.row_version) THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_managed';
    END IF;
    SELECT * INTO c FROM mkt_campaigns WHERE id = NEW.campaign_id FOR UPDATE;
    IF c.status IS DISTINCT FROM 'APPROVED' THEN
        RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_need_approved_plan';
    END IF;
    IF NEW.period_start < c.starts_on OR NEW.period_end > c.ends_on THEN
        RAISE EXCEPTION 'outside' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_outside_campaign';
    END IF;
    IF NEW.period_end > ew_riyadh_today() THEN
        RAISE EXCEPTION 'future' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_in_future';
    END IF;
    IF EXISTS (SELECT 1 FROM mkt_results r
                WHERE r.campaign_id = NEW.campaign_id AND r.channel = NEW.channel AND r.id <> NEW.id
                  AND r.period_start <= NEW.period_end AND r.period_end >= NEW.period_start) THEN
        RAISE EXCEPTION 'overlap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_overlap';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.row_version <> 1 THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_managed';
        END IF;
        IF (SELECT count(*) FROM mkt_results WHERE campaign_id = NEW.campaign_id) >= 1000 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_cap';
        END IF;
        NEW.created_at := now();
    ELSE
        NEW.row_version := OLD.row_version + 1;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;


ALTER FUNCTION public.ew_mkt_results_guard() OWNER TO eyework_owner;

--
-- Name: ew_mkt_results_save(uuid, text, uuid, integer, date, date, bigint, bigint, bigint, bigint, bigint, bigint, text[]); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_results_save(p_campaign uuid, p_channel text, p_result uuid, p_expected_row_version integer, p_period_start date, p_period_end date, p_spend_halalas bigint, p_impressions bigint, p_clicks bigint, p_leads bigint, p_orders bigint, p_revenue_halalas bigint, p_acknowledged text[]) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    c    mkt_campaigns%ROWTYPE;
    r    mkt_results%ROWTYPE;
    keys text[];
    rid  uuid;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, NULL);
    IF c.status <> 'APPROVED' THEN
        RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_need_approved_plan';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = c.id AND channel = p_channel) THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    IF p_result IS NOT NULL THEN
        SELECT * INTO r FROM mkt_results WHERE id = p_result AND campaign_id = c.id AND user_id = uid FOR UPDATE;
        IF NOT FOUND OR r.channel <> p_channel THEN
            RAISE EXCEPTION 'result' USING ERRCODE = 'no_data_found';
        END IF;
        IF r.row_version <> p_expected_row_version THEN
            RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
        END IF;
    END IF;
    keys := ARRAY(SELECT f.flag_key FROM ew_mkt_results_flags(c.id, p_channel, p_result, p_spend_halalas) f);
    IF NOT ew_mkt_same_keys(keys, p_acknowledged) THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_flags_changed';
    END IF;
    IF p_result IS NULL THEN
        INSERT INTO mkt_results (campaign_id, user_id, channel, period_start, period_end, spend_halalas, impressions,
                                 clicks, leads, orders, revenue_halalas, acknowledged_flags)
        VALUES (c.id, uid, p_channel, p_period_start, p_period_end, p_spend_halalas, p_impressions, p_clicks,
                p_leads, p_orders, p_revenue_halalas, keys)
        RETURNING id INTO rid;
    ELSE
        UPDATE mkt_results
           SET period_start = p_period_start, period_end = p_period_end, spend_halalas = p_spend_halalas,
               impressions = p_impressions, clicks = p_clicks, leads = p_leads, orders = p_orders,
               revenue_halalas = p_revenue_halalas, acknowledged_flags = keys
         WHERE id = p_result
        RETURNING id INTO rid;
    END IF;
    RETURN rid;
END
$$;


ALTER FUNCTION public.ew_mkt_results_save(p_campaign uuid, p_channel text, p_result uuid, p_expected_row_version integer, p_period_start date, p_period_end date, p_spend_halalas bigint, p_impressions bigint, p_clicks bigint, p_leads bigint, p_orders bigint, p_revenue_halalas bigint, p_acknowledged text[]) OWNER TO eyework_owner;

--
-- Name: ew_mkt_review_begin(uuid); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_review_begin(p_item uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid   uuid := ew_mkt_require();
    i     mkt_items%ROWTYPE;
    fresh boolean;
    call  uuid;
BEGIN
    -- قفلٌ لكل مستخدم: الفحص والإدراج ذرّيان، وطلبان متزامنان لا يمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.mkt.review.' || uid::text, 0));
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    IF i.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_fixed';
    END IF;
    IF i.ai_reviewed_digest = i.body_digest THEN
        RETURN NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM mkt_review_calls
                WHERE user_id = uid AND finished_at IS NULL AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_in_progress';
    END IF;
    IF (SELECT count(*) FROM mkt_review_calls
         WHERE user_id = uid AND started_at > now() - interval '10 minutes') >= 6 THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_rate';
    END IF;
    fresh := ew_new_open_account(uid);
    IF (SELECT count(*) FROM mkt_review_calls
         WHERE user_id = uid AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       >= (CASE WHEN fresh THEN 10 ELSE 30 END) THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation',
            CONSTRAINT = CASE WHEN fresh THEN 'mkt_review_new_account_cap' ELSE 'mkt_review_daily_cap' END;
    END IF;
    -- القفل العام نفسه الذي يأخذه ew_begin_generation: السقف واحدٌ للأدوات كلها.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM mkt_review_calls
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 600 THEN
        RAISE EXCEPTION 'app' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_app_cap';
    END IF;
    IF ew_ai_spend(false) >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF fresh AND ew_ai_spend(true) >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    INSERT INTO mkt_review_calls (user_id, item_id, body_digest, new_account)
    VALUES (uid, i.id, i.body_digest, fresh)
    RETURNING id INTO call;
    RETURN call;
END
$$;


ALTER FUNCTION public.ew_mkt_review_begin(p_item uuid) OWNER TO eyework_owner;

--
-- Name: ew_mkt_review_finish(uuid, text, integer, integer, text, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_review_finish(p_call uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer, p_served_model text, p_request_id text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    IF p_outcome IS NULL OR p_outcome NOT IN ('REFUSED', 'OUTPUT_INVALID', 'UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE',
                                              'UPSTREAM_TIMEOUT', 'UPSTREAM_ERROR') THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_outcome';
    END IF;
    UPDATE mkt_review_calls
       SET finished_at = now(), outcome = p_outcome, input_tokens = p_input_tokens, output_tokens = p_output_tokens,
           served_model = p_served_model, api_request_id = p_request_id
     WHERE id = p_call AND user_id = uid AND finished_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'no_data_found';
    END IF;
END
$$;


ALTER FUNCTION public.ew_mkt_review_finish(p_call uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer, p_served_model text, p_request_id text) OWNER TO eyework_owner;

--
-- Name: ew_mkt_review_record(uuid, text[], text[], text[], integer, integer, text, text, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_review_record(p_call uuid, p_kinds text[], p_quotes text[], p_reasons text[], p_input_tokens integer, p_output_tokens integer, p_served_model text, p_prompt_version text, p_request_id text) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    call mkt_review_calls%ROWTYPE;
    i    mkt_items%ROWTYPE;
BEGIN
    SELECT * INTO call FROM mkt_review_calls WHERE id = p_call AND user_id = uid AND finished_at IS NULL FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'no_data_found';
    END IF;
    IF p_kinds IS NULL OR p_quotes IS NULL OR p_reasons IS NULL
       OR cardinality(p_kinds) <> cardinality(p_quotes) OR cardinality(p_kinds) <> cardinality(p_reasons)
       OR cardinality(p_kinds) > 5 THEN
        RAISE EXCEPTION 'shape' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_shape';
    END IF;
    SELECT * INTO i FROM mkt_items WHERE id = call.item_id AND user_id = uid FOR UPDATE;
    IF NOT FOUND OR i.status <> 'DRAFT' OR i.body_digest <> call.body_digest THEN
        UPDATE mkt_review_calls
           SET finished_at = now(), outcome = 'DISCARDED', input_tokens = p_input_tokens,
               output_tokens = p_output_tokens, served_model = p_served_model, prompt_version = p_prompt_version,
               api_request_id = p_request_id
         WHERE id = p_call;
        RETURN false;
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(p_quotes) q WHERE q IS NULL OR strpos(i.body, q) = 0) THEN
        RAISE EXCEPTION 'quote' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_quote';
    END IF;
    DELETE FROM mkt_ai_flags WHERE item_id = i.id;
    INSERT INTO mkt_ai_flags (item_id, user_id, body_digest, ordinal, kind, quote, reason)
    SELECT i.id, uid, i.body_digest, t.n, t.k, t.q, t.r
      FROM unnest(p_kinds, p_quotes, p_reasons) WITH ORDINALITY AS t(k, q, r, n);
    UPDATE mkt_items SET ai_reviewed_digest = body_digest WHERE id = i.id;
    UPDATE mkt_review_calls
       SET finished_at = now(), outcome = 'OK', input_tokens = p_input_tokens, output_tokens = p_output_tokens,
           served_model = p_served_model, prompt_version = p_prompt_version, api_request_id = p_request_id
     WHERE id = p_call;
    RETURN true;
END
$$;


ALTER FUNCTION public.ew_mkt_review_record(p_call uuid, p_kinds text[], p_quotes text[], p_reasons text[], p_input_tokens integer, p_output_tokens integer, p_served_model text, p_prompt_version text, p_request_id text) OWNER TO eyework_owner;

--
-- Name: ew_mkt_review_tombstone(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_review_tombstone() RETURNS trigger
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


ALTER FUNCTION public.ew_mkt_review_tombstone() OWNER TO eyework_owner;

--
-- Name: ew_mkt_same_keys(text[], text[]); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_same_keys(a text[], b text[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT ARRAY(SELECT DISTINCT x FROM unnest(coalesce(a, '{}')) x ORDER BY x)
         = ARRAY(SELECT DISTINCT x FROM unnest(coalesce(b, '{}')) x ORDER BY x)
$$;


ALTER FUNCTION public.ew_mkt_same_keys(a text[], b text[]) OWNER TO eyework_owner;

--
-- Name: ew_mkt_set_channels(uuid, integer, text[], bigint[]); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_mkt_set_channels(p_campaign uuid, p_expected_row_version integer, p_channels text[], p_allocations bigint[]) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid uuid := ew_mkt_require();
    c   mkt_campaigns%ROWTYPE;
    rv  integer;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, p_expected_row_version);
    IF c.status <> 'PLANNING' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
    END IF;
    IF p_channels IS NULL OR p_allocations IS NULL
       OR cardinality(p_channels) <> cardinality(p_allocations)
       OR cardinality(p_channels) NOT BETWEEN 1 AND 8
       OR (SELECT count(DISTINCT x) FROM unnest(p_channels) x) <> cardinality(p_channels)
       OR array_position(p_channels, NULL) IS NOT NULL OR array_position(p_allocations, NULL) IS NOT NULL THEN
        RAISE EXCEPTION 'shape' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channels_shape';
    END IF;
    IF (SELECT sum(a) FROM unnest(p_allocations) a) > c.budget_halalas THEN
        RAISE EXCEPTION 'budget' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_allocations_over_budget';
    END IF;
    DELETE FROM mkt_campaign_channels WHERE campaign_id = p_campaign AND NOT (channel = ANY (p_channels));
    INSERT INTO mkt_campaign_channels (campaign_id, user_id, channel, allocated_halalas)
    SELECT p_campaign, uid, t.ch, t.al FROM unnest(p_channels, p_allocations) AS t(ch, al)
    ON CONFLICT (campaign_id, channel) DO UPDATE SET allocated_halalas = EXCLUDED.allocated_halalas
     WHERE mkt_campaign_channels.allocated_halalas IS DISTINCT FROM EXCLUDED.allocated_halalas;
    UPDATE mkt_campaigns SET updated_at = now() WHERE id = p_campaign RETURNING row_version INTO rv;
    RETURN rv;
END
$$;


ALTER FUNCTION public.ew_mkt_set_channels(p_campaign uuid, p_expected_row_version integer, p_channels text[], p_allocations bigint[]) OWNER TO eyework_owner;

--
-- Name: ew_my_display_name(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_my_display_name() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT display_name FROM users WHERE id = ew_current_user() AND is_active
$$;


ALTER FUNCTION public.ew_my_display_name() OWNER TO eyework_owner;

--
-- Name: ew_my_generation_limit(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_my_generation_limit() RETURNS integer
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT CASE WHEN ew_new_open_account(id) THEN 10 ELSE 40 END
      FROM users WHERE id = ew_current_user() AND is_active
$$;


ALTER FUNCTION public.ew_my_generation_limit() OWNER TO eyework_owner;

--
-- Name: ew_my_passkeys(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_my_passkeys() RETURNS TABLE(credential_id bytea, transports text[])
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT p.credential_id, p.transports FROM passkeys p
     WHERE p.user_id = ew_current_user()
     ORDER BY p.created_at, p.id
$$;


ALTER FUNCTION public.ew_my_passkeys() OWNER TO eyework_owner;

--
-- Name: ew_my_profession(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_my_profession() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT profession FROM users WHERE id = ew_current_user() AND is_active
$$;


ALTER FUNCTION public.ew_my_profession() OWNER TO eyework_owner;

--
-- Name: ew_my_terms_version(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_my_terms_version() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT terms_version FROM users WHERE id = ew_current_user() AND is_active
$$;


ALTER FUNCTION public.ew_my_terms_version() OWNER TO eyework_owner;

--
-- Name: ew_my_ui_size(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_my_ui_size() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT ui_size FROM users WHERE id = ew_current_user() AND is_active
$$;


ALTER FUNCTION public.ew_my_ui_size() OWNER TO eyework_owner;

--
-- Name: ew_new_open_account(uuid); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_new_open_account(p_user uuid) RETURNS boolean
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT coalesce((SELECT open_registered AND created_at > now() - interval '7 days'
                       FROM users WHERE id = p_user), false)
$$;


ALTER FUNCTION public.ew_new_open_account(p_user uuid) OWNER TO eyework_owner;

--
-- Name: ew_open_registration_blocker(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_open_registration_blocker() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT ew_registration_blocker('OPEN')
$$;


ALTER FUNCTION public.ew_open_registration_blocker() OWNER TO eyework_owner;

--
-- Name: ew_open_session(uuid, bytea); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_passkey_add(bytea, bytea, bigint, text[]); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_passkey_challenge(bytea, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_passkey_lookup(bytea); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_passkey_lookup(p_credential bytea) RETURNS TABLE(user_id uuid, public_key bytea, sign_count bigint)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT p.user_id, p.public_key, p.sign_count
      FROM passkeys p JOIN users u ON u.id = p.user_id
     WHERE p.credential_id = p_credential AND u.is_active AND u.activated_at IS NOT NULL
$$;


ALTER FUNCTION public.ew_passkey_lookup(p_credential bytea) OWNER TO eyework_owner;

--
-- Name: ew_passkey_signed_in(bytea, bigint); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_passkey_take_challenge(bytea, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_purge_image_on_cancel(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_register(bytea, bytea, text, text, date, text, text, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_register_open(bytea, text, text, date, text, text, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_registration_blocker(text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_resolve_session(bytea); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_resolve_session(p_token bytea) RETURNS uuid
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT s.user_id FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.token_hash = p_token AND s.revoked_at IS NULL AND s.expires_at > now()
       AND u.is_active
$$;


ALTER FUNCTION public.ew_resolve_session(p_token bytea) OWNER TO eyework_owner;

--
-- Name: ew_revoke_session(bytea); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_revoke_session(p_token bytea) RETURNS void
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    UPDATE sessions SET revoked_at = now() WHERE token_hash = p_token AND revoked_at IS NULL
$$;


ALTER FUNCTION public.ew_revoke_session(p_token bytea) OWNER TO eyework_owner;

--
-- Name: ew_riyadh_today(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_riyadh_today() RETURNS date
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT (now() AT TIME ZONE 'Asia/Riyadh')::date
$$;


ALTER FUNCTION public.ew_riyadh_today() OWNER TO eyework_owner;

--
-- Name: ew_set_my_ui_size(text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_signup_code_usable(bytea); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_signup_code_usable(p_code bytea) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT EXISTS (SELECT 1 FROM signup_codes
                    WHERE code_hash = p_code AND used_at IS NULL AND expires_at > now() AND taken_count < 3)
$$;


ALTER FUNCTION public.ew_signup_code_usable(p_code bytea) OWNER TO eyework_owner;

--
-- Name: ew_version_becomes_current(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: ew_version_insert_guard(); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

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

--
-- Name: activation_tokens; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: attempt_tombstones; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.attempt_tombstones (
    started_at timestamp with time zone NOT NULL,
    outcome text,
    new_account boolean DEFAULT false NOT NULL
);

ALTER TABLE ONLY public.attempt_tombstones FORCE ROW LEVEL SECURITY;


ALTER TABLE public.attempt_tombstones OWNER TO eyework_owner;

--
-- Name: campaign_images; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: campaign_transition; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.campaign_transition (
    from_status text NOT NULL,
    to_status text NOT NULL
);


ALTER TABLE public.campaign_transition OWNER TO eyework_owner;

--
-- Name: campaigns; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: copy_versions; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: generation_attempts; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: mkt_ai_flags; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_ai_flags (
    item_id uuid NOT NULL,
    user_id uuid NOT NULL,
    body_digest bytea NOT NULL,
    ordinal smallint NOT NULL,
    kind text NOT NULL,
    quote text NOT NULL,
    reason text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT mkt_ai_flag_kind CHECK ((kind = ANY (ARRAY['COMPARATIVE'::text, 'ABSOLUTE'::text, 'HEALTH'::text, 'CERTIFICATION'::text, 'PRICE_OFFER'::text, 'ORIGIN_NATURE'::text, 'RESULT'::text, 'ENDORSEMENT'::text]))),
    CONSTRAINT mkt_ai_flag_ordinal CHECK (((ordinal >= 1) AND (ordinal <= 5))),
    CONSTRAINT mkt_ai_flag_quote CHECK ((((char_length(quote) >= 2) AND (char_length(quote) <= 120)) AND public.ew_mkt_text_ok(quote, false))),
    CONSTRAINT mkt_ai_flag_reason CHECK ((((char_length(reason) >= 1) AND (char_length(reason) <= 160)) AND public.ew_mkt_text_ok(reason, false))),
    CONSTRAINT mkt_ai_flags_body_digest_check CHECK ((octet_length(body_digest) = 32))
);

ALTER TABLE ONLY public.mkt_ai_flags FORCE ROW LEVEL SECURITY;


ALTER TABLE public.mkt_ai_flags OWNER TO eyework_owner;

--
-- Name: mkt_campaign_channels; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_campaign_channels (
    campaign_id uuid NOT NULL,
    user_id uuid NOT NULL,
    channel text NOT NULL,
    allocated_halalas bigint DEFAULT 0 NOT NULL,
    CONSTRAINT mkt_allocation_range CHECK (((allocated_halalas >= 0) AND (allocated_halalas <= '10000000000'::bigint))),
    CONSTRAINT mkt_channel_known CHECK (public.ew_mkt_channel_known(channel))
);

ALTER TABLE ONLY public.mkt_campaign_channels FORCE ROW LEVEL SECURITY;


ALTER TABLE public.mkt_campaign_channels OWNER TO eyework_owner;

--
-- Name: mkt_campaign_transition; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_campaign_transition (
    from_status text NOT NULL,
    to_status text NOT NULL
);


ALTER TABLE public.mkt_campaign_transition OWNER TO eyework_owner;

--
-- Name: mkt_item_transition; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_item_transition (
    from_status text NOT NULL,
    to_status text NOT NULL
);


ALTER TABLE public.mkt_item_transition OWNER TO eyework_owner;

--
-- Name: mkt_items; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    campaign_id uuid NOT NULL,
    user_id uuid NOT NULL,
    channel text NOT NULL,
    status text DEFAULT 'DRAFT'::text NOT NULL,
    row_version integer DEFAULT 1 NOT NULL,
    publish_on date NOT NULL,
    publish_at time(0) without time zone,
    body text NOT NULL,
    body_digest bytea DEFAULT '\x'::bytea NOT NULL,
    copy_warnings text[] DEFAULT '{}'::text[] NOT NULL,
    planned_spend_halalas bigint,
    source_campaign_id uuid,
    ai_reviewed_digest bytea,
    approved_at timestamp with time zone,
    published_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    approved_with_flags text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT mkt_item_approved_iff_time CHECK (((status = ANY (ARRAY['APPROVED'::text, 'PUBLISHED'::text])) = (approved_at IS NOT NULL))),
    CONSTRAINT mkt_item_body CHECK ((((char_length(body) >= 1) AND (char_length(body) <= 2000)) AND public.ew_mkt_text_ok(body, true))),
    CONSTRAINT mkt_item_cancelled_iff_time CHECK (((status = 'CANCELLED'::text) = (cancelled_at IS NOT NULL))),
    CONSTRAINT mkt_item_copy_warnings CHECK (((copy_warnings <@ ARRAY['PRICE'::text, 'HEALTH_CLAIM'::text, 'SUPERLATIVE'::text, 'TOO_LONG_FOR_X'::text]) AND (cardinality(copy_warnings) <= 4))),
    CONSTRAINT mkt_item_date_floor CHECK ((publish_on >= '2020-01-01'::date)),
    CONSTRAINT mkt_item_digest CHECK ((octet_length(body_digest) = 32)),
    CONSTRAINT mkt_item_published_iff_time CHECK (((status = 'PUBLISHED'::text) = (published_at IS NOT NULL))),
    CONSTRAINT mkt_item_spend_range CHECK (((planned_spend_halalas IS NULL) OR ((planned_spend_halalas >= 0) AND (planned_spend_halalas <= '10000000000'::bigint)))),
    CONSTRAINT mkt_item_status CHECK ((status = ANY (ARRAY['DRAFT'::text, 'APPROVED'::text, 'PUBLISHED'::text, 'CANCELLED'::text]))),
    CONSTRAINT mkt_item_time_minute CHECK (((publish_at IS NULL) OR (EXTRACT(second FROM publish_at) = (0)::numeric)))
);

ALTER TABLE ONLY public.mkt_items FORCE ROW LEVEL SECURITY;


ALTER TABLE public.mkt_items OWNER TO eyework_owner;

--
-- Name: mkt_results; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    campaign_id uuid NOT NULL,
    user_id uuid NOT NULL,
    channel text NOT NULL,
    row_version integer DEFAULT 1 NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    spend_halalas bigint,
    impressions bigint,
    clicks bigint,
    leads bigint,
    orders bigint,
    revenue_halalas bigint,
    acknowledged_flags text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT mkt_results_clicks CHECK (((clicks >= 0) AND (clicks <= '100000000000'::bigint))),
    CONSTRAINT mkt_results_impressions CHECK (((impressions >= 0) AND (impressions <= '100000000000'::bigint))),
    CONSTRAINT mkt_results_leads CHECK (((leads >= 0) AND (leads <= 1000000000))),
    CONSTRAINT mkt_results_orders CHECK (((orders >= 0) AND (orders <= 1000000000))),
    CONSTRAINT mkt_results_period CHECK (((period_end >= period_start) AND (period_start >= '2020-01-01'::date))),
    CONSTRAINT mkt_results_revenue CHECK (((revenue_halalas >= 0) AND (revenue_halalas <= '100000000000'::bigint))),
    CONSTRAINT mkt_results_some CHECK ((num_nonnulls(spend_halalas, impressions, clicks, leads, orders, revenue_halalas) >= 1)),
    CONSTRAINT mkt_results_spend CHECK (((spend_halalas >= 0) AND (spend_halalas <= '10000000000'::bigint)))
);

ALTER TABLE ONLY public.mkt_results FORCE ROW LEVEL SECURITY;


ALTER TABLE public.mkt_results OWNER TO eyework_owner;

--
-- Name: mkt_review_calls; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.mkt_review_calls (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    item_id uuid NOT NULL,
    body_digest bytea NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    outcome text,
    input_tokens integer,
    output_tokens integer,
    served_model text,
    prompt_version text,
    api_request_id text,
    new_account boolean DEFAULT false NOT NULL,
    CONSTRAINT mkt_review_calls_api_request_id_check CHECK (((api_request_id IS NULL) OR (char_length(api_request_id) <= 128))),
    CONSTRAINT mkt_review_calls_input_tokens_check CHECK ((input_tokens >= 0)),
    CONSTRAINT mkt_review_calls_output_tokens_check CHECK ((output_tokens >= 0)),
    CONSTRAINT mkt_review_calls_prompt_version_check CHECK (((prompt_version IS NULL) OR (prompt_version ~ '^[a-z0-9.-]{1,32}$'::text))),
    CONSTRAINT mkt_review_calls_served_model_check CHECK (((served_model IS NULL) OR (served_model ~ '^claude-[a-z0-9.-]{1,57}$'::text))),
    CONSTRAINT mkt_review_digest CHECK ((octet_length(body_digest) = 32)),
    CONSTRAINT mkt_review_finished_iff_outcome CHECK (((finished_at IS NULL) = (outcome IS NULL))),
    CONSTRAINT mkt_review_outcome CHECK ((outcome = ANY (ARRAY['OK'::text, 'REFUSED'::text, 'OUTPUT_INVALID'::text, 'DISCARDED'::text, 'UPSTREAM_BUSY'::text, 'UPSTREAM_UNREACHABLE'::text, 'UPSTREAM_TIMEOUT'::text, 'UPSTREAM_ERROR'::text])))
);

ALTER TABLE ONLY public.mkt_review_calls FORCE ROW LEVEL SECURITY;


ALTER TABLE public.mkt_review_calls OWNER TO eyework_owner;

--
-- Name: passkey_challenges; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: passkeys; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: professions; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.professions (
    code text NOT NULL,
    name_ar text NOT NULL,
    CONSTRAINT profession_code_shape CHECK ((code ~ '^[A-Z_]{3,20}$'::text)),
    CONSTRAINT profession_name_shape CHECK (((char_length(name_ar) >= 2) AND (char_length(name_ar) <= 40)))
);

ALTER TABLE ONLY public.professions FORCE ROW LEVEL SECURITY;


ALTER TABLE public.professions OWNER TO eyework_owner;

--
-- Name: registration_ledger; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: eyework_owner
--

CREATE TABLE public.schema_migrations (
    version text NOT NULL,
    name text NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.schema_migrations OWNER TO eyework_owner;

--
-- Name: sessions; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: signup_codes; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: users; Type: TABLE; Schema: public; Owner: eyework_owner
--

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

--
-- Name: activation_tokens activation_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.activation_tokens
    ADD CONSTRAINT activation_tokens_pkey PRIMARY KEY (token_hash);


--
-- Name: campaign_images campaign_images_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaign_images
    ADD CONSTRAINT campaign_images_pkey PRIMARY KEY (campaign_id);


--
-- Name: campaign_transition campaign_transition_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaign_transition
    ADD CONSTRAINT campaign_transition_pkey PRIMARY KEY (from_status, to_status);


--
-- Name: campaigns campaigns_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_id_user_id_key UNIQUE (id, user_id);


--
-- Name: campaigns campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_pkey PRIMARY KEY (id);


--
-- Name: copy_versions copy_versions_attempt_id_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_attempt_id_key UNIQUE (attempt_id);


--
-- Name: copy_versions copy_versions_campaign_id_id_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_id_key UNIQUE (campaign_id, id);


--
-- Name: copy_versions copy_versions_campaign_id_version_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_version_key UNIQUE (campaign_id, version);


--
-- Name: copy_versions copy_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_pkey PRIMARY KEY (id);


--
-- Name: generation_attempts generation_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.generation_attempts
    ADD CONSTRAINT generation_attempts_pkey PRIMARY KEY (id);


--
-- Name: mkt_ai_flags mkt_ai_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_ai_flags
    ADD CONSTRAINT mkt_ai_flags_pkey PRIMARY KEY (item_id, body_digest, ordinal);


--
-- Name: mkt_campaign_channels mkt_campaign_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_campaign_channels
    ADD CONSTRAINT mkt_campaign_channels_pkey PRIMARY KEY (campaign_id, channel);


--
-- Name: mkt_campaign_transition mkt_campaign_transition_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_campaign_transition
    ADD CONSTRAINT mkt_campaign_transition_pkey PRIMARY KEY (from_status, to_status);


--
-- Name: mkt_campaigns mkt_campaigns_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_campaigns
    ADD CONSTRAINT mkt_campaigns_id_user_id_key UNIQUE (id, user_id);


--
-- Name: mkt_campaigns mkt_campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_campaigns
    ADD CONSTRAINT mkt_campaigns_pkey PRIMARY KEY (id);


--
-- Name: mkt_item_transition mkt_item_transition_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_item_transition
    ADD CONSTRAINT mkt_item_transition_pkey PRIMARY KEY (from_status, to_status);


--
-- Name: mkt_items mkt_items_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_items
    ADD CONSTRAINT mkt_items_id_user_id_key UNIQUE (id, user_id);


--
-- Name: mkt_items mkt_items_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_items
    ADD CONSTRAINT mkt_items_pkey PRIMARY KEY (id);


--
-- Name: mkt_results mkt_results_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_results
    ADD CONSTRAINT mkt_results_pkey PRIMARY KEY (id);


--
-- Name: mkt_review_calls mkt_review_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_review_calls
    ADD CONSTRAINT mkt_review_calls_pkey PRIMARY KEY (id);


--
-- Name: passkey_challenges passkey_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.passkey_challenges
    ADD CONSTRAINT passkey_challenges_pkey PRIMARY KEY (challenge_hash);


--
-- Name: passkeys passkeys_credential_id_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.passkeys
    ADD CONSTRAINT passkeys_credential_id_key UNIQUE (credential_id);


--
-- Name: passkeys passkeys_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.passkeys
    ADD CONSTRAINT passkeys_pkey PRIMARY KEY (id);


--
-- Name: professions professions_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.professions
    ADD CONSTRAINT professions_pkey PRIMARY KEY (code);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_token_hash_key UNIQUE (token_hash);


--
-- Name: signup_codes signup_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.signup_codes
    ADD CONSTRAINT signup_codes_pkey PRIMARY KEY (code_hash);


--
-- Name: users users_login_hmac_key; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_login_hmac_key UNIQUE (login_hmac);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: activation_one_open; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE UNIQUE INDEX activation_one_open ON public.activation_tokens USING btree (user_id) WHERE (used_at IS NULL);


--
-- Name: attempt_tombstones_time; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX attempt_tombstones_time ON public.attempt_tombstones USING btree (started_at);


--
-- Name: attempts_campaign; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX attempts_campaign ON public.generation_attempts USING btree (campaign_id);


--
-- Name: attempts_time; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX attempts_time ON public.generation_attempts USING btree (started_at DESC);


--
-- Name: attempts_user_time; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX attempts_user_time ON public.generation_attempts USING btree (user_id, started_at DESC);


--
-- Name: campaigns_user_recent; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX campaigns_user_recent ON public.campaigns USING btree (user_id, updated_at DESC);


--
-- Name: mkt_campaigns_user_status; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX mkt_campaigns_user_status ON public.mkt_campaigns USING btree (user_id, status, starts_on);


--
-- Name: mkt_items_campaign; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX mkt_items_campaign ON public.mkt_items USING btree (campaign_id, channel);


--
-- Name: mkt_items_source; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX mkt_items_source ON public.mkt_items USING btree (source_campaign_id) WHERE (source_campaign_id IS NOT NULL);


--
-- Name: mkt_items_user_day; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX mkt_items_user_day ON public.mkt_items USING btree (user_id, publish_on);


--
-- Name: mkt_results_channel_period; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX mkt_results_channel_period ON public.mkt_results USING btree (campaign_id, channel, period_start);


--
-- Name: mkt_review_calls_time; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX mkt_review_calls_time ON public.mkt_review_calls USING btree (started_at DESC);


--
-- Name: mkt_review_calls_user_time; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX mkt_review_calls_user_time ON public.mkt_review_calls USING btree (user_id, started_at DESC);


--
-- Name: passkey_challenges_expiry_idx; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX passkey_challenges_expiry_idx ON public.passkey_challenges USING btree (expires_at);


--
-- Name: passkeys_user_idx; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX passkeys_user_idx ON public.passkeys USING btree (user_id);


--
-- Name: registration_ledger_time; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX registration_ledger_time ON public.registration_ledger USING btree (occurred_at);


--
-- Name: sessions_user_idx; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX sessions_user_idx ON public.sessions USING btree (user_id) WHERE (revoked_at IS NULL);


--
-- Name: generation_attempts trg_attempt_settle; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_attempt_settle BEFORE UPDATE ON public.generation_attempts FOR EACH ROW EXECUTE FUNCTION public.ew_attempt_settle_once();


--
-- Name: generation_attempts trg_attempt_tombstone; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_attempt_tombstone BEFORE DELETE ON public.generation_attempts FOR EACH ROW EXECUTE FUNCTION public.ew_attempt_tombstone();


--
-- Name: campaigns trg_campaign_guard; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_campaign_guard BEFORE UPDATE ON public.campaigns FOR EACH ROW EXECUTE FUNCTION public.ew_campaign_guard();


--
-- Name: campaigns trg_campaign_insert; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_campaign_insert BEFORE INSERT ON public.campaigns FOR EACH ROW EXECUTE FUNCTION public.ew_campaign_insert_guard();


--
-- Name: campaign_images trg_image_guard; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_image_guard BEFORE INSERT OR UPDATE ON public.campaign_images FOR EACH ROW EXECUTE FUNCTION public.ew_image_guard();


--
-- Name: campaign_images trg_image_touch; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_image_touch BEFORE UPDATE ON public.campaign_images FOR EACH ROW EXECUTE FUNCTION public.ew_image_touch();


--
-- Name: mkt_ai_flags trg_mkt_ai_flags_append_only; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_ai_flags_append_only BEFORE UPDATE ON public.mkt_ai_flags FOR EACH ROW EXECUTE FUNCTION public.ew_forbid_update();


--
-- Name: mkt_campaign_channels trg_mkt_allocations; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE CONSTRAINT TRIGGER trg_mkt_allocations AFTER INSERT OR UPDATE ON public.mkt_campaign_channels DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_allocations_check();


--
-- Name: mkt_campaigns trg_mkt_campaign_guard; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_campaign_guard BEFORE UPDATE ON public.mkt_campaigns FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_campaign_guard();


--
-- Name: mkt_campaigns trg_mkt_campaign_insert; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_campaign_insert BEFORE INSERT ON public.mkt_campaigns FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_campaign_insert_guard();


--
-- Name: mkt_campaign_channels trg_mkt_channel_guard; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_channel_guard BEFORE INSERT OR DELETE OR UPDATE ON public.mkt_campaign_channels FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_channel_guard();


--
-- Name: mkt_items trg_mkt_item_guard; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_item_guard BEFORE UPDATE ON public.mkt_items FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_item_guard();


--
-- Name: mkt_items trg_mkt_item_insert; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_item_insert BEFORE INSERT ON public.mkt_items FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_item_insert_guard();


--
-- Name: mkt_results trg_mkt_results_guard; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_results_guard BEFORE INSERT OR UPDATE ON public.mkt_results FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_results_guard();


--
-- Name: mkt_review_calls trg_mkt_review_settle; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_review_settle BEFORE UPDATE ON public.mkt_review_calls FOR EACH ROW EXECUTE FUNCTION public.ew_attempt_settle_once();


--
-- Name: mkt_review_calls trg_mkt_review_tombstone; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_mkt_review_tombstone BEFORE DELETE ON public.mkt_review_calls FOR EACH ROW EXECUTE FUNCTION public.ew_mkt_review_tombstone();


--
-- Name: campaigns trg_purge_image; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_purge_image AFTER UPDATE OF status ON public.campaigns FOR EACH ROW WHEN ((new.status = 'CANCELLED'::text)) EXECUTE FUNCTION public.ew_purge_image_on_cancel();


--
-- Name: copy_versions trg_version_current; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_version_current AFTER INSERT ON public.copy_versions FOR EACH ROW EXECUTE FUNCTION public.ew_version_becomes_current();


--
-- Name: copy_versions trg_version_insert; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_version_insert BEFORE INSERT ON public.copy_versions FOR EACH ROW EXECUTE FUNCTION public.ew_version_insert_guard();


--
-- Name: copy_versions trg_versions_append_only; Type: TRIGGER; Schema: public; Owner: eyework_owner
--

CREATE TRIGGER trg_versions_append_only BEFORE UPDATE ON public.copy_versions FOR EACH ROW EXECUTE FUNCTION public.ew_forbid_update();


--
-- Name: activation_tokens activation_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.activation_tokens
    ADD CONSTRAINT activation_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: campaigns approved_version_belongs; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT approved_version_belongs FOREIGN KEY (id, approved_version_id) REFERENCES public.copy_versions(campaign_id, id);


--
-- Name: generation_attempts attempt_base_belongs; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.generation_attempts
    ADD CONSTRAINT attempt_base_belongs FOREIGN KEY (campaign_id, based_on_version_id) REFERENCES public.copy_versions(campaign_id, id);


--
-- Name: campaign_images campaign_images_campaign_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaign_images
    ADD CONSTRAINT campaign_images_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.campaigns(id, user_id) ON DELETE CASCADE;


--
-- Name: campaigns campaigns_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: copy_versions copy_versions_attempt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_attempt_id_fkey FOREIGN KEY (attempt_id) REFERENCES public.generation_attempts(id);


--
-- Name: copy_versions copy_versions_campaign_id_based_on_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_based_on_version_id_fkey FOREIGN KEY (campaign_id, based_on_version_id) REFERENCES public.copy_versions(campaign_id, id);


--
-- Name: copy_versions copy_versions_campaign_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.copy_versions
    ADD CONSTRAINT copy_versions_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.campaigns(id, user_id) ON DELETE CASCADE;


--
-- Name: campaigns current_version_belongs; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT current_version_belongs FOREIGN KEY (id, current_version_id) REFERENCES public.copy_versions(campaign_id, id);


--
-- Name: generation_attempts generation_attempts_campaign_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.generation_attempts
    ADD CONSTRAINT generation_attempts_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.campaigns(id, user_id) ON DELETE CASCADE;


--
-- Name: mkt_ai_flags mkt_ai_flags_item_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_ai_flags
    ADD CONSTRAINT mkt_ai_flags_item_id_user_id_fkey FOREIGN KEY (item_id, user_id) REFERENCES public.mkt_items(id, user_id) ON DELETE CASCADE;


--
-- Name: mkt_campaign_channels mkt_campaign_channels_campaign_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_campaign_channels
    ADD CONSTRAINT mkt_campaign_channels_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.mkt_campaigns(id, user_id) ON DELETE CASCADE;


--
-- Name: mkt_campaigns mkt_campaigns_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_campaigns
    ADD CONSTRAINT mkt_campaigns_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: mkt_items mkt_items_campaign_id_channel_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_items
    ADD CONSTRAINT mkt_items_campaign_id_channel_fkey FOREIGN KEY (campaign_id, channel) REFERENCES public.mkt_campaign_channels(campaign_id, channel) ON DELETE CASCADE;


--
-- Name: mkt_items mkt_items_campaign_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_items
    ADD CONSTRAINT mkt_items_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.mkt_campaigns(id, user_id) ON DELETE CASCADE;


--
-- Name: mkt_items mkt_items_source_campaign_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_items
    ADD CONSTRAINT mkt_items_source_campaign_id_user_id_fkey FOREIGN KEY (source_campaign_id, user_id) REFERENCES public.campaigns(id, user_id) ON DELETE SET NULL (source_campaign_id);


--
-- Name: mkt_results mkt_results_campaign_id_channel_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_results
    ADD CONSTRAINT mkt_results_campaign_id_channel_fkey FOREIGN KEY (campaign_id, channel) REFERENCES public.mkt_campaign_channels(campaign_id, channel);


--
-- Name: mkt_results mkt_results_campaign_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_results
    ADD CONSTRAINT mkt_results_campaign_id_user_id_fkey FOREIGN KEY (campaign_id, user_id) REFERENCES public.mkt_campaigns(id, user_id) ON DELETE CASCADE;


--
-- Name: mkt_review_calls mkt_review_calls_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.mkt_review_calls
    ADD CONSTRAINT mkt_review_calls_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: passkey_challenges passkey_challenges_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.passkey_challenges
    ADD CONSTRAINT passkey_challenges_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: passkeys passkeys_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.passkeys
    ADD CONSTRAINT passkeys_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: signup_codes signup_codes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.signup_codes
    ADD CONSTRAINT signup_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: users users_profession_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eyework_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_profession_fkey FOREIGN KEY (profession) REFERENCES public.professions(code) ON DELETE RESTRICT;


--
-- Name: activation_tokens activation_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY activation_owner_access ON public.activation_tokens TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: activation_tokens; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.activation_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: attempt_tombstones; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.attempt_tombstones ENABLE ROW LEVEL SECURITY;

--
-- Name: attempt_tombstones attempt_tombstones_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY attempt_tombstones_owner_access ON public.attempt_tombstones TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: generation_attempts attempts_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY attempts_own ON public.generation_attempts TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));


--
-- Name: generation_attempts attempts_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY attempts_owner_access ON public.generation_attempts TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: campaign_images; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.campaign_images ENABLE ROW LEVEL SECURITY;

--
-- Name: campaigns; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;

--
-- Name: campaigns campaigns_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY campaigns_own ON public.campaigns TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));


--
-- Name: campaigns campaigns_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY campaigns_owner_access ON public.campaigns TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: copy_versions; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.copy_versions ENABLE ROW LEVEL SECURITY;

--
-- Name: generation_attempts; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.generation_attempts ENABLE ROW LEVEL SECURITY;

--
-- Name: campaign_images images_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY images_own ON public.campaign_images TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));


--
-- Name: campaign_images images_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY images_owner_access ON public.campaign_images TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: mkt_ai_flags; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.mkt_ai_flags ENABLE ROW LEVEL SECURITY;

--
-- Name: mkt_ai_flags mkt_ai_flags_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_ai_flags_own ON public.mkt_ai_flags FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));


--
-- Name: mkt_ai_flags mkt_ai_flags_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_ai_flags_owner_access ON public.mkt_ai_flags TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: mkt_campaign_channels; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.mkt_campaign_channels ENABLE ROW LEVEL SECURITY;

--
-- Name: mkt_campaigns; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.mkt_campaigns ENABLE ROW LEVEL SECURITY;

--
-- Name: mkt_campaigns mkt_campaigns_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_campaigns_own ON public.mkt_campaigns FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));


--
-- Name: mkt_campaigns mkt_campaigns_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_campaigns_owner_access ON public.mkt_campaigns TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: mkt_campaign_channels mkt_channels_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_channels_own ON public.mkt_campaign_channels FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));


--
-- Name: mkt_campaign_channels mkt_channels_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_channels_owner_access ON public.mkt_campaign_channels TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: mkt_items; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.mkt_items ENABLE ROW LEVEL SECURITY;

--
-- Name: mkt_items mkt_items_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_items_own ON public.mkt_items FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));


--
-- Name: mkt_items mkt_items_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_items_owner_access ON public.mkt_items TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: mkt_results; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.mkt_results ENABLE ROW LEVEL SECURITY;

--
-- Name: mkt_results mkt_results_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_results_own ON public.mkt_results FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));


--
-- Name: mkt_results mkt_results_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_results_owner_access ON public.mkt_results TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: mkt_review_calls; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.mkt_review_calls ENABLE ROW LEVEL SECURITY;

--
-- Name: mkt_review_calls mkt_reviews_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_reviews_own ON public.mkt_review_calls FOR SELECT TO eyework_app USING ((user_id = public.ew_current_user()));


--
-- Name: mkt_review_calls mkt_reviews_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY mkt_reviews_owner_access ON public.mkt_review_calls TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: passkey_challenges; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.passkey_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: passkey_challenges passkey_challenges_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY passkey_challenges_owner_access ON public.passkey_challenges TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: passkeys; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.passkeys ENABLE ROW LEVEL SECURITY;

--
-- Name: passkeys passkeys_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY passkeys_owner_access ON public.passkeys TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: professions; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.professions ENABLE ROW LEVEL SECURITY;

--
-- Name: professions professions_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY professions_owner_access ON public.professions TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: registration_ledger; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.registration_ledger ENABLE ROW LEVEL SECURITY;

--
-- Name: registration_ledger registration_ledger_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY registration_ledger_owner_access ON public.registration_ledger TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: sessions; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions sessions_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY sessions_owner_access ON public.sessions TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: signup_codes; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.signup_codes ENABLE ROW LEVEL SECURITY;

--
-- Name: signup_codes signup_codes_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY signup_codes_owner_access ON public.signup_codes TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: eyework_owner
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: users users_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY users_owner_access ON public.users TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: copy_versions versions_own; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY versions_own ON public.copy_versions TO eyework_app USING ((user_id = public.ew_current_user())) WITH CHECK ((user_id = public.ew_current_user()));


--
-- Name: copy_versions versions_owner_access; Type: POLICY; Schema: public; Owner: eyework_owner
--

CREATE POLICY versions_owner_access ON public.copy_versions TO eyework_owner USING (true) WITH CHECK (true);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO eyework_app;


--
-- Name: FUNCTION ew_accept_terms(p_version text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_accept_terms(p_version text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_accept_terms(p_version text) TO eyework_app;


--
-- Name: FUNCTION ew_activate(p_token bytea, p_login bytea, p_password_hash text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) TO eyework_app;


--
-- Name: FUNCTION ew_ai_spend(p_new_only boolean); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_ai_spend(p_new_only boolean) FROM PUBLIC;


--
-- Name: FUNCTION ew_attempt_settle_once(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_attempt_settle_once() FROM PUBLIC;


--
-- Name: FUNCTION ew_attempt_tombstone(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_attempt_tombstone() FROM PUBLIC;


--
-- Name: FUNCTION ew_begin_generation(p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_begin_generation(p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_begin_generation(p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid) TO eyework_app;


--
-- Name: FUNCTION ew_budget_allowed(v integer); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_budget_allowed(v integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_budget_allowed(v integer) TO eyework_app;


--
-- Name: FUNCTION ew_campaign_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_campaign_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_campaign_insert_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_campaign_insert_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_current_user(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_current_user() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_current_user() TO eyework_app;


--
-- Name: FUNCTION ew_delete_me(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_delete_me() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_delete_me() TO eyework_app;


--
-- Name: FUNCTION ew_finish_generation(p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_finish_generation(p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_finish_generation(p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer) TO eyework_app;


--
-- Name: FUNCTION ew_forbid_update(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_forbid_update() FROM PUBLIC;


--
-- Name: FUNCTION ew_image_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_image_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_image_touch(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_image_touch() FROM PUBLIC;


--
-- Name: FUNCTION ew_is_billable(o text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_is_billable(o text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_is_billable(o text) TO eyework_app;


--
-- Name: FUNCTION ew_jpeg_has_no_metadata(b bytea); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_jpeg_has_no_metadata(b bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_jpeg_has_no_metadata(b bytea) TO eyework_app;


--
-- Name: FUNCTION ew_login_lookup(p_login bytea); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_login_lookup(p_login bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_login_lookup(p_login bytea) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_allocations_check(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_allocations_check() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_campaign_create(p_name text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_campaign_create(p_name text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_campaign_create(p_name text) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_campaign_flags(p_campaign uuid); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_campaign_flags(p_campaign uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_campaign_flags(p_campaign uuid) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_campaign_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_campaign_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_campaign_insert_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_campaign_insert_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_campaign_save(p_campaign uuid, p_expected_row_version integer, p_name text, p_brief text, p_goal text, p_kpi_metric text, p_kpi_target bigint, p_audience text, p_budget_halalas bigint, p_starts_on date, p_ends_on date); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_campaign_save(p_campaign uuid, p_expected_row_version integer, p_name text, p_brief text, p_goal text, p_kpi_metric text, p_kpi_target bigint, p_audience text, p_budget_halalas bigint, p_starts_on date, p_ends_on date) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_campaign_save(p_campaign uuid, p_expected_row_version integer, p_name text, p_brief text, p_goal text, p_kpi_metric text, p_kpi_target bigint, p_audience text, p_budget_halalas bigint, p_starts_on date, p_ends_on date) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_campaign_transition(p_campaign uuid, p_expected_row_version integer, p_to text, p_acknowledged text[]); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_campaign_transition(p_campaign uuid, p_expected_row_version integer, p_to text, p_acknowledged text[]) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_campaign_transition(p_campaign uuid, p_expected_row_version integer, p_to text, p_acknowledged text[]) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_channel_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_channel_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_channel_known(c text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_channel_known(c text) FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_item_create(p_campaign uuid, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint, p_source_campaign uuid); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_item_create(p_campaign uuid, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint, p_source_campaign uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_item_create(p_campaign uuid, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint, p_source_campaign uuid) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_item_flags(p_item uuid); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_item_flags(p_item uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_item_flags(p_item uuid) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_item_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_item_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_item_insert_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_item_insert_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_item_save(p_item uuid, p_expected_row_version integer, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_item_save(p_item uuid, p_expected_row_version integer, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_item_save(p_item uuid, p_expected_row_version integer, p_channel text, p_publish_on date, p_publish_at time without time zone, p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_item_transition(p_item uuid, p_expected_row_version integer, p_to text, p_acknowledged text[], p_published_at timestamp with time zone); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_item_transition(p_item uuid, p_expected_row_version integer, p_to text, p_acknowledged text[], p_published_at timestamp with time zone) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_item_transition(p_item uuid, p_expected_row_version integer, p_to text, p_acknowledged text[], p_published_at timestamp with time zone) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_kpi_fits(p_goal text, p_kpi text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_kpi_fits(p_goal text, p_kpi text) FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_text_ok(t text, p_multiline boolean); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_text_ok(t text, p_multiline boolean) FROM PUBLIC;


--
-- Name: TABLE mkt_campaigns; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_campaigns TO eyework_app;


--
-- Name: FUNCTION ew_mkt_lock_campaign(p_uid uuid, p_campaign uuid, p_expected_row_version integer); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_lock_campaign(p_uid uuid, p_campaign uuid, p_expected_row_version integer) FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_require(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_require() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_results_flags(p_campaign uuid, p_channel text, p_result uuid, p_spend bigint); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_results_flags(p_campaign uuid, p_channel text, p_result uuid, p_spend bigint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_results_flags(p_campaign uuid, p_channel text, p_result uuid, p_spend bigint) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_results_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_results_guard() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_results_save(p_campaign uuid, p_channel text, p_result uuid, p_expected_row_version integer, p_period_start date, p_period_end date, p_spend_halalas bigint, p_impressions bigint, p_clicks bigint, p_leads bigint, p_orders bigint, p_revenue_halalas bigint, p_acknowledged text[]); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_results_save(p_campaign uuid, p_channel text, p_result uuid, p_expected_row_version integer, p_period_start date, p_period_end date, p_spend_halalas bigint, p_impressions bigint, p_clicks bigint, p_leads bigint, p_orders bigint, p_revenue_halalas bigint, p_acknowledged text[]) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_results_save(p_campaign uuid, p_channel text, p_result uuid, p_expected_row_version integer, p_period_start date, p_period_end date, p_spend_halalas bigint, p_impressions bigint, p_clicks bigint, p_leads bigint, p_orders bigint, p_revenue_halalas bigint, p_acknowledged text[]) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_review_begin(p_item uuid); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_review_begin(p_item uuid) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_review_begin(p_item uuid) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_review_finish(p_call uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer, p_served_model text, p_request_id text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_review_finish(p_call uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer, p_served_model text, p_request_id text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_review_finish(p_call uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer, p_served_model text, p_request_id text) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_review_record(p_call uuid, p_kinds text[], p_quotes text[], p_reasons text[], p_input_tokens integer, p_output_tokens integer, p_served_model text, p_prompt_version text, p_request_id text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_review_record(p_call uuid, p_kinds text[], p_quotes text[], p_reasons text[], p_input_tokens integer, p_output_tokens integer, p_served_model text, p_prompt_version text, p_request_id text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_review_record(p_call uuid, p_kinds text[], p_quotes text[], p_reasons text[], p_input_tokens integer, p_output_tokens integer, p_served_model text, p_prompt_version text, p_request_id text) TO eyework_app;


--
-- Name: FUNCTION ew_mkt_review_tombstone(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_review_tombstone() FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_same_keys(a text[], b text[]); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_same_keys(a text[], b text[]) FROM PUBLIC;


--
-- Name: FUNCTION ew_mkt_set_channels(p_campaign uuid, p_expected_row_version integer, p_channels text[], p_allocations bigint[]); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_mkt_set_channels(p_campaign uuid, p_expected_row_version integer, p_channels text[], p_allocations bigint[]) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_mkt_set_channels(p_campaign uuid, p_expected_row_version integer, p_channels text[], p_allocations bigint[]) TO eyework_app;


--
-- Name: FUNCTION ew_my_display_name(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_my_display_name() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_display_name() TO eyework_app;


--
-- Name: FUNCTION ew_my_generation_limit(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_my_generation_limit() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_generation_limit() TO eyework_app;


--
-- Name: FUNCTION ew_my_passkeys(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_my_passkeys() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_passkeys() TO eyework_app;


--
-- Name: FUNCTION ew_my_profession(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_my_profession() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_profession() TO eyework_app;


--
-- Name: FUNCTION ew_my_terms_version(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_my_terms_version() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_terms_version() TO eyework_app;


--
-- Name: FUNCTION ew_my_ui_size(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_my_ui_size() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_ui_size() TO eyework_app;


--
-- Name: FUNCTION ew_new_open_account(p_user uuid); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_new_open_account(p_user uuid) FROM PUBLIC;


--
-- Name: FUNCTION ew_open_registration_blocker(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_open_registration_blocker() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_open_registration_blocker() TO eyework_app;


--
-- Name: FUNCTION ew_open_session(p_user uuid, p_token bytea); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_open_session(p_user uuid, p_token bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_open_session(p_user uuid, p_token bytea) TO eyework_app;


--
-- Name: FUNCTION ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint, p_transports text[]); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint, p_transports text[]) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint, p_transports text[]) TO eyework_app;


--
-- Name: FUNCTION ew_passkey_challenge(p_challenge bytea, p_purpose text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_passkey_challenge(p_challenge bytea, p_purpose text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_challenge(p_challenge bytea, p_purpose text) TO eyework_app;


--
-- Name: FUNCTION ew_passkey_lookup(p_credential bytea); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_passkey_lookup(p_credential bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_lookup(p_credential bytea) TO eyework_app;


--
-- Name: FUNCTION ew_passkey_signed_in(p_credential bytea, p_sign_count bigint); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_passkey_signed_in(p_credential bytea, p_sign_count bigint) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_signed_in(p_credential bytea, p_sign_count bigint) TO eyework_app;


--
-- Name: FUNCTION ew_passkey_take_challenge(p_challenge bytea, p_purpose text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_passkey_take_challenge(p_challenge bytea, p_purpose text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_passkey_take_challenge(p_challenge bytea, p_purpose text) TO eyework_app;


--
-- Name: FUNCTION ew_purge_image_on_cancel(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_purge_image_on_cancel() FROM PUBLIC;


--
-- Name: FUNCTION ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) TO eyework_app;


--
-- Name: FUNCTION ew_register_open(p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_register_open(p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_register_open(p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text, p_size text) TO eyework_app;


--
-- Name: FUNCTION ew_registration_blocker(p_via text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_registration_blocker(p_via text) FROM PUBLIC;


--
-- Name: FUNCTION ew_resolve_session(p_token bytea); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_resolve_session(p_token bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_resolve_session(p_token bytea) TO eyework_app;


--
-- Name: FUNCTION ew_revoke_session(p_token bytea); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_revoke_session(p_token bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_revoke_session(p_token bytea) TO eyework_app;


--
-- Name: FUNCTION ew_riyadh_today(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_riyadh_today() FROM PUBLIC;


--
-- Name: FUNCTION ew_set_my_ui_size(p_size text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_set_my_ui_size(p_size text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_set_my_ui_size(p_size text) TO eyework_app;


--
-- Name: FUNCTION ew_signup_code_usable(p_code bytea); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_signup_code_usable(p_code bytea) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_signup_code_usable(p_code bytea) TO eyework_app;


--
-- Name: FUNCTION ew_version_becomes_current(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_version_becomes_current() FROM PUBLIC;


--
-- Name: FUNCTION ew_version_insert_guard(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_version_insert_guard() FROM PUBLIC;


--
-- Name: TABLE campaign_images; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.campaign_images TO eyework_app;


--
-- Name: COLUMN campaign_images.campaign_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(campaign_id) ON TABLE public.campaign_images TO eyework_app;


--
-- Name: COLUMN campaign_images.user_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(user_id) ON TABLE public.campaign_images TO eyework_app;


--
-- Name: COLUMN campaign_images.jpeg; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(jpeg),UPDATE(jpeg) ON TABLE public.campaign_images TO eyework_app;


--
-- Name: COLUMN campaign_images.width; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(width),UPDATE(width) ON TABLE public.campaign_images TO eyework_app;


--
-- Name: COLUMN campaign_images.height; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(height),UPDATE(height) ON TABLE public.campaign_images TO eyework_app;


--
-- Name: COLUMN campaign_images.sha256; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(sha256),UPDATE(sha256) ON TABLE public.campaign_images TO eyework_app;


--
-- Name: TABLE campaign_transition; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.campaign_transition TO eyework_app;


--
-- Name: TABLE campaigns; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.campaigns TO eyework_app;


--
-- Name: COLUMN campaigns.user_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(user_id) ON TABLE public.campaigns TO eyework_app;


--
-- Name: COLUMN campaigns.status; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT UPDATE(status) ON TABLE public.campaigns TO eyework_app;


--
-- Name: COLUMN campaigns.current_version_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT UPDATE(current_version_id) ON TABLE public.campaigns TO eyework_app;


--
-- Name: COLUMN campaigns.budget_sar; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT UPDATE(budget_sar) ON TABLE public.campaigns TO eyework_app;


--
-- Name: COLUMN campaigns.days; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT UPDATE(days) ON TABLE public.campaigns TO eyework_app;


--
-- Name: TABLE copy_versions; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.campaign_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(campaign_id) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.user_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(user_id) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.attempt_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(attempt_id) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.title; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(title) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.description; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(description) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.edit_presets; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(edit_presets) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.edit_note; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(edit_note) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.warnings; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(warnings) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.served_model; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(served_model) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.prompt_version; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(prompt_version) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.api_request_id; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(api_request_id) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: COLUMN copy_versions.assistant_note; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT INSERT(assistant_note) ON TABLE public.copy_versions TO eyework_app;


--
-- Name: TABLE generation_attempts; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.generation_attempts TO eyework_app;


--
-- Name: TABLE mkt_ai_flags; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_ai_flags TO eyework_app;


--
-- Name: TABLE mkt_campaign_channels; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_campaign_channels TO eyework_app;


--
-- Name: TABLE mkt_campaign_transition; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_campaign_transition TO eyework_app;


--
-- Name: TABLE mkt_item_transition; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_item_transition TO eyework_app;


--
-- Name: TABLE mkt_items; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_items TO eyework_app;


--
-- Name: TABLE mkt_results; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_results TO eyework_app;


--
-- Name: TABLE mkt_review_calls; Type: ACL; Schema: public; Owner: eyework_owner
--

GRANT SELECT ON TABLE public.mkt_review_calls TO eyework_app;


--
-- PostgreSQL database dump complete
--


