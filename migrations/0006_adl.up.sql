-- ════════════════════════════════════════════════════════════════════════
-- 0006_adl — وحدتا النشاط اليومي: اللبس والمطبخ المتدرّج
-- ════════════════════════════════════════════════════════════════════════
-- معيار القبول 5: «اختبار يثبت أن مستوى مطبخ غير مصرَّح به لا يمكن فتحه بأي
-- مسار». ولا مستوياتٍ في المستودع ولا تفويض، فهذا الملف يُنشئ الاثنين
-- ويفرضهما حيث لا تُلتَفّ: في الصلاحيات وفي العرض، لا في الواجهة.
--
-- ثلاث ضمانات:
--   • المطبخ مُدرَّج، وكل مستوى يُفوَّض وحده. تفويض مستوىً لا يفتح ما تحته
--     ولا ما فوقه، ودور المريض لا يملك صلاحية على جدول التفويض أصلاً.
--   • المستويات الحرارية تُعلَّق ما دام هناك بلاغ علامة حمراء لم يستلمه
--     إنسان — **شرطَ قراءةٍ لا كتابةَ صفّ**. لو كان سحباً تلقائياً لكان
--     النظام قد قرّر، وهو لا يقرر؛ وكشرطِ قراءة يرتفع في اللحظة التي يستلم
--     فيها الممارس البلاغ، ولا يمكن أن يُنسى مرفوعاً.
--   • برنامج لبسٍ يخالف الترتيب السريري لا يدخل طابور المراجعة: الفحص
--     مربوط ببصمة الحمولة كما في بوابة الصور، فتعديلها يُبطله تلقائياً.
--
-- ما لا يفرضه هذا الملف، وقراراً معلناً: **لا تسلسل بين المستويات.** تفويض
-- المستوى 4 بلا 1-3 ممكن. النظام يقترح ولا يقرر، والممارس المرخَّص هو من
-- يقرر ويسجّل أساسه في `basis`.
-- ════════════════════════════════════════════════════════════════════════

-- ── تدرّج المطبخ ────────────────────────────────────────────────────────
-- `suspends_on_red_flag` عمودٌ لا رقمُ مستوى مكتوب في شرط العرض: سياسة
-- التعليق تُقرأ في صفّها، فيراها من يقرأ الجدول ويغيّرها ترحيلٌ يُراجَع،
-- بدل `tier < 3` مدفونة في تعريف عرض لا ينظر فيه أحد.
CREATE TABLE kitchen_tier (
    tier                 smallint PRIMARY KEY CHECK (tier BETWEEN 1 AND 4),
    label_ar             text NOT NULL,
    hazard               text NOT NULL,
    suspends_on_red_flag boolean NOT NULL
);

INSERT INTO kitchen_tier (tier, label_ar, hazard, suspends_on_red_flag) VALUES
    (1, 'تحضير بارد: بلا أداة حادّة وبلا حرارة',
        'لا حرارة ولا حدّ — الخطر انزلاق أو إجهاد وقوف', false),
    (2, 'أدوات حادّة بلا حرارة',
        'الجرح والقطع', false),
    (3, 'حرارة: موقد أو فرن أو ميكروويف',
        'الحرق والحريق وانسكاب السوائل الساخنة', true),
    (4, 'طبخ كامل مستقل',
        'حرارة وحدّ وتعدّد مهام متزامن بلا إشراف', true);

-- ── كتالوج المهام ───────────────────────────────────────────────────────
-- كتالوج ثابت في الترحيل لا جدولٌ يُحرَّر: إضافة مهمة تعديلُ ملف يُراجَع
-- كشيفرة، لأن المهمة تحمل خطراً وتُفتح بتفويض.
CREATE TABLE adl_task (
    code     text PRIMARY KEY,
    module   text NOT NULL CHECK (module IN ('DRESSING', 'KITCHEN')),
    tier     smallint REFERENCES kitchen_tier(tier) ON DELETE RESTRICT,
    label_ar text NOT NULL,
    hazard   text,

    -- المطبخ وحده مُدرَّج: مهمة مطبخ بلا مستوى تفلت من التفويض، ومهمة لبس
    -- بمستوى تدّعي تدرّجاً لا يفرضه شيء.
    CONSTRAINT kitchen_is_tiered CHECK ((module = 'KITCHEN') = (tier IS NOT NULL))
);

