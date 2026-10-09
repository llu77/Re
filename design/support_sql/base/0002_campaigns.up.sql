-- ════════════════════════════════════════════════════════════════════════
-- 0002_campaigns — الحملة: صورة، ونصٌّ يقترحه النموذج ويعتمده صاحبه، ومال
-- ════════════════════════════════════════════════════════════════════════
-- الضمانات التي يجب أن تصمد ولو أخطأت الواجهة أو الخادم، فتُفرض هنا:
--
--   • النصّ المعتمد هو ما رآه صاحبه بالضبط. المحفّز وحده يكتب
--     `approved_version_id`، من النسخة الحالية لحظة الموافقة — لا يختاره
--     العميل. والنسخ لا تُعدَّل بعد كتابتها.
--   • لا نسخة بلا محاولة توليدٍ محسوبة، مبنيّةٍ على النسخة الحالية. سقوف
--     كلفة النموذج (واحدة جارية، ستٌّ في عشر دقائق، أربعون في اليوم لكل
--     مستخدم وألفان للجميع، وعشر نسخ لكل حملة) تُفرض في دالّة هنا، فتصمد
--     مهما تعدّدت العمليات.
--   • المال لا يتغيّر إلا والنصّ معتمد، ولا يتغيّر بعد التأكيد. READY ثابتة
--     إلا إلى الإلغاء، والإلغاء نهائي ويحذف الصورة في المعاملة نفسها.
--   • صورةٌ فيها توقيع EXIF أو XMP لا تُخزَّن، ولو أخطأ التنظيف في التطبيق.
--   • العزل بالصفّ على `eyework.user_id`، مفروضٌ على المالك أيضاً (FORCE).
--   • لا DELETE ولا TRUNCATE لدور الويب على أي جدول، والمنح بالأعمدة.
-- ════════════════════════════════════════════════════════════════════════

-- ── آلة الحالات ─────────────────────────────────────────────────────────
-- جدولٌ لا ثوابت في الشيفرة: المحفّز يقرؤه، واختبارٌ يقارنه بـeyework/states.py.
CREATE TABLE campaign_transition (
    from_status text NOT NULL,
    to_status   text NOT NULL,
    PRIMARY KEY (from_status, to_status)
);

INSERT INTO campaign_transition (from_status, to_status) VALUES
    ('DRAFT',         'COPY_PROPOSED'),
    ('COPY_PROPOSED', 'COPY_APPROVED'),
    ('COPY_APPROVED', 'COPY_PROPOSED'),
    ('COPY_APPROVED', 'READY'),
    ('DRAFT',         'CANCELLED'),
    ('COPY_PROPOSED', 'CANCELLED'),
    ('COPY_APPROVED', 'CANCELLED'),
    ('READY',         'CANCELLED');

-- ── المجالات ────────────────────────────────────────────────────────────
-- ستٌّ وثلاثون قيمة، نظير eyework/money.py BUDGET_VALUES؛ اختبارٌ يقارنهما
-- على كل عددٍ من صفرٍ إلى ستة آلاف.
CREATE FUNCTION ew_budget_allowed(v integer) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT (v BETWEEN 50 AND 1000 AND v % 50 = 0) OR (v BETWEEN 1250 AND 5000 AND v % 250 = 0)
$$;

