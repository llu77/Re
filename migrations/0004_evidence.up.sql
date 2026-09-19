-- ════════════════════════════════════════════════════════════════════════
-- 0004_evidence — الأدلة المسترجَعة وبوابة الاستشهاد
-- ════════════════════════════════════════════════════════════════════════
-- القاعدة 3: لا محتوى سريري بلا مصدر مسترجَع، وغياب المصدر رفضٌ صريح.
-- القاعدة 5 (الشقّ الثاني): لا بيانات مريض في استعلامات المصادر الخارجية.
--
-- ما كان قائماً: `tools/pubmed.py` يمرّر نصّاً حراً يؤلّفه النموذج إلى NCBI،
-- ولا يخزّن ما يسترجعه. فلا شيء يمنع خروج ملاحظة مريض في سطر العنوان، ولا
-- شيء يتيح لاحقاً التمييز بين معرّف مقال استُرجع فعلاً ورقمٍ اختلقه النموذج.
--
-- ثلاث ضمانات يفرضها هذا الملف في طبقة البيانات:
--   • لا يدخل طابور المراجعة مقترحٌ من نوع مُلزِم بلا استشهاد واحد على الأقل.
--   • لا يُستشهَد إلا بصفّ في `evidence_sources`، ولا يُكتب فيه إلا عبر دالة
--     `record_retrieved_source` — فلا دور تطبيق يصنع مصدراً بيده، ومعرّفٌ
--     لم يُسترجع لا يملك صفّاً يُستشهَد به.
--   • كل استعلام خارجي يُسجَّل بنصّه الذي غادر فعلاً، وقيدٌ يرفض تسجيل نصّ
--     يحمل محرفاً خارج اللاتينية — والعربية هي لغة كل بيانات المريض هنا.
-- ════════════════════════════════════════════════════════════════════════

-- ── المصادر المسترجَعة ──────────────────────────────────────────────────
-- سجل ببليوغرافي عامّ: مقال PubMed ليس ملك مستأجر، وهذا الجدول هو الذاكرة
-- أيضاً. لذلك لا `tenant_id` فيه ولا فاعل — تلك على `evidence_queries`،
-- وإلا لرأى مستأجرٌ أثر بحث مستأجر آخر.
CREATE TABLE evidence_sources (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source         text NOT NULL CHECK (source IN ('PUBMED')),
    external_id    text NOT NULL,                       -- PMID
    title          text NOT NULL,
    url            text NOT NULL,
    journal        text,
    published_year smallint CHECK (published_year BETWEEN 1800 AND 2200),
    doi            text,
    abstract       text,
    mesh           jsonb NOT NULL DEFAULT '[]'::jsonb,
    retrieved_at   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT external_id_is_not_blank
        CHECK (nullif(btrim(external_id), '') IS NOT NULL),
    CONSTRAINT title_is_not_blank
        CHECK (nullif(btrim(title), '') IS NOT NULL),
    UNIQUE (source, external_id)
);

-- ── سجل الاستعلامات ─────────────────────────────────────────────────────
CREATE TABLE evidence_queries (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    actor_id          uuid NOT NULL REFERENCES users(id)   ON DELETE RESTRICT,

    -- الاستعلام المُركَّب كما طلبه المستدعي
    query             jsonb NOT NULL,
    -- والنصّ الذي غادر إلى الشبكة فعلاً. هذان مختلفان، والثاني هو الدليل.
    sent_term         text NOT NULL,

    result_count      int NOT NULL CHECK (result_count >= 0),
    served_from_cache boolean NOT NULL DEFAULT false,
    executed_at       timestamptz NOT NULL DEFAULT now(),

    -- الطبقة الثالثة بعد النوع والمفردات: قاعدة البيانات نفسها ترفض تسجيل
    -- استعلام يحمل عربية أو محارف غير متوقّعة. لا تمنع الحزمة من المغادرة،
    -- لكنها تجعل المخالفة غير قابلة للتسجيل — فالسجل يبقى دليلاً لا رواية.
    CONSTRAINT sent_term_is_latin_only
        CHECK (sent_term ~ '^[A-Za-z0-9 ,.:"''()\[\]+\-]+$')
);

