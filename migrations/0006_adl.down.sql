-- ════════════════════════════════════════════════════════════════════════
-- 0006_adl — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- الترتيب معكوس عن الصعود: ما يعتمد عليه غيره يسقط أخيراً.

DROP VIEW IF EXISTS patient_adl_task_v;

DROP TRIGGER IF EXISTS trg_dressing_declares_itself ON proposals;
DROP FUNCTION IF EXISTS forbid_undeclared_dressing();

DROP TRIGGER IF EXISTS trg_dressing_verification_immutable ON dressing_verification;
DROP FUNCTION IF EXISTS forbid_dressing_verification_rewrite();
DROP TABLE IF EXISTS dressing_verification;

DROP TRIGGER IF EXISTS trg_kitchen_authorization_audit ON kitchen_authorization;
DROP FUNCTION IF EXISTS audit_kitchen_authorization_change();
DROP TRIGGER IF EXISTS trg_kitchen_authorization_immutable ON kitchen_authorization;
DROP FUNCTION IF EXISTS forbid_kitchen_authorization_rewrite();
DROP TRIGGER IF EXISTS trg_kitchen_authorization_is_sound ON kitchen_authorization;
DROP FUNCTION IF EXISTS check_kitchen_authorization();
DROP TABLE IF EXISTS kitchen_authorization;

DROP TABLE IF EXISTS adl_task;
DROP TABLE IF EXISTS kitchen_tier;

-- استعادة محفّز الانتقالات كما عرّفه الترحيل 0005: بوابتا الاستشهاد والصور
-- بلا بوابة اللبس. إسقاط الجدول وحده يترك الدالة تشير إلى جدول محذوف،
-- فيفشل أول انتقال بعد التراجع بخطأ لا علاقة له بسببه.
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
