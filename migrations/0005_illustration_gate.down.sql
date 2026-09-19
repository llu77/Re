-- ════════════════════════════════════════════════════════════════════════
-- 0005_illustration_gate — تراجع
-- ════════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS trg_illustrations_live_in_one_kind ON proposals;
DROP FUNCTION IF EXISTS forbid_unguarded_illustration();
DROP TRIGGER IF EXISTS trg_verification_immutable ON illustration_verification;
DROP FUNCTION IF EXISTS forbid_verification_rewrite();
DROP TABLE IF EXISTS illustration_verification;

-- استعادة محفّز الانتقالات كما عرّفه الترحيل 0004: بوابة الاستشهاد بلا
-- بوابة الصور.
CREATE OR REPLACE FUNCTION enforce_proposal_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
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

    RETURN NEW;
END
$$;