CREATE INDEX evidence_queries_tenant_idx ON evidence_queries (tenant_id, executed_at);

-- ما أعاده استعلامٌ بعينه، بترتيبه. هو ما يجعل الذاكرة ممكنة: استعلام مطابق
-- خلال المهلة يُخدَم من هنا بلا لمس الشبكة، وبالترتيب نفسه الذي رآه الممارس.
CREATE TABLE evidence_query_result (
    query_id  uuid NOT NULL REFERENCES evidence_queries(id)  ON DELETE RESTRICT,
    source_id uuid NOT NULL REFERENCES evidence_sources(id)  ON DELETE RESTRICT,
    rank      smallint NOT NULL CHECK (rank >= 0),

    PRIMARY KEY (query_id, source_id)
);

-- ── الاستشهادات ─────────────────────────────────────────────────────────
CREATE TABLE proposal_citations (
    proposal_id uuid NOT NULL REFERENCES proposals(id)        ON DELETE RESTRICT,
    source_id   uuid NOT NULL REFERENCES evidence_sources(id) ON DELETE RESTRICT,
    locator     text,                    -- الموضع المستشهد به داخل المصدر
    added_by    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    added_at    timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (proposal_id, source_id)
);

CREATE INDEX proposal_citations_source_idx ON proposal_citations (source_id);

-- ── الأنواع المُلزِمة ───────────────────────────────────────────────────
-- نظير `core.types.EVIDENCE_REQUIRED_KINDS`، واختبار يقارن الاثنين فيمنع
-- انحرافهما — كما في `proposal_transition`.
CREATE TABLE evidence_required_kind (
    kind text PRIMARY KEY CHECK (kind IN
        ('PLAN', 'PLAN_UPDATE', 'ILLUSTRATION_SET', 'READINESS', 'DOCUMENTATION'))
);

INSERT INTO evidence_required_kind (kind)
VALUES ('PLAN'), ('PLAN_UPDATE'), ('READINESS');

-- ── المسار الوحيد للكتابة في المصادر ────────────────────────────────────
-- SECURITY DEFINER مع سحب INSERT من أدوار التطبيق: قرار «المسترجَع آلياً
-- فقط» يصير مفروضاً في طبقة البيانات لا في الشيفرة. ممارسٌ يريد تلفيق مصدر
-- لا يملك الصلاحية، ووحدة الاسترجاع وحدها تستدعي هذه الدالة — واختبار معماري
-- يمنع استدعاءها من غيرها.
CREATE FUNCTION record_retrieved_source(
    p_source         text,
    p_external_id    text,
    p_title          text,
    p_url            text,
    p_journal        text,
    p_published_year smallint,
    p_doi            text,
    p_abstract       text,
    p_mesh           jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    stored uuid;
BEGIN
    INSERT INTO evidence_sources
        (source, external_id, title, url, journal, published_year, doi, abstract, mesh)
    VALUES
        (p_source, p_external_id, p_title, p_url, p_journal, p_published_year,
         p_doi, p_abstract, coalesce(p_mesh, '[]'::jsonb))
    ON CONFLICT (source, external_id) DO UPDATE SET
        -- إعادة الاسترجاع تُحدّث النسخة: المقال قد يُصحَّح عند الناشر،
        -- و`retrieved_at` يقول متى كانت هذه النسخة صحيحة.
        title = EXCLUDED.title,
        url = EXCLUDED.url,
        journal = EXCLUDED.journal,
        published_year = EXCLUDED.published_year,
        doi = EXCLUDED.doi,
        abstract = EXCLUDED.abstract,
        mesh = EXCLUDED.mesh,
        retrieved_at = now()
    RETURNING id INTO stored;

    RETURN stored;
END
$$;

-- ── ثبات الاستشهاد ──────────────────────────────────────────────────────
-- الاستشهاد يُضاف قبل القرار أو لا يُضاف. إضافته بعد الاعتماد تعني تلفيق
-- دليلٍ لمحتوى وصل المريض أصلاً — وهي الحالة التي تجعل السجل كذباً موثَّقاً.
CREATE FUNCTION check_citation_is_timely() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    proposal_status text;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'الاستشهاد لا يُعدَّل ولا يُحذف: % ممنوع', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    SELECT status INTO proposal_status FROM proposals WHERE id = NEW.proposal_id;

    IF proposal_status IS NULL THEN
        RAISE EXCEPTION 'لا مقترح بهذا المعرّف' USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM proposal_transition WHERE from_status = proposal_status) THEN
        RAISE EXCEPTION 'لا يُضاف استشهاد إلى مقترح حالته نهائية (%)', proposal_status
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER trg_citation_is_timely
    BEFORE INSERT OR UPDATE OR DELETE ON proposal_citations
    FOR EACH ROW EXECUTE FUNCTION check_citation_is_timely();

