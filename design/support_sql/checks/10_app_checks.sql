\set ON_ERROR_STOP 1
-- helper: expect a named constraint (or errcode) from a statement
CREATE TEMP TABLE IF NOT EXISTS results (n serial, name text, ok boolean, info text);
CREATE OR REPLACE FUNCTION pg_temp.expect(p_name text, p_sql text, p_want text) RETURNS void
LANGUAGE plpgsql AS $f$
DECLARE c text; s text; m text;
BEGIN
  BEGIN
    EXECUTE p_sql;
    EXECUTE 'SET CONSTRAINTS ALL IMMEDIATE';
    INSERT INTO results (name, ok, info) VALUES (p_name, false, 'no error');
  EXCEPTION WHEN others THEN
    GET STACKED DIAGNOSTICS c = CONSTRAINT_NAME, s = RETURNED_SQLSTATE, m = MESSAGE_TEXT;
    INSERT INTO results (name, ok, info) VALUES (p_name, coalesce(c,'')=p_want OR s=p_want OR m LIKE '%'||p_want||'%', coalesce(c,'')||' '||s||' '||m);
  END;
END $f$;
CREATE OR REPLACE FUNCTION pg_temp.check(p_name text, p_ok boolean, p_info text) RETURNS void
LANGUAGE sql AS $f$ INSERT INTO results (name, ok, info) VALUES (p_name, coalesce(p_ok,false), p_info) $f$;

-- ── S2 before the desk notice ──
SELECT set_config('eyework.user_id', '22222222-2222-2222-2222-222222222222', false);
SELECT pg_temp.expect('ticket refused before the desk notice',
  $$SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'الطابعة لا تطبع منذ الصباح', 0::smallint)$$, 'support_notice_required');
-- ── as S1 ──
SELECT set_config('eyework.user_id', '11111111-1111-1111-1111-111111111111', false);
SELECT ew_support_accept_notice('2026-10-09');

SELECT pg_temp.expect('web role cannot insert tickets directly',
  $$INSERT INTO support_tickets (user_id, client_token, channel) VALUES ('11111111-1111-1111-1111-111111111111', gen_random_uuid(), 'EMAIL')$$, '42501');
SELECT pg_temp.expect('email in pasted message refused',
  $$SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'راسلني على ali@example.com لو سمحت', 0::smallint)$$, 'support_message_contact_free');
SELECT pg_temp.expect('phone in pasted message refused',
  $$SELECT ew_support_create_ticket(gen_random_uuid(), 'MESSAGING', 'NORMAL', NULL, NULL, NULL, 'جوالي 055 123 4567 اتصل بي', 0::smallint)$$, 'support_message_contact_free');
SELECT pg_temp.expect('phone-like customer label refused',
  $$SELECT ew_support_create_ticket(gen_random_uuid(), 'MESSAGING', 'NORMAL', NULL, '0551234567', NULL, 'الطابعة لا تطبع منذ الصباح', 0::smallint)$$, 'support_customer_label_shape');

-- ticket T1 (KB numbers like KB5034441 survive: 7 digits)
SELECT ew_support_create_ticket('aaaaaaaa-0000-0000-0000-000000000001', 'MESSAGING', 'NORMAL', NULL, 'سارة', NULL,
  'الإنترنت مقطوع عن كل أجهزة المكتب منذ الصباح بعد تحديث KB5034441، ولا أحد يستطيع العمل', 1::smallint) AS t1 \gset
SELECT pg_temp.check('ticket created NEW with number 1 and SLA due', status='NEW' AND number=1 AND first_reply_due_at > now() + interval '7 hours', status||' '||number) FROM support_tickets WHERE id = :'t1';
SELECT pg_temp.check('idempotent create returns same id', ew_support_create_ticket('aaaaaaaa-0000-0000-0000-000000000001', 'MESSAGING', 'NORMAL', NULL, NULL, NULL, 'نصٌّ آخر لا يُحفظ أبداً', 0::smallint) = :'t1', 'same');
SELECT pg_temp.check('one message stored', count(*)=1, count(*)::text) FROM support_messages WHERE ticket_id = :'t1';