INSERT INTO adl_task (code, module, tier, label_ar, hazard) VALUES
    ('KITCHEN_COLD_PREP',  'KITCHEN', 1,
     'إعداد وجبة باردة: شطيرة أو سلطة جاهزة التقطيع',
     'الوقوف الطويل وانزلاق الأرضية'),
    ('KITCHEN_KNIFE_PREP', 'KITCHEN', 2,
     'تقطيع الخضار بسكين على لوح مثبَّت',
     'الجرح، وانزلاق اللوح تحت يدٍ واحدة'),
    ('KITCHEN_STOVETOP',   'KITCHEN', 3,
     'تسخين على الموقد: بيض أو شوربة',
     'الحرق، وانسكاب سائل ساخن أثناء النقل'),
    ('KITCHEN_FULL_MEAL',  'KITCHEN', 4,
     'طبخ وجبة كاملة من عدة مكوّنات',
     'حرارة وحدّ ومتابعة عدة أوانٍ في آن'),

    ('DRESS_UPPER', 'DRESSING', NULL,
     'لبس القطعة العلوية وخلعها', 'شدّ الكتف المصاب داخل كمّ مشدود'),
    ('DRESS_LOWER', 'DRESSING', NULL,
     'لبس القطعة السفلية وخلعها', 'فقدان التوازن عند الوقوف على قدم واحدة'),
    ('DRESS_FOOTWEAR', 'DRESSING', NULL,
     'الجوارب والحذاء', 'الانحناء الطويل ودوار الانتصاب');

-- ── التفويض ─────────────────────────────────────────────────────────────
CREATE TABLE kitchen_authorization (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES tenants(id)      ON DELETE RESTRICT,
    patient_id uuid NOT NULL REFERENCES patients(id)     ON DELETE RESTRICT,
    tier       smallint NOT NULL REFERENCES kitchen_tier(tier) ON DELETE RESTRICT,

    -- على أي أساس سريري فُوِّض هذا المستوى لهذا المريض. تفويضٌ بلا أساس
    -- قرارٌ بلا سبب، ولا يُراجَع بعد شهر لأنه لا يقول شيئاً.
    basis      text NOT NULL,

    granted_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    granted_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    revoked_by uuid REFERENCES users(id) ON DELETE RESTRICT,

    CONSTRAINT basis_is_not_blank
        CHECK (nullif(btrim(basis), '') IS NOT NULL),
    CONSTRAINT revocation_is_complete
        CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
    CONSTRAINT revoked_after_granted
        CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);

-- تفويض فاعل واحد لكل مستوى. الصفّ الثاني يفشل أمام الممارس بدل أن يصير
-- «أيّ التفويضين؟» سؤالاً يُجاب عليه بالتخمين عند القراءة.
CREATE UNIQUE INDEX one_active_grant_per_tier
    ON kitchen_authorization (patient_id, tier) WHERE revoked_at IS NULL;

CREATE INDEX kitchen_authorization_patient_idx
    ON kitchen_authorization (patient_id) WHERE revoked_at IS NULL;

-- المفاتيح الخارجية لا تقول شيئاً عن الدور ولا عن المستأجر، وفحصها يتجاوز
-- عزل الصفوف أصلاً. بلا هذا المحفّز يصير معرّف مستخدمٍ مخمَّن تفويضاً.
--
-- الدور `PRACTITIONER` لا `ADMIN`: قيد على `users` يمنع ممارساً بلا رقم
-- ترخيص، فاشتراط الدور هنا اشتراطُ ترخيصٍ فعلي لا مجرد صلاحية إدارية.
CREATE FUNCTION check_kitchen_authorization() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    granter_role   text;
    granter_tenant uuid;
    patient_tenant uuid;
BEGIN
    SELECT role, tenant_id INTO granter_role, granter_tenant
    FROM users WHERE id = NEW.granted_by;

    IF granter_role IS DISTINCT FROM 'PRACTITIONER' THEN
        RAISE EXCEPTION 'التفويض قرار ممارس مرخَّص لا %', coalesce(granter_role, 'مستخدم مجهول')
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT tenant_id INTO patient_tenant FROM patients WHERE id = NEW.patient_id;

    IF patient_tenant IS DISTINCT FROM NEW.tenant_id
       OR granter_tenant IS DISTINCT FROM NEW.tenant_id THEN
        RAISE EXCEPTION 'الممارس والمريض والتفويض يجب أن يكونوا في مستأجر واحد'
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER trg_kitchen_authorization_is_sound
    BEFORE INSERT ON kitchen_authorization
    FOR EACH ROW EXECUTE FUNCTION check_kitchen_authorization();