-- محاولةٌ ربما فُوترت تُحسب في حدّ اليوم، وما لم يصل المزوّد أو رفضه قبل
-- العمل لا يُحسب: انقطاع الخدمة لا يستهلك حصّة صاحبها. والمحاولة الجارية
-- (أو التي انقطعت عمليّتها) تُحسب احتياطاً.
CREATE FUNCTION ew_is_billable(o text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT o IS NULL OR o NOT IN ('UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE', 'UPSTREAM_ERROR')
$$;

-- لا مقطع تطبيقٍ غير JFIF (APP1–APP15: EXIF وICC وXMP وغيرها) ولا تعليق (COM).
-- هذه الأزواج لا تقع داخل البيانات المضغوطة (كل 0xFF فيها يتبعه 0x00 أو
-- علامة RST)، ولا في جداول المشفّر. فوجودها في أيّ موضع يعني بياناتٍ وصفية
-- نجت من التنظيف — حاجزٌ ثانٍ خلف التطبيق.
CREATE FUNCTION ew_jpeg_has_no_metadata(b bytea) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT bool_and(position(set_byte('\xff00'::bytea, 1, m) IN b) = 0)
      FROM unnest(ARRAY[225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 254]) AS m
$$;

-- ── الجداول ─────────────────────────────────────────────────────────────
CREATE TABLE campaigns (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status              text NOT NULL DEFAULT 'DRAFT' CHECK (status IN
                            ('DRAFT','COPY_PROPOSED','COPY_APPROVED','READY','CANCELLED')),
    -- يزيده المحفّز مع كل تعديل. كل كتابةٍ من التطبيق تشترط القيمة التي
    -- رآها صاحبها، فالضغطة المكرّرة أو التبويب القديم يُرفضان بدل أن يُطبَّقا.
    row_version         integer NOT NULL DEFAULT 1,
    current_version_id  uuid,
    approved_version_id uuid,
    -- ميزانيةٌ إجمالية بالريال الصحيح، ونظيرها eyework/money.py.
    budget_sar          integer CONSTRAINT budget_in_domain CHECK (budget_sar IS NULL OR ew_budget_allowed(budget_sar)),
    days                smallint CONSTRAINT days_in_range CHECK (days IS NULL OR days BETWEEN 1 AND 30),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    approved_at         timestamptz,
    ready_at            timestamptz,
    cancelled_at        timestamptz,
    UNIQUE (id, user_id),
    CONSTRAINT draft_has_no_copy
        CHECK (status <> 'DRAFT' OR current_version_id IS NULL),
    CONSTRAINT copy_states_have_copy
        CHECK (status NOT IN ('COPY_PROPOSED','COPY_APPROVED','READY') OR current_version_id IS NOT NULL),
    CONSTRAINT approval_has_time
        CHECK ((approved_version_id IS NULL) = (approved_at IS NULL)),
    CONSTRAINT approval_matches_status
        CHECK (status = 'CANCELLED'
               OR (status IN ('COPY_APPROVED','READY')) = (approved_version_id IS NOT NULL)),
    CONSTRAINT approved_is_current
        CHECK (approved_version_id IS NULL OR approved_version_id = current_version_id),
    CONSTRAINT ready_is_complete
        CHECK (status <> 'READY' OR (budget_sar IS NOT NULL AND days IS NOT NULL
                                     AND ready_at IS NOT NULL AND approved_version_id IS NOT NULL)),
    CONSTRAINT cancelled_iff_time
        CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL))
);
CREATE INDEX campaigns_user_recent ON campaigns (user_id, updated_at DESC);

-- كل استدعاءٍ للنموذج محاولةٌ تُحسب، نجحت أم فشلت: الفشل يكلّف أيضاً.
CREATE TABLE generation_attempts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id   uuid NOT NULL,
    user_id       uuid NOT NULL,
    kind          text NOT NULL CHECK (kind IN ('INITIAL','EDIT')),
    -- النسخة الحالية لحظة بدء المحاولة. التعديل يُبنى عليها وحدها.
    based_on_version_id uuid,
    -- الصورة التي أُرسلت. النصّ يصف هذه الصورة لا غيرها.
    image_sha256  bytea NOT NULL CHECK (octet_length(image_sha256) = 32),
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    outcome       text CHECK (outcome IN ('OK','UNUSABLE_PHOTO','REFUSED','OUTPUT_INVALID','DISCARDED',
                                          'UPSTREAM_BUSY','UPSTREAM_UNREACHABLE','UPSTREAM_TIMEOUT',
                                          'UPSTREAM_ERROR')),
    input_tokens  integer CHECK (input_tokens >= 0),
    output_tokens integer CHECK (output_tokens >= 0),
    FOREIGN KEY (campaign_id, user_id) REFERENCES campaigns (id, user_id) ON DELETE CASCADE,
    CONSTRAINT finished_iff_outcome CHECK ((finished_at IS NULL) = (outcome IS NULL)),
    CONSTRAINT kind_matches_base CHECK ((kind = 'INITIAL') = (based_on_version_id IS NULL))
);
CREATE INDEX attempts_user_time ON generation_attempts (user_id, started_at DESC);
CREATE INDEX attempts_time      ON generation_attempts (started_at DESC);
CREATE INDEX attempts_campaign  ON generation_attempts (campaign_id);