-- KB article A1, published
SELECT ew_kb_create('bbbbbbbb-0000-0000-0000-000000000001', 'انقطاع الإنترنت عن المكتب كله',
  'الإنترنت مقطوع عن كل الأجهزة في المكتب', NULL,
  '1. أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية. 2. إن بقي الانقطاع فاتصل بمزوّد الخدمة على الرقم المكتوب على الموجّه.',
  NULL, NULL) AS a1 \gset
SELECT pg_temp.check('article created as DRAFT v1', state='DRAFT' AND latest_version=1 AND number=1, state) FROM kb_articles WHERE id = :'a1';
SELECT pg_temp.expect('publish with stale version refused', format($$SELECT ew_kb_publish(%L, 1, 2::smallint)$$, :'a1'), 'stale_row_version');
SELECT row_version AS a1rv FROM kb_articles WHERE id = :'a1' \gset
SELECT ew_kb_publish(:'a1', :a1rv, 1::smallint);
SELECT pg_temp.check('article published v1', state='PUBLISHED' AND published_version=1, state) FROM kb_articles WHERE id = :'a1';
SELECT pg_temp.expect('national ID in article refused',
  format($$SELECT ew_kb_create(gen_random_uuid(), 'عنوانٌ للتجربة', 'مشكلةٌ في الدخول إلى الحساب', NULL, 'اكتب رقم هويتك 1012345678 في الخانة ثم اضغط دخول', NULL, NULL)$$), 'kb_version_clean');
SELECT pg_temp.check('KB search finds the article by Arabic words', count(*)=1, count(*)::text) FROM ew_kb_search('انقطع الانترنت في المكتب', 3);

-- draft D1 without citation for ANSWER → refused at commit
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT call_id AS c1, based_on_message_id AS m1 FROM ew_support_begin_draft(:'t1', :t1rv) \gset
SELECT pg_temp.expect('ANSWER without citation refused',
  format($$SELECT ew_support_record_draft(%L, 'DRAFT', 'ANSWER', 'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.', 'انقطاع الإنترنت', NULL, 'NETWORK', 'WIDESPREAD', 'STOPPED', false, NULL, 'AR', '{}', NULL, NULL, NULL, 100, 50, 'claude-opus-5-5', 'support-2026-10-09.1', 'req_1')$$, :'c1'),
  'support_answer_needs_citation');
SELECT pg_temp.expect('non-verbatim quote refused',
  format($$SELECT ew_support_record_draft(%L, 'DRAFT', 'ANSWER', 'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.', 'انقطاع الإنترنت', NULL, 'NETWORK', 'WIDESPREAD', 'STOPPED', false, NULL, 'AR', '{}', NULL, NULL, %L::jsonb, 100, 50, 'claude-opus-5-5', 'support-2026-10-09.1', 'req_1')$$,
         :'c1', json_build_array(json_build_object('article_id', :'a1', 'version', 1, 'quote', 'أعد تشغيل الحاسوب مرتين'))::text),
  'support_citation_not_verbatim');
SELECT ew_support_record_draft(:'c1', 'DRAFT', 'ANSWER', 'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.',
  'انقطاع الإنترنت', NULL, 'NETWORK', 'WIDESPREAD', 'STOPPED', false, NULL, 'AR', '{}', NULL, NULL,
  json_build_array(json_build_object('article_id', :'a1', 'version', 1, 'quote', 'أعد تشغيل   الموجّه بفصله عن الكهرباء ثلاثين ثانية'))::jsonb,
  100, 50, 'claude-opus-5-5', 'support-2026-10-09.1', 'req_1') AS d1 \gset