-- التفويض سجل واقعة: لا يُعاد كتابته ولا يُحذف. المتغيّر الوحيد هو السحب،
-- ومرة واحدة. تصحيح تفويض خاطئ يكون بسحبه ومنح تفويض جديد بأساسه.
CREATE FUNCTION forbid_kitchen_authorization_rewrite() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    revoker_role text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'صفّ تفويض المطبخ غير قابل للحذف'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.tenant_id  IS DISTINCT FROM OLD.tenant_id
       OR NEW.patient_id IS DISTINCT FROM OLD.patient_id
       OR NEW.tier     IS DISTINCT FROM OLD.tier
       OR NEW.basis    IS DISTINCT FROM OLD.basis
       OR NEW.granted_by IS DISTINCT FROM OLD.granted_by
       OR NEW.granted_at IS DISTINCT FROM OLD.granted_at THEN
        RAISE EXCEPTION 'لا يُعدَّل من صفّ التفويض إلا سحبه'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF OLD.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'التفويض مسحوب بالفعل ولا يُعاد'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.revoked_by IS NOT NULL THEN
        SELECT role INTO revoker_role FROM users WHERE id = NEW.revoked_by;
        IF revoker_role IS DISTINCT FROM 'PRACTITIONER' THEN
            RAISE EXCEPTION 'السحب قرار ممارس مرخَّص لا %',
                coalesce(revoker_role, 'مستخدم مجهول')
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER trg_kitchen_authorization_immutable
    BEFORE UPDATE OR DELETE ON kitchen_authorization
    FOR EACH ROW EXECUTE FUNCTION forbid_kitchen_authorization_rewrite();

-- كل منح وكل سحب في السجل غير القابل للتزوير، بمستواه وأساسه.
CREATE FUNCTION audit_kitchen_authorization_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    acting uuid := nullif(current_setting('app.actor_id', true), '')::uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action,
                               to_status, reason, detail)
        VALUES (coalesce(acting, NEW.granted_by), NEW.tenant_id,
                'kitchen_authorization', NEW.id, 'GRANT', 'ACTIVE', NEW.basis,
                jsonb_build_object('patient_id', NEW.patient_id, 'tier', NEW.tier));
    ELSIF OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action,
                               from_status, to_status, detail)
        VALUES (coalesce(acting, NEW.revoked_by), NEW.tenant_id,
                'kitchen_authorization', NEW.id, 'REVOKE', 'ACTIVE', 'REVOKED',
                jsonb_build_object('patient_id', NEW.patient_id, 'tier', NEW.tier));
    END IF;
    RETURN NULL;
END
$$;

CREATE TRIGGER trg_kitchen_authorization_audit
    AFTER INSERT OR UPDATE ON kitchen_authorization
    FOR EACH ROW EXECUTE FUNCTION audit_kitchen_authorization_change();

-- ── فحص برنامج اللبس ────────────────────────────────────────────────────
-- الشكل نفسه الذي يحمله `illustration_verification`: الحكم مربوط ببصمة
-- الحمولة، فتعديلها يُبطله بلا تدخّل.
--
-- ملاحظة تصميم: هذا ثاني جدول تحقق بهذا الشكل. اثنان مصادفة وثالثٌ نمط —
-- إن ظهر فحصٌ ثالث تُدمَج الثلاثة في `payload_verification` بعمود
-- `check_name`. لا يُعمَّم الآن: تعميمٌ على مثالين يخمّن الثالث.
CREATE TABLE dressing_verification (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id    uuid NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,

    -- تُحسب في قاعدة البيانات لا في التطبيق: تمثيل jsonb النصّي مُطبَّع
    -- بقواعدها، وإعادة بنائه في بايثون تطبيعٌ ثانٍ يفترق يوماً ما بصمت.
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),

    verdict        text NOT NULL CHECK (verdict IN ('PASS', 'BLOCKED')),
    detail         jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason         text,

    verified_by    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    verified_at    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT blocked_needs_a_reason CHECK (
        verdict <> 'BLOCKED' OR nullif(btrim(reason), '') IS NOT NULL)
);

CREATE INDEX dressing_verification_proposal_idx
    ON dressing_verification (proposal_id, payload_sha256)
    WHERE verdict = 'PASS';