CREATE TABLE copy_versions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id    uuid NOT NULL,
    user_id        uuid NOT NULL,
    -- بلا CASCADE: حذف محاولةٍ وحدها لا يمحو نصّاً بصمت. الحذف يكون للحملة،
    -- فيمتدّ إلى الاثنين ويُفحص المرجع في نهاية العبارة.
    attempt_id     uuid NOT NULL UNIQUE REFERENCES generation_attempts(id),
    image_sha256   bytea NOT NULL DEFAULT '\x' CHECK (octet_length(image_sha256) = 32),
    -- يكتبهما المحفّز، لا التطبيق.
    version        smallint NOT NULL DEFAULT 0 CONSTRAINT version_cap CHECK (version BETWEEN 1 AND 10),
    based_on_version_id uuid,
    -- الحدود نظير eyework/copy_rules.py.
    title          text NOT NULL CHECK (char_length(title) BETWEEN 8 AND 60
                                        AND strpos(title, chr(10)) = 0 AND strpos(title, chr(13)) = 0),
    description    text NOT NULL CHECK (char_length(description) BETWEEN 40 AND 240),
    edit_presets   text[] NOT NULL DEFAULT '{}'
                   CHECK (edit_presets <@ ARRAY['SHORTER','SIMPLER','MORE_FORMAL','MORE_LIVELY',
                                                'NEW_TITLE','NEW_DESCRIPTION']::text[]
                          AND cardinality(edit_presets) <= 3
                          AND NOT (edit_presets @> ARRAY['MORE_FORMAL','MORE_LIVELY']::text[])
                          AND NOT (edit_presets @> ARRAY['NEW_TITLE','NEW_DESCRIPTION']::text[])),
    edit_note      text CHECK (edit_note IS NULL OR char_length(edit_note) BETWEEN 1 AND 200),
    warnings       text[] NOT NULL DEFAULT '{}'
                   CHECK (warnings <@ ARRAY['PRICE','HEALTH_CLAIM','SUPERLATIVE']::text[]),
    -- النموذج الذي خدم فعلاً — قد يكون البديل من جهة الخادم.
    served_model   text NOT NULL CHECK (served_model ~ '^claude-[a-z0-9.-]{1,57}$'),
    prompt_version text NOT NULL CHECK (prompt_version ~ '^[a-z0-9.-]{1,32}$'),
    api_request_id text CHECK (char_length(api_request_id) <= 128),
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, version),
    UNIQUE (campaign_id, id),
    FOREIGN KEY (campaign_id, user_id) REFERENCES campaigns (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id, based_on_version_id) REFERENCES copy_versions (campaign_id, id),
    CONSTRAINT first_is_fresh CHECK ((version = 1) = (based_on_version_id IS NULL)),
    CONSTRAINT edit_has_reason
        CHECK ((based_on_version_id IS NULL) = (cardinality(edit_presets) = 0 AND edit_note IS NULL))
);

ALTER TABLE campaigns ADD CONSTRAINT current_version_belongs
    FOREIGN KEY (id, current_version_id) REFERENCES copy_versions (campaign_id, id);
ALTER TABLE campaigns ADD CONSTRAINT approved_version_belongs
    FOREIGN KEY (id, approved_version_id) REFERENCES copy_versions (campaign_id, id);
ALTER TABLE generation_attempts ADD CONSTRAINT attempt_base_belongs
    FOREIGN KEY (campaign_id, based_on_version_id) REFERENCES copy_versions (campaign_id, id);

CREATE TABLE campaign_images (
    campaign_id uuid PRIMARY KEY,
    user_id     uuid NOT NULL,
    jpeg        bytea NOT NULL,
    width       smallint NOT NULL CHECK (width  BETWEEN 320 AND 1568),
    height      smallint NOT NULL CHECK (height BETWEEN 320 AND 1568),
    sha256      bytea NOT NULL CHECK (octet_length(sha256) = 32),
    created_at  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (campaign_id, user_id) REFERENCES campaigns (id, user_id) ON DELETE CASCADE,
    CONSTRAINT image_size        CHECK (octet_length(jpeg) BETWEEN 1 AND 3145728),
    CONSTRAINT image_is_jpeg     CHECK (substring(jpeg FROM 1 FOR 3) = '\xffd8ff'::bytea),
    CONSTRAINT image_has_no_metadata CHECK (ew_jpeg_has_no_metadata(jpeg)),
    -- "Exif\0\0" و"http://ns.adobe.com/xap/" في أيّ موضع — حاجزٌ ثالث.
    CONSTRAINT image_has_no_exif CHECK (position('\x457869660000'::bytea IN jpeg) = 0),
    CONSTRAINT image_has_no_xmp  CHECK (position('\x687474703a2f2f6e732e61646f62652e636f6d2f7861702f'::bytea
                                                 IN jpeg) = 0)
);
-- مضغوطةٌ أصلاً؛ ضغطها ثانيةً يكلّف ولا يوفّر.
ALTER TABLE campaign_images ALTER COLUMN jpeg SET STORAGE EXTERNAL;

