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
-- Name: regopen_spec_test; Type: DATABASE; Schema: -; Owner: eyework_owner
--

CREATE DATABASE regopen_spec_test WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C.UTF-8';


ALTER DATABASE regopen_spec_test OWNER TO eyework_owner;

\connect regopen_spec_test

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
        INSERT INTO attempt_tombstones (started_at, outcome) VALUES (OLD.started_at, OLD.outcome);
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
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image)
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
-- Name: ew_register(bytea, bytea, text, text, date, text, text); Type: FUNCTION; Schema: public; Owner: eyework_owner
--

CREATE FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text) RETURNS TABLE(new_user uuid, outcome text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
    uid  uuid;
    code signup_codes%ROWTYPE;
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
    -- قفلٌ واحد للجميع: بلا هذا يرى تسجيلان متزامنان العدَّ نفسه ويمرّان معاً.
    -- والعدّ من الرموز المستعملة لا من الحسابات: الحساب يُحذف بيد صاحبه، والرمز
    -- يبقى مستعملاً (user_id يصير NULL)، فلا يُفرغ الحذفُ السقفَ.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    IF (SELECT count(*) FROM signup_codes WHERE used_at > now() - interval '24 hours') >= 200 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_daily_cap';
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       self_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        UPDATE signup_codes SET taken_count = taken_count + 1 WHERE code_hash = p_code;
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    UPDATE signup_codes SET used_at = now(), user_id = uid WHERE code_hash = p_code;
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;


ALTER FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text) OWNER TO eyework_owner;

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

SET default_tablespace = '';

SET default_table_access_method = heap;

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
    outcome text
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
    CONSTRAINT activated_iff_password CHECK (((activated_at IS NULL) = (password_hash IS NULL))),
    CONSTRAINT birth_date_range CHECK (((birth_date IS NULL) OR (birth_date >= '1900-01-01'::date))),
    CONSTRAINT display_name_shape CHECK (((display_name IS NULL) OR (((char_length(display_name) >= 1) AND (char_length(display_name) <= 30)) AND (display_name ~ '^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$'::text)))),
    CONSTRAINT self_registered_accepted_terms CHECK (((NOT self_registered) OR (terms_version IS NOT NULL))),
    CONSTRAINT terms_complete CHECK (((terms_version IS NULL) = (terms_accepted_at IS NULL))),
    CONSTRAINT terms_version_shape CHECK (((terms_version IS NULL) OR (terms_version ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'::text))),
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
-- Name: passkey_challenges_expiry_idx; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX passkey_challenges_expiry_idx ON public.passkey_challenges USING btree (expires_at);


--
-- Name: passkeys_user_idx; Type: INDEX; Schema: public; Owner: eyework_owner
--

CREATE INDEX passkeys_user_idx ON public.passkeys USING btree (user_id);


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
-- Name: DATABASE regopen_spec_test; Type: ACL; Schema: -; Owner: eyework_owner
--

REVOKE CONNECT,TEMPORARY ON DATABASE regopen_spec_test FROM PUBLIC;
GRANT CONNECT ON DATABASE regopen_spec_test TO eyework_app;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO eyework_app;


--
-- Name: FUNCTION ew_activate(p_token bytea, p_login bytea, p_password_hash text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_activate(p_token bytea, p_login bytea, p_password_hash text) TO eyework_app;


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
-- Name: FUNCTION ew_my_display_name(); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_my_display_name() FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_my_display_name() TO eyework_app;


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
-- Name: FUNCTION ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text); Type: ACL; Schema: public; Owner: eyework_owner
--

REVOKE ALL ON FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text) FROM PUBLIC;
GRANT ALL ON FUNCTION public.ew_register(p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text, p_terms_version text) TO eyework_app;


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
-- PostgreSQL database dump complete
--


