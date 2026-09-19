-- ════════════════════════════════════════════════════════════════════════
-- 0004_evidence — تراجع
-- ════════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS trg_citation_is_timely ON proposal_citations;

DROP FUNCTION IF EXISTS check_citation_is_timely();
DROP FUNCTION IF EXISTS record_retrieved_source(
    text, text, text, text, text, smallint, text, text, jsonb);

DROP TABLE IF EXISTS proposal_citations;
DROP TABLE IF EXISTS evidence_query_result;
DROP TABLE IF EXISTS evidence_queries;
DROP TABLE IF EXISTS evidence_sources;
DROP TABLE IF EXISTS evidence_required_kind;

-- استعادة محفّز الانتقالات كما عرّفه الترحيل 0001، بلا شرط الاستشهاد.
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

    RETURN NEW;
END
$$;
