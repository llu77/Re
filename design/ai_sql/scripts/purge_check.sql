-- The §7.5 purge statements on a crafted state, in a rolled-back transaction.
BEGIN;
INSERT INTO users (login_hmac, profession, display_name) VALUES (sha256('purge-check'), 'STOREKEEPER', 'سارة');
INSERT INTO ai_requests (user_id, feature, started_at) SELECT id, 'ASSISTANT', now() - interval '2 hours' FROM users WHERE login_hmac = sha256('purge-check');
INSERT INTO ai_requests (user_id, feature, subject_kind, subject_id, content_digest, started_at, finished_at, outcome, flags_count)
  SELECT id, 'STOCK_REVIEW', 'PURCHASE', '00000000-0000-0000-0000-000000000001', sha256('a'), now() - interval '40 days', now() - interval '40 days', 'OK', 2 FROM users WHERE login_hmac = sha256('purge-check');
INSERT INTO ai_flags (user_id, request_id, feature, subject_kind, subject_id, content_digest, position, check_code, severity, field, line_no, reason, created_at, closed_at)
  SELECT r.user_id, r.id, 'STOCK_REVIEW', 'PURCHASE', r.subject_id, r.content_digest, 1, 'PRICE_IMPLAUSIBLE', 'HIGH', 'unit_cost', 1, 'سعر الوحدة في السطر 1 أعلى بكثير من المعتاد لهذا الصنف.', now() - interval '40 days', now() - interval '39 days'
    FROM ai_requests r WHERE r.feature = 'STOCK_REVIEW' AND r.started_at < now() - interval '30 days';
INSERT INTO ai_flags (user_id, request_id, feature, subject_kind, subject_id, content_digest, position, check_code, severity, field, line_no, reason, created_at)
  SELECT r.user_id, r.id, 'STOCK_REVIEW', 'PURCHASE', r.subject_id, r.content_digest, 2, 'UNIT_MISMATCH', 'MEDIUM', 'unit', 2, 'الوحدة في السطر 2 لا تناسب الصنف كما سُمّي في الفاتورة.', now() - interval '40 days'
    FROM ai_requests r WHERE r.feature = 'STOCK_REVIEW' AND r.started_at < now() - interval '30 days';
INSERT INTO ai_flag_decisions (flag_id, user_id, choice) SELECT id, user_id, 'PROCEED' FROM ai_flags WHERE check_code = 'PRICE_IMPLAUSIBLE';
INSERT INTO ai_flag_decisions (flag_id, user_id, choice) SELECT id, user_id, 'EDIT' FROM ai_flags WHERE check_code = 'UNIT_MISMATCH';
\echo '-- before: 2 requests (1 open for 2 h, 1 settled 40 days ago), 2 flags (1 closed, 1 open), 2 decisions'
UPDATE ai_requests SET finished_at = now(), outcome = 'ABANDONED' WHERE finished_at IS NULL AND started_at < now() - interval '1 hour';
DELETE FROM ai_requests WHERE started_at < now() - interval '30 days';
DELETE FROM ai_flags WHERE closed_at IS NULL AND created_at < now() - interval '30 days';
\echo '-- after:'
SELECT feature, outcome FROM ai_requests ORDER BY feature;
SELECT check_code, request_id IS NULL AS unlinked, closed_at IS NOT NULL AS closed,
       (SELECT count(*) FROM ai_flag_decisions d WHERE d.flag_id = f.id) AS decisions FROM ai_flags f;
SELECT count(*) AS decisions_left FROM ai_flag_decisions;
SELECT count(*) AS tombstones_from_purge FROM attempt_tombstones;
ROLLBACK;