-- ── المحفّزات ───────────────────────────────────────────────────────────
-- حملةٌ تبدأ مسودة، بلا نصٍّ ولا مال، وعشرون مفتوحةً لكل مستخدم على الأكثر.
CREATE FUNCTION ew_campaign_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.current_version_id IS NOT NULL
       OR NEW.approved_version_id IS NOT NULL OR NEW.budget_sar IS NOT NULL OR NEW.days IS NOT NULL
       OR NEW.approved_at IS NOT NULL OR NEW.ready_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_starts_as_draft';
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
CREATE TRIGGER trg_campaign_insert BEFORE INSERT ON campaigns
    FOR EACH ROW EXECUTE FUNCTION ew_campaign_insert_guard();

CREATE FUNCTION ew_campaign_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
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
CREATE TRIGGER trg_campaign_guard BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION ew_campaign_guard();

-- الإلغاء يحذف الصورة في المعاملة نفسها. بصلاحية المالك لأن دور الويب لا
-- يملك DELETE أصلاً.
CREATE FUNCTION ew_purge_image_on_cancel() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    DELETE FROM campaign_images WHERE campaign_id = NEW.id;
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_purge_image AFTER UPDATE OF status ON campaigns
    FOR EACH ROW WHEN (NEW.status = 'CANCELLED') EXECUTE FUNCTION ew_purge_image_on_cancel();

-- الصورة تُوضع أو تُستبدل والحملة مسودةٌ فقط: بعد أن يُكتب نصٌّ عنها لا
-- تتغيّر تحته.
CREATE FUNCTION ew_image_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
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
CREATE TRIGGER trg_image_guard BEFORE INSERT OR UPDATE ON campaign_images
    FOR EACH ROW EXECUTE FUNCTION ew_image_guard();

-- نسخةٌ لا توجد إلا على محاولةٍ مفتوحة محسوبة، لهذه الحملة وهذا المستخدم،
-- عمرها دون خمس دقائق، ومبنيّةٍ على النسخة المعروضة الآن. رقمها وأساسها
-- و«أبقِ الحقل الآخر» تُفرض هنا.
CREATE FUNCTION ew_version_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
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
CREATE TRIGGER trg_version_insert BEFORE INSERT ON copy_versions
    FOR EACH ROW EXECUTE FUNCTION ew_version_insert_guard();

-- أحدث نسخةٍ هي المعروضة دائماً، وهي وحدها ما يمكن اعتماده.
CREATE FUNCTION ew_version_becomes_current() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    UPDATE campaigns SET current_version_id = NEW.id, status = 'COPY_PROPOSED'
     WHERE id = NEW.campaign_id;
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_version_current AFTER INSERT ON copy_versions
    FOR EACH ROW EXECUTE FUNCTION ew_version_becomes_current();

-- ما كُتب لا يُعاد كتابته، ولا للمالك: المحفّزات لا يتجاوزها أحد.
CREATE FUNCTION ew_forbid_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'append-only: %', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
END
$$;
CREATE TRIGGER trg_versions_append_only BEFORE UPDATE ON copy_versions
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();

-- محاولةٌ أُغلقت لا تُعاد فتحاً ولا تُعدَّل نتيجتها.
CREATE FUNCTION ew_attempt_settle_once() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.finished_at IS NOT NULL THEN
        RAISE EXCEPTION 'settled' USING ERRCODE = 'check_violation', CONSTRAINT = 'attempt_settled';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_attempt_settle BEFORE UPDATE ON generation_attempts
    FOR EACH ROW EXECUTE FUNCTION ew_attempt_settle_once();