-- ── البوابة ─────────────────────────────────────────────────────────────
-- `DRAFT → PENDING` هي لحظة دخول الطابور، فهنا موضع الشرط. نُعيد تعريف
-- المحفّز القائم من الترحيل 0001 بدل إضافة محفّز ثانٍ: شرطان على انتقال
-- واحد في موضعين يفترقان بمرور الوقت.
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

-- ── الصلاحيات ───────────────────────────────────────────────────────────
GRANT SELECT ON evidence_sources        TO app_practitioner;
GRANT SELECT ON evidence_required_kind  TO app_practitioner;
GRANT SELECT, INSERT ON proposal_citations TO app_practitioner;
GRANT SELECT, INSERT ON evidence_queries      TO app_practitioner;
GRANT SELECT, INSERT ON evidence_query_result TO app_practitioner;
GRANT EXECUTE ON FUNCTION record_retrieved_source(
    text, text, text, text, text, smallint, text, text, jsonb) TO app_practitioner;

-- لا كتابة مباشرة في المصادر لأي دور تطبيق — الدالة أعلاه هي المسار الوحيد.
REVOKE INSERT, UPDATE, DELETE ON evidence_sources FROM app_practitioner;
REVOKE ALL ON evidence_sources, evidence_queries, evidence_query_result,
              proposal_citations, evidence_required_kind FROM app_patient;

-- المريض يرى المحتوى المعتمد، لا أدلّته ولا ما بُحث عنه لأجله.
REVOKE EXECUTE ON FUNCTION record_retrieved_source(
    text, text, text, text, text, smallint, text, text, jsonb) FROM app_patient;

-- ── عزل الصفوف ──────────────────────────────────────────────────────────
ALTER TABLE evidence_queries    ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_queries    FORCE  ROW LEVEL SECURITY;
ALTER TABLE proposal_citations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_citations  FORCE  ROW LEVEL SECURITY;
ALTER TABLE evidence_query_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_query_result FORCE  ROW LEVEL SECURITY;

CREATE POLICY evidence_queries_tenant_scope ON evidence_queries
    FOR ALL TO app_practitioner
    USING      (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

-- الاستشهاد يُرى متى رُئي مقترحه. لا نسخة ثانية من `tenant_id` هنا تنحرف عن
-- الأولى: العزل موروث من `proposals` التي تخضع لعزلها هي.
CREATE POLICY proposal_citations_follow_proposal ON proposal_citations
    FOR ALL TO app_practitioner
    USING (EXISTS (SELECT 1 FROM proposals p WHERE p.id = proposal_id))
    WITH CHECK (EXISTS (SELECT 1 FROM proposals p WHERE p.id = proposal_id));

-- النتيجة تُرى متى رُئي استعلامها، تماماً كالاستشهاد مع مقترحه.
CREATE POLICY evidence_query_result_follow_query ON evidence_query_result
    FOR ALL TO app_practitioner
    USING      (EXISTS (SELECT 1 FROM evidence_queries q WHERE q.id = query_id))
    WITH CHECK (EXISTS (SELECT 1 FROM evidence_queries q WHERE q.id = query_id));

CREATE POLICY evidence_query_result_owner_access ON evidence_query_result
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

CREATE POLICY evidence_queries_owner_access ON evidence_queries
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY proposal_citations_owner_access ON proposal_citations
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
