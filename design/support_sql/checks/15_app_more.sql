\set ON_ERROR_STOP 1
CREATE TEMP TABLE IF NOT EXISTS results (n serial, name text, ok boolean, info text);
CREATE OR REPLACE FUNCTION pg_temp.expect(p_name text, p_sql text, p_want text) RETURNS void
LANGUAGE plpgsql AS $f$
DECLARE c text; s text; m text;
BEGIN
  BEGIN
    EXECUTE p_sql; EXECUTE 'SET CONSTRAINTS ALL IMMEDIATE';
    INSERT INTO results (name, ok, info) VALUES (p_name, false, 'no error');
  EXCEPTION WHEN others THEN
    GET STACKED DIAGNOSTICS c = CONSTRAINT_NAME, s = RETURNED_SQLSTATE, m = MESSAGE_TEXT;
    INSERT INTO results (name, ok, info) VALUES (p_name, coalesce(c,'')=p_want OR s=p_want OR m LIKE '%'||p_want||'%', coalesce(c,'')||' '||s||' '||m);
  END;
END $f$;
CREATE OR REPLACE FUNCTION pg_temp.check(p_name text, p_ok boolean, p_info text) RETURNS void
LANGUAGE sql AS $f$ INSERT INTO results (name, ok, info) VALUES (p_name, coalesce(p_ok,false), p_info) $f$;
SELECT set_config('eyework.user_id', '11111111-1111-1111-1111-111111111111', false);
SELECT id AS t1 FROM support_tickets WHERE number = 1 \gset
-- proposal from a ticket with a sent reply
SELECT ew_kb_begin_proposal(:'t1') AS c5 \gset
SELECT ew_kb_record_proposal(:'c5', 'الأضواء الحمراء في الموجّه بعد إعادة تشغيله',
  'الموجّه أضواؤه حمراء والإنترنت مقطوع بعد إعادة التشغيل', NULL,
  '1. تأكّد من توصيل سلك الخط بالموجّه. 2. أعد تشغيله مرةً واحدة. 3. إن بقيت الأضواء حمراء فالمشكلة في الخط: صعّد التذكرة إلى مزوّد الخدمة.',
  NULL, 120, 300, 'claude-opus-5-5', 'kbprop-2026-10-09.1', 'req_5') AS a2 \gset
SELECT pg_temp.check('AI proposal stored as PROPOSED v1 origin AI', a.state='PROPOSED' AND v.origin='AI' AND v.call_id IS NOT NULL, a.state) FROM kb_articles a JOIN kb_versions v ON v.article_id=a.id WHERE a.id = :'a2';
SELECT pg_temp.check('proposal invisible to drafting search', count(*)=0, count(*)::text) FROM ew_kb_search('الأضواء الحمراء الموجّه', 5) WHERE article_id = :'a2';
-- AI review of the proposal before publish
SELECT ew_kb_begin_review(:'a2', 1::smallint) AS c6 \gset
SELECT pg_temp.expect('publish while article review running refused', format($$SELECT ew_kb_publish(%L, (SELECT row_version FROM kb_articles WHERE id=%L), 1::smallint)$$, :'a2', :'a2'), 'support_review_waiting');
SELECT ew_kb_record_review(:'c6', '[{"code":"UNCLEAR_STEPS","evidence":"أعد تشغيله مرةً واحدة"}]'::jsonb, 60, 30, 'claude-opus-5-5', 'kbreview-2026-10-09.1', 'req_6');
SELECT pg_temp.expect('publish with open article flag refused', format($$SELECT ew_kb_publish(%L, (SELECT row_version FROM kb_articles WHERE id=%L), 1::smallint)$$, :'a2', :'a2'), 'support_flags_open');
SELECT ew_support_ack_flag((SELECT id FROM support_flags WHERE article_id = :'a2' AND state='OPEN'), 'HEEDED', NULL);
-- employee edits → v2 becomes DRAFT, publish v2
SELECT ew_kb_add_version(:'a2', (SELECT row_version FROM kb_articles WHERE id = :'a2'), 'الأضواء الحمراء في الموجّه بعد إعادة تشغيله',
  'الموجّه أضواؤه حمراء والإنترنت مقطوع بعد إعادة التشغيل', NULL,
  '1. تأكّد من توصيل سلك الخط بالموجّه جيداً. 2. افصل الموجّه عن الكهرباء ثلاثين ثانية ثم أعد توصيله. 3. إن بقيت الأضواء حمراء فالمشكلة في الخط: صعّد التذكرة إلى مزوّد الخدمة.',
  NULL) AS v2 \gset
SELECT pg_temp.check('employee edit turns PROPOSED into DRAFT v2', state='DRAFT' AND latest_version=2, state) FROM kb_articles WHERE id = :'a2';
SELECT pg_temp.expect('publishing an older version refused', format($$SELECT ew_kb_publish(%L, (SELECT row_version FROM kb_articles WHERE id=%L), 1::smallint)$$, :'a2', :'a2'), 'stale_row_version');
SELECT ew_kb_publish(:'a2', (SELECT row_version FROM kb_articles WHERE id = :'a2'), 2::smallint);
SELECT pg_temp.check('published v2 visible to search', count(*)=1, count(*)::text) FROM ew_kb_search('الأضواء حمراء', 5) WHERE article_id = :'a2';
-- archive removes from search
SELECT ew_kb_set_state(:'a2', (SELECT row_version FROM kb_articles WHERE id = :'a2'), 'ARCHIVED');
SELECT pg_temp.check('archived article not searchable', count(*)=0, count(*)::text) FROM ew_kb_search('الأضواء حمراء', 5) WHERE article_id = :'a2';
-- a second proposal left untouched (exercises purge: PROPOSED → DISCARDED → deleted)
SELECT ew_kb_begin_proposal(:'t1') AS c7 \gset
SELECT ew_kb_record_proposal(:'c7', 'إعادة تشغيل الموجّه حين ينقطع الإنترنت',
  'الإنترنت مقطوع عن كل أجهزة المكتب', NULL,
  '1. افصل الموجّه عن الكهرباء ثلاثين ثانية. 2. أعد توصيله وانتظر دقيقتين حتى تثبت أضواؤه.',
  NULL, 100, 200, 'claude-opus-5-5', 'kbprop-2026-10-09.1', 'req_7') AS a3 \gset
SELECT pg_temp.expect('third proposal from the same ticket refused', format($$SELECT ew_kb_begin_proposal(%L)$$, :'t1'), 'kb_ticket_proposal_cap');
SELECT n, CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END, name, CASE WHEN ok THEN '' ELSE info END FROM results ORDER BY n;