CREATE FUNCTION forbid_dressing_verification_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'سجل فحص برنامج اللبس غير قابل لـ%', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER trg_dressing_verification_immutable
    BEFORE UPDATE OR DELETE ON dressing_verification
    FOR EACH ROW EXECUTE FUNCTION forbid_dressing_verification_rewrite();

-- ── البوابة ─────────────────────────────────────────────────────────────
-- تُضاف إلى محفّز الانتقالات نفسه الذي يحمل بوابتَي الاستشهاد والصور: كل
-- شرطٍ على انتقالٍ في موضع واحد، فلا تفترق الشروط مع الوقت ولا يُنسى أحدها.
CREATE OR REPLACE FUNCTION enforce_proposal_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    payload_hash text;
BEGIN
    IF OLD.status = NEW.status THEN
        IF NOT EXISTS (SELECT 1 FROM proposal_transition WHERE from_status = OLD.status) THEN
            RAISE EXCEPTION 'حالة نهائية غير قابلة للتعديل: %', OLD.status
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM proposal_transition
        WHERE from_status = OLD.status AND to_status = NEW.status
    ) THEN
        RAISE EXCEPTION 'انتقال غير مسموح: % ← %', OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;

    -- القاعدة 3: بلا مصدر مسترجَع لا يدخل المقترح طابور المراجعة أصلاً.
    IF NEW.status = 'PENDING'
       AND EXISTS (SELECT 1 FROM evidence_required_kind WHERE kind = NEW.kind)
       AND NOT EXISTS (SELECT 1 FROM proposal_citations WHERE proposal_id = NEW.id)
    THEN
        RAISE EXCEPTION 'لا يدخل طابور المراجعة مقترح بلا استشهاد (%)', NEW.kind
            USING ERRCODE = 'check_violation';
    END IF;

    -- القاعدة 4: الصورة لا تتقدّم خطوةً واحدة بلا تحقق ناجح من جانبها،
    -- مرتبطٍ ببصمة الحمولة الحالية.
    IF NEW.kind = 'ILLUSTRATION_SET'
       AND NEW.status IN ('PENDING', 'APPROVED', 'EDITED_APPROVED')
    THEN
        payload_hash := encode(sha256(convert_to(NEW.payload::text, 'UTF8')), 'hex');

        IF NOT EXISTS (
            SELECT 1 FROM illustration_verification v
            WHERE v.proposal_id = NEW.id
              AND v.verdict = 'PASS'
              AND v.side = NEW.affected_side
              AND v.payload_sha256 = payload_hash
        ) THEN
            RAISE EXCEPTION
                'الصورة لم تجتز التحقق الآلي من الجانب % — محجوبة', NEW.affected_side
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    -- برنامج اللبس: الترتيب السريري شرطُ دخولٍ لا ملاحظةُ مراجعة. الفحص
    -- عند كل انتقال لا عند الطابور وحده، لأن `edit_and_approve` يغيّر
    -- الحمولة بعد الطابور.
    IF NEW.payload->>'module' = 'DRESSING'
       AND NEW.status IN ('PENDING', 'APPROVED', 'EDITED_APPROVED')
    THEN
        payload_hash := encode(sha256(convert_to(NEW.payload::text, 'UTF8')), 'hex');

        IF NOT EXISTS (
            SELECT 1 FROM dressing_verification v
            WHERE v.proposal_id = NEW.id
              AND v.verdict = 'PASS'
              AND v.payload_sha256 = payload_hash
        ) THEN
            RAISE EXCEPTION 'برنامج اللبس لم يجتز فحص الترتيب — محجوب'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NEW;
END
$$;

-- ── برنامج اللبس يُعلن عن نفسه ──────────────────────────────────────────
-- البوابة أعلاه تحرس ما يقول `module = 'DRESSING'`. وحمولةٌ تحمل خطوات لبس
-- ولا تقولها تمرّ بلا فحص — وهو «مسار التسليم البديل» الذي تُغلقه القاعدة.
--
-- المنع بنيوي كما في الصور: خطوات `DON`/`DOFF` لا تسكن إلا حمولةً معلنة،
-- فما يحمل الخطوات محروس بالضرورة لا بالاتفاق.
CREATE FUNCTION forbid_undeclared_dressing() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF coalesce(NEW.payload->>'module', '') <> 'DRESSING'
       AND jsonb_typeof(NEW.payload->'steps') = 'array'
       AND EXISTS (
           SELECT 1 FROM jsonb_array_elements(NEW.payload->'steps') AS step
           WHERE jsonb_typeof(step) = 'object' AND step->>'action' IN ('DON', 'DOFF')
       )
    THEN
        RAISE EXCEPTION 'خطوات لبس في حمولة لا تعلن module = DRESSING — لا تمر ببوابة الترتيب'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER trg_dressing_declares_itself
    BEFORE INSERT OR UPDATE OF payload ON proposals
    FOR EACH ROW EXECUTE FUNCTION forbid_undeclared_dressing();