SELECT pg_temp.check('suggested priority computed by trigger = URGENT', suggested_priority='URGENT' AND seq=1, suggested_priority) FROM support_drafts WHERE id = :'d1';
SELECT pg_temp.check('call settled OK', outcome='OK', outcome) FROM support_ai_calls WHERE id = :'c1';
SELECT pg_temp.check('ticket status unchanged by draft', status='NEW', status) FROM support_tickets WHERE id = :'t1';

-- classification: accept suggestion must match; then lower priority → rule flag
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT pg_temp.expect('accepting a suggestion that does not match refused',
  format($$SELECT ew_support_set_ticket(%L, %s, 'NETWORK', 'LOW', 'انقطاع الإنترنت', %L)$$, :'t1', :t1rv, :'d1'), 'support_suggestion_mismatch');
SELECT ew_support_set_ticket(:'t1', :t1rv, 'NETWORK', 'LOW', 'انقطاع الإنترنت', NULL);
SELECT pg_temp.check('priority below suggestion raised a RULE flag', count(*)=1, count(*)::text) FROM support_flags WHERE ticket_id = :'t1' AND code='PRIORITY_BELOW_SUGGESTION' AND state='OPEN';
SELECT pg_temp.check('LOW priority recomputed first reply due (24h)', first_reply_due_at > created_at + interval '23 hours', first_reply_due_at::text) FROM support_tickets WHERE id = :'t1';
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT ew_support_set_ticket(:'t1', :t1rv, 'NETWORK', 'URGENT', 'انقطاع الإنترنت', :'d1');

-- reply AS_IS, release, confirm
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT ew_support_prepare_reply(:'t1', :t1rv, 'cccccccc-0000-0000-0000-000000000001', :'d1', 'ANSWER', false,
  'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.',
  E'مرحباً سارة،\n\nأعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.\n\nفريق الدعم الفني', NULL) AS r1 \gset
SELECT pg_temp.check('origin AS_IS, review NOT_NEEDED, READY', origin='AS_IS' AND review='NOT_NEEDED' AND state='READY', origin||' '||review) FROM support_replies WHERE id = :'r1';
SELECT pg_temp.expect('second live reply on same ticket refused',
  format($$SELECT ew_support_prepare_reply(%L, (SELECT row_version FROM support_tickets WHERE id=%L), gen_random_uuid(), NULL, 'UPDATE', false, 'نعمل على المشكلة الآن وسنعود إليك قريباً.', 'نعمل على المشكلة الآن وسنعود إليك قريباً.', NULL)$$, :'t1', :'t1'),
  'support_one_live_reply');
SELECT pg_temp.expect('release with a different hash refused',
  format($$SELECT ew_support_release_reply(%L, 'COPY', sha256('x'::bytea), false)$$, :'r1'), 'support_reply_hash_mismatch');
SELECT pg_temp.expect('confirm sent before release refused', format($$SELECT ew_support_confirm_reply(%L, true)$$, :'r1'), 'support_reply_transition');
SELECT ew_support_release_reply(:'r1', 'COPY', (SELECT body_sha256 FROM support_replies WHERE id = :'r1'), false);
SELECT ew_support_confirm_reply(:'r1', true);
SELECT pg_temp.check('ANSWER sent → RESOLVED/REPLIED, first reply set', status='RESOLVED' AND resolution='REPLIED' AND first_replied_at IS NOT NULL AND clock_since IS NULL, status) FROM support_tickets WHERE id = :'t1';
SELECT pg_temp.check('agent message equals body', count(*)=1, count(*)::text) FROM support_messages m JOIN support_replies r ON r.id = m.reply_id WHERE m.ticket_id = :'t1' AND m.author='AGENT' AND m.body = r.body;
SELECT pg_temp.check('reuse counted on cited article', reuse_count=1, reuse_count::text) FROM kb_articles WHERE id = :'a1';
SELECT pg_temp.check('status events logged', count(*)>=1, count(*)::text) FROM support_events WHERE ticket_id = :'t1' AND event='STATUS_CHANGED' AND to_status='RESOLVED';

