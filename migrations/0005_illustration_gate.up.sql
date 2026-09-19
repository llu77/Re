-- ════════════════════════════════════════════════════════════════════════
-- 0005_illustration_gate — التحقق الآلي من الجانب المصاب
-- ════════════════════════════════════════════════════════════════════════
-- القاعدة 4: كل صورة تصل المريض تجتاز تحققاً آلياً من الجانب المصاب، ثم
-- اعتماد ممارس. الصورة الفاشلة تُحجب، ولا مسار تسليم بديل.
--
-- الترحيل 0001 فرض أن `ILLUSTRATION_SET` لا يوجد بلا `affected_side`. وهذا
-- يضمن أن الحقل مملوء، لا أن الصورة تمثّله: قياس مولّدات هذا المستودع أظهر
-- أن ثلاثة منها كانت تستقبل الجانب وتتجاهله، فتُنتج لليمين واليسار الصورةَ
-- نفسها حرفياً. الحقل كان يقول «يمين» والرسم لا يقول شيئاً.
--
-- ما يفرضه هذا الملف:
--   • لا ينتقل `ILLUSTRATION_SET` إلى الطابور ولا إلى الاعتماد بلا صفّ
--     تحقق ناجح، لجانبه هو، **ولبصمة حمولته هي**.
--   • ربط التحقق بالبصمة يُبطله تلقائياً عند أي تعديل للحمولة — فلا يمكن
--     أن يُعتمد رسمٌ غير الذي فُحص. وهذا هو الباب الذي كان يفتحه
--     `edit_and_approve`.
--   • الحجب مسجَّل لا صامت: صفّ `BLOCKED` بسببه يبقى للمراجعة.
-- ════════════════════════════════════════════════════════════════════════

CREATE TABLE illustration_verification (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id    uuid NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,

    -- بصمة الحمولة كما تراها قاعدة البيانات. تُحسب هنا لا في التطبيق:
    -- تمثيل jsonb النصّي مُطبَّع، وإعادة بنائه في بايثون بابُ انحراف صامت.
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),

    side           text NOT NULL CHECK (side IN ('LEFT', 'RIGHT', 'BILATERAL')),
    verdict        text NOT NULL CHECK (verdict IN ('PASS', 'BLOCKED')),

    -- ما قيس فعلاً: الانحياز الأفقي للحبر، من -1 (كله يسار) إلى +1.
    bias           double precision,
    detail         jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason         text,

    verified_by    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    verified_at    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT blocked_needs_a_reason CHECK (
        verdict <> 'BLOCKED' OR nullif(btrim(reason), '') IS NOT NULL),
    CONSTRAINT pass_needs_a_measurement CHECK (
        verdict <> 'PASS' OR bias IS NOT NULL)
);

CREATE INDEX illustration_verification_proposal_idx
    ON illustration_verification (proposal_id, payload_sha256)
    WHERE verdict = 'PASS';

-- سجل واقعة: لا يُعدَّل ولا يُحذف. تصحيح تحقق خاطئ يكون بتحقق جديد.
CREATE FUNCTION forbid_verification_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'سجل التحقق من الصورة غير قابل لـ%', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER trg_verification_immutable
    BEFORE UPDATE OR DELETE ON illustration_verification
    FOR EACH ROW EXECUTE FUNCTION forbid_verification_rewrite();

-- ── البوابة ─────────────────────────────────────────────────────────────
-- تُضاف إلى محفّز الانتقالات نفسه الذي يحمل بوابة الاستشهاد: شرطان على
-- انتقال واحد في موضع واحد، فلا يفترقان مع الوقت.
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
    -- مرتبطٍ ببصمة الحمولة الحالية. الفحص عند كل انتقال لا عند الطابور
    -- وحده، لأن `edit_and_approve` يغيّر الحمولة بعد الطابور.
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

    RETURN NEW;
END
$$;

-- ── الصور تسكن نوعاً واحداً ─────────────────────────────────────────────
-- بوابة التحقق أعلاه تحرس `ILLUSTRATION_SET` وحده. وخطةٌ تحمل رسماً داخل
-- خطوة من خطواتها كانت تصل المريض بلا أي فحص — وهو «مسار التسليم البديل»
-- الذي تمنعه القاعدة 4 نصاً.
--
-- المنع هنا بنيوي: لا ترميم SVG في حمولة أي نوع آخر. فتسكن الصور نوعاً
-- واحداً، وذلك النوع محروس. الخطة تشير إلى الصورة باسم تمرينها، والبوابة
-- تجلبها من المجموعة المعتمدة.
CREATE FUNCTION forbid_unguarded_illustration() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind <> 'ILLUSTRATION_SET' AND NEW.payload::text ~* '<svg' THEN
        RAISE EXCEPTION 'رسمٌ داخل حمولة % لا تمر ببوابة التحقق', NEW.kind
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER trg_illustrations_live_in_one_kind
    BEFORE INSERT OR UPDATE OF payload ON proposals
    FOR EACH ROW EXECUTE FUNCTION forbid_unguarded_illustration();

-- ── الصلاحيات وعزل الصفوف ───────────────────────────────────────────────
GRANT SELECT, INSERT ON illustration_verification TO app_practitioner;
REVOKE ALL ON illustration_verification FROM app_patient;

ALTER TABLE illustration_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE illustration_verification FORCE  ROW LEVEL SECURITY;

-- التحقق يُرى متى رُئي مقترحه — العزل موروث من `proposals` لا منسوخ عنها.
CREATE POLICY illustration_verification_follow_proposal ON illustration_verification
    FOR ALL TO app_practitioner
    USING      (EXISTS (SELECT 1 FROM proposals p WHERE p.id = proposal_id))
    WITH CHECK (EXISTS (SELECT 1 FROM proposals p WHERE p.id = proposal_id));

CREATE POLICY illustration_verification_owner_access ON illustration_verification
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