-- ── نقطة العبور إلى المريض ──────────────────────────────────────────────
-- نظير `patient_deliverable_v`: المريض يرى ما يجوز فتحه، ولا يرى أن هناك
-- ما لا يجوز. مهمةٌ غير مفوَّضة لا تظهر معطَّلة — لا تظهر أصلاً. زرٌّ
-- معطَّل يخبر المريض أن شيئاً يُمنع عنه، وهي معلومة ليست له ولا تنفعه.
CREATE VIEW patient_adl_task_v WITH (security_barrier) AS
SELECT
    t.code,
    t.module,
    t.tier,
    t.label_ar,
    t.hazard,
    k.label_ar AS tier_label_ar
FROM adl_task t
LEFT JOIN kitchen_tier k ON k.tier = t.tier
WHERE
    -- سياق غائب ⇒ لا شيء، كما في `patient_deliverable_v`. كتالوج اللبس ليس
    -- بيانات مريض، لكن «الفشل مغلق» خاصية تُحفظ في كل عروض المريض أو لا
    -- تكون خاصية: استدعاءٌ ينسى السياق يجب أن يعود فارغاً لا ناقصاً —
    -- فالفارغ يُلاحَظ، والناقص يُصدَّق.
    nullif(current_setting('app.patient_id', true), '')::uuid IS NOT NULL
    AND (
        t.module = 'DRESSING'
        OR (
            EXISTS (
                SELECT 1 FROM kitchen_authorization a
                WHERE a.patient_id = nullif(current_setting('app.patient_id', true), '')::uuid
                  AND a.tier = t.tier
                  AND a.revoked_at IS NULL
            )
            AND NOT (
                k.suspends_on_red_flag
                AND EXISTS (
                    SELECT 1 FROM red_flag_reports r
                    WHERE r.patient_id = nullif(current_setting('app.patient_id', true), '')::uuid
                      AND r.acknowledged_at IS NULL
                )
            )
        )
    );

-- ── الصلاحيات ───────────────────────────────────────────────────────────
-- المريض: العرض فقط. لا صلاحية على الكتالوج ولا على التفويض، فالمسار
-- الالتفافي مستحيل لا ممنوع.
REVOKE ALL ON adl_task, kitchen_tier, kitchen_authorization, dressing_verification
    FROM app_patient;
GRANT SELECT ON patient_adl_task_v TO app_patient;

GRANT SELECT ON adl_task, kitchen_tier TO app_practitioner;
GRANT SELECT, INSERT, UPDATE ON kitchen_authorization TO app_practitioner;
GRANT SELECT, INSERT ON dressing_verification TO app_practitioner;

-- ── عزل الصفوف ──────────────────────────────────────────────────────────
-- الكتالوج والتدرّج بلا مستأجر ولا عزل: قائمتان ثابتتان لا تحملان بيانات
-- مريض. التفويض والفحص يحملانها، فيُعزلان.
ALTER TABLE kitchen_authorization ENABLE ROW LEVEL SECURITY;
ALTER TABLE kitchen_authorization FORCE  ROW LEVEL SECURITY;
ALTER TABLE dressing_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE dressing_verification FORCE  ROW LEVEL SECURITY;

CREATE POLICY kitchen_authorization_tenant_scope ON kitchen_authorization
    FOR ALL TO app_practitioner
    USING      (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY kitchen_authorization_owner_access ON kitchen_authorization
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- الفحص يُرى متى رُئي مقترحه — العزل موروث من `proposals` لا منسوخ عنها.
CREATE POLICY dressing_verification_follow_proposal ON dressing_verification
    FOR ALL TO app_practitioner
    USING      (EXISTS (SELECT 1 FROM proposals p WHERE p.id = proposal_id))
    WITH CHECK (EXISTS (SELECT 1 FROM proposals p WHERE p.id = proposal_id));

CREATE POLICY dressing_verification_owner_access ON dressing_verification
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