-- customer replies on RESOLVED → OPEN
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT ew_support_add_message(:'t1', :t1rv, 'CUSTOMER', 'جرّبت ولم ينجح، ما زال الانقطاع', 0::smallint, gen_random_uuid());
SELECT pg_temp.check('customer message reopens RESOLVED → OPEN', status='OPEN' AND resolution IS NULL AND resolved_at IS NULL, status) FROM support_tickets WHERE id = :'t1';

-- EDITED reply needs review
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT call_id AS c2 FROM ew_support_begin_draft(:'t1', :t1rv) \gset
SELECT ew_support_record_draft(:'c2', 'CANNOT_ANSWER', 'ASK_INFO', 'هل تظهر أضواء الموجّه كلها باللون الأخضر؟ وما رسالة الخطأ التي تظهر في الحاسوب؟',
  NULL, 'قاعدة المعرفة لا تذكر ما يُفعل إن لم تنفع إعادة التشغيل.', 'NETWORK', 'WIDESPREAD', 'STOPPED', false, 'VENDOR', 'AR', '{}', NULL, NULL, NULL,
  80, 40, 'claude-opus-5-5', 'support-2026-10-09.1', 'req_2') AS d2 \gset
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT pg_temp.expect('reply on old draft refused',
  format($$SELECT ew_support_prepare_reply(%L, %s, gen_random_uuid(), %L, 'ANSWER', false, 'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.', 'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.', NULL)$$, :'t1', :t1rv, :'d1'),
  'support_reply_draft_not_current');
SELECT ew_support_prepare_reply(:'t1', :t1rv, 'cccccccc-0000-0000-0000-000000000002', :'d2', 'ASK_INFO', false,
  'هل تظهر أضواء الموجّه كلها باللون الأخضر؟ وما رسالة الخطأ التي تظهر في الحاسوب بالضبط؟',
  'هل تظهر أضواء الموجّه كلها باللون الأخضر؟ وما رسالة الخطأ التي تظهر في الحاسوب بالضبط؟',
  '[{"code":"NO_QUESTION","evidence":null}]'::jsonb) AS r2 \gset
SELECT pg_temp.check('edited → EDITED, review PENDING', origin='EDITED' AND review='PENDING', origin||' '||review) FROM support_replies WHERE id = :'r2';
SELECT pg_temp.expect('release while review pending refused', format($$SELECT ew_support_release_reply(%L, 'COPY', (SELECT body_sha256 FROM support_replies WHERE id=%L), false)$$, :'r2', :'r2'), 'support_flags_open');
SELECT id AS f0 FROM support_flags WHERE reply_id = :'r2' \gset
SELECT ew_support_ack_flag(:'f0', 'DISMISSED', 'FALSE_ALARM');
SELECT pg_temp.expect('release while review pending refused (no flags)', format($$SELECT ew_support_release_reply(%L, 'COPY', (SELECT body_sha256 FROM support_replies WHERE id=%L), false)$$, :'r2', :'r2'), 'support_review_waiting');
SELECT ew_support_begin_review(:'r2') AS c3 \gset
SELECT pg_temp.expect('AI flag with non-verbatim evidence refused',
  format($$SELECT ew_support_record_review(%L, '[{"code":"TONE","evidence":"أنت المخطئ"}]'::jsonb, 50, 20, 'claude-opus-5-5', 'review-2026-10-09.1', 'req_3')$$, :'c3'), 'support_flag_evidence_verbatim');