-- ── سقوف كلفة النموذج ───────────────────────────────────────────────────
-- تُفتح المحاولة قبل الاتصال بالنموذج وفي معاملةٍ مستقلّة، فلا تُحجز أقفالٌ
-- أثناء دقيقةٍ من الانتظار. والقفل على صفّ المستخدم يجعل الفحص والإدراج
-- ذرّيين لكل مستخدم: طلبان متزامنان لا يمرّان معاً.
CREATE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
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

-- تُغلق كل محاولة بنتيجتها. OK تعني نسخةً كُتبت في المعاملة نفسها، ولا
-- نسخة بغير OK.
CREATE FUNCTION ew_finish_generation(
    p_attempt uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
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

REVOKE ALL ON FUNCTION ew_begin_generation(uuid, text, integer, uuid),
                       ew_finish_generation(uuid, text, integer, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_begin_generation(uuid, text, integer, uuid),
                          ew_finish_generation(uuid, text, integer, integer) TO eyework_app;

-- دوالّ القيود تُستدعى بصلاحية من يكتب، فتُمنح لدور الويب وحده لا لـPUBLIC.
REVOKE ALL ON FUNCTION ew_budget_allowed(integer), ew_is_billable(text), ew_jpeg_has_no_metadata(bytea)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_budget_allowed(integer), ew_is_billable(text), ew_jpeg_has_no_metadata(bytea)
    TO eyework_app;

-- دوالّ المحفّزات لا يستدعيها أحدٌ مباشرة.
REVOKE ALL ON FUNCTION ew_campaign_insert_guard(), ew_campaign_guard(), ew_purge_image_on_cancel(),
                       ew_image_guard(), ew_version_insert_guard(), ew_version_becomes_current(),
                       ew_forbid_update(), ew_attempt_settle_once() FROM PUBLIC;

-- ── العزل بالصفّ: ENABLE + FORCE ─────────────────────────────────────────
-- السياسة تقارن بقيمةٍ يضبطها التطبيق داخل كل معاملة. بلا قيمةٍ لا صفّ:
-- `ew_current_user()` تُرجع NULL، والمقارنة بـNULL لا تُرجع شيئاً.
ALTER TABLE campaigns           ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns           FORCE  ROW LEVEL SECURITY;
ALTER TABLE generation_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_attempts FORCE  ROW LEVEL SECURITY;
ALTER TABLE copy_versions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE copy_versions       FORCE  ROW LEVEL SECURITY;
ALTER TABLE campaign_images     ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_images     FORCE  ROW LEVEL SECURITY;

CREATE POLICY campaigns_own ON campaigns FOR ALL TO eyework_app
    USING      (user_id = ew_current_user())
    WITH CHECK (user_id = ew_current_user());
CREATE POLICY attempts_own ON generation_attempts FOR ALL TO eyework_app
    USING      (user_id = ew_current_user())
    WITH CHECK (user_id = ew_current_user());
CREATE POLICY versions_own ON copy_versions FOR ALL TO eyework_app
    USING      (user_id = ew_current_user())
    WITH CHECK (user_id = ew_current_user());
CREATE POLICY images_own ON campaign_images FOR ALL TO eyework_app
    USING      (user_id = ew_current_user())
    WITH CHECK (user_id = ew_current_user());

CREATE POLICY campaigns_owner_access ON campaigns           FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY attempts_owner_access  ON generation_attempts FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY versions_owner_access  ON copy_versions       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY images_owner_access    ON campaign_images     FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- ── المنح: بالأعمدة، بلا DELETE ولا TRUNCATE ───────────────────────────
GRANT SELECT ON campaign_transition TO eyework_app;

GRANT SELECT ON campaigns TO eyework_app;
GRANT INSERT (user_id) ON campaigns TO eyework_app;
GRANT UPDATE (status, current_version_id, budget_sar, days) ON campaigns TO eyework_app;

GRANT SELECT ON copy_versions TO eyework_app;
GRANT INSERT (campaign_id, user_id, attempt_id, title, description, edit_presets, edit_note,
              warnings, served_model, prompt_version, api_request_id) ON copy_versions TO eyework_app;

GRANT SELECT ON campaign_images TO eyework_app;
GRANT INSERT (campaign_id, user_id, jpeg, width, height, sha256) ON campaign_images TO eyework_app;
GRANT UPDATE (jpeg, width, height, sha256) ON campaign_images TO eyework_app;

GRANT SELECT ON generation_attempts TO eyework_app;