SELECT ew_support_record_review(:'c3', '[{"code":"KIND_MISMATCH","evidence":"بالضبط"}]'::jsonb, 50, 20, 'claude-opus-5-5', 'review-2026-10-09.1', 'req_3');
SELECT pg_temp.check('review DONE with one open AI flag', r.review='DONE' AND (SELECT count(*) FROM support_flags f WHERE f.reply_id=r.id AND f.state='OPEN' AND f.source='AI')=1, r.review) FROM support_replies r WHERE id = :'r2';
SELECT pg_temp.expect('release with open AI flag refused', format($$SELECT ew_support_release_reply(%L, 'COPY', (SELECT body_sha256 FROM support_replies WHERE id=%L), false)$$, :'r2', :'r2'), 'support_flags_open');
SELECT ew_support_ack_flag((SELECT id FROM support_flags WHERE reply_id = :'r2' AND state='OPEN'), 'DISMISSED', 'FALSE_ALARM');
SELECT ew_support_release_reply(:'r2', 'SHARE', (SELECT body_sha256 FROM support_replies WHERE id = :'r2'), false);
SELECT ew_support_confirm_reply(:'r2', true);
SELECT pg_temp.check('ASK_INFO sent → PENDING, clock stopped', status='PENDING' AND clock_since IS NULL AND wait_seconds >= 0, status) FROM support_tickets WHERE id = :'t1';

-- resolve rules
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT ew_support_add_message(:'t1', :t1rv, 'CUSTOMER', 'الأضواء حمراء، ورسالة الخطأ: لا يوجد اتصال', 0::smallint, gen_random_uuid());
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT pg_temp.expect('NOT_SUPPORT with unanswered customer message needs confirmation', format($$SELECT ew_support_resolve(%L, %s, 'NOT_SUPPORT', false)$$, :'t1', :t1rv), 'support_resolve_unanswered');
SELECT pg_temp.expect('NO_RESPONSE only from PENDING', format($$SELECT ew_support_resolve(%L, %s, 'NO_RESPONSE', true)$$, :'t1', :t1rv), 'support_ticket_transition');

-- escalation
SELECT ew_support_escalate(:'t1', :t1rv, 'VENDOR', 'الأضواء حمراء بعد إعادة التشغيل؛ يحتاج مزوّد الخدمة إلى فحص الخط.');
SELECT pg_temp.check('ESCALATED with target', status='ESCALATED' AND escalation_target='VENDOR', status) FROM support_tickets WHERE id = :'t1';
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT pg_temp.expect('ANSWER while escalated refused',
  format($$SELECT ew_support_prepare_reply(%L, %s, gen_random_uuid(), NULL, 'ANSWER', false, 'أصلح المزوّد الخط، والإنترنت يعمل الآن في المكتب.', 'أصلح المزوّد الخط، والإنترنت يعمل الآن في المكتب.', NULL)$$, :'t1', :t1rv),
  'support_escalation_open');
SELECT ew_support_return_escalation(:'t1', :t1rv, 'أصلح المزوّد الخط صباح اليوم.');
SELECT pg_temp.check('escalation returned → OPEN', status='OPEN' AND escalation_target IS NULL, status) FROM support_tickets WHERE id = :'t1';
SELECT row_version AS t1rv FROM support_tickets WHERE id = :'t1' \gset
SELECT ew_support_resolve(:'t1', :t1rv, 'BY_PHONE', false);
SELECT pg_temp.check('resolved by phone', status='RESOLVED' AND resolution='BY_PHONE', status) FROM support_tickets WHERE id = :'t1';

-- reject a draft citing an article with WRONG_INFO flags the article
SELECT ew_support_create_ticket('aaaaaaaa-0000-0000-0000-000000000002', 'EMAIL', 'NORMAL', NULL, NULL, NULL,
  'الإنترنت مقطوع عن جهازي فقط، وزملائي يعملون عادي', 0::smallint) AS t2 \gset
SELECT call_id AS c4 FROM ew_support_begin_draft(:'t2', 1) \gset
SELECT ew_support_record_draft(:'c4', 'DRAFT', 'ANSWER', 'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة.',
  'انقطاع الإنترنت عن جهاز', NULL, 'NETWORK', 'SINGLE', 'STOPPED', false, NULL, 'AR', '{}', NULL, NULL,
  json_build_array(json_build_object('article_id', :'a1', 'version', 1, 'quote', 'أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية'))::jsonb,
  100, 50, 'claude-opus-5-5', 'support-2026-10-09.1', 'req_4') AS d4 \gset
SELECT pg_temp.check('single-user stopped → HIGH', suggested_priority='HIGH', suggested_priority) FROM support_drafts WHERE id = :'d4';
SELECT ew_support_reject_draft(:'d4', 'WRONG_INFO', 'المشكلة في جهازٍ واحد لا في الموجّه');
SELECT pg_temp.check('cited article marked needs_review', needs_review AND needs_review_reason='DRAFT_WRONG_INFO', needs_review::text) FROM kb_articles WHERE id = :'a1';
SELECT pg_temp.expect('second rejection refused', format($$SELECT ew_support_reject_draft(%L, 'OTHER', 'اتصل 0551234567')$$, :'d4'), 'support_draft_immutable');

-- per-user isolation
SELECT set_config('eyework.user_id', '22222222-2222-2222-2222-222222222222', false);
SELECT pg_temp.check('S2 sees none of S1 tickets', count(*)=0, count(*)::text) FROM support_tickets;
SELECT pg_temp.check('S2 sees none of S1 articles', count(*)=0, count(*)::text) FROM kb_articles;
SELECT pg_temp.expect('S2 cannot act on S1 ticket', format($$SELECT ew_support_reopen(%L, 1)$$, :'t1'), 'P0002');
SELECT pg_temp.check('S2 search returns nothing from S1', count(*)=0, count(*)::text) FROM ew_kb_search('الإنترنت', 3);
-- marketing account refused
SELECT set_config('eyework.user_id', '33333333-3333-3333-3333-333333333333', false);
SELECT pg_temp.expect('marketing account cannot open a ticket',
  $$SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'لا تعمل الطابعة منذ الأمس', 0::smallint)$$, 'support_needs_support');
-- no session
SELECT set_config('eyework.user_id', '', false);
SELECT pg_temp.check('no session sees nothing', count(*)=0, count(*)::text) FROM support_tickets;
SELECT pg_temp.expect('no session cannot call functions', $$SELECT ew_support_accept_notice('2026-10-09')$$, 'support_needs_support');
-- internal functions are not callable
SELECT pg_temp.expect('web role cannot call ew_support_ai_open',
  $$SELECT ew_support_ai_open('11111111-1111-1111-1111-111111111111', 'DRAFT', NULL, NULL, NULL, NULL, NULL)$$, '42501');
SELECT pg_temp.expect('web role cannot call ew_ai_spend', $$SELECT ew_ai_spend(false)$$, '42501');

-- new open account: notice, then daily cap 10 for drafts is beyond reach here; check ticket cap 30 open
SELECT set_config('eyework.user_id', '44444444-4444-4444-4444-444444444444', false);
SELECT ew_support_accept_notice('2026-10-09');
DO $$ BEGIN FOR i IN 1..30 LOOP PERFORM ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'رسالة تجربة رقم ' || i, 0::smallint); END LOOP; END $$;
SELECT pg_temp.expect('new open account: 31st open ticket refused',
  $$SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'رسالة زائدة', 0::smallint)$$, 'support_open_ticket_cap');
SELECT pg_temp.check('usage reports new-account draft limit 20', per_day=20, per_day::text) FROM ew_support_my_ai_usage() WHERE kind='DRAFT';

SELECT n, CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END, name, CASE WHEN ok THEN '' ELSE info END FROM results ORDER BY n;
SELECT count(*) FILTER (WHERE ok) AS passed, count(*) FILTER (WHERE NOT ok) AS failed FROM results;
