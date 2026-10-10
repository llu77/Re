\set ON_ERROR_STOP 1
-- 2) text purge of closed ticket (what admin purge runs 30 days after closing; here at once)
WITH t AS (SELECT id FROM support_tickets WHERE status = 'CLOSED' AND texts_purged_at IS NULL)
, f AS (UPDATE support_flags SET evidence = NULL WHERE ticket_id IN (SELECT id FROM t) AND evidence IS NOT NULL)
, e AS (DELETE FROM support_escalations WHERE ticket_id IN (SELECT id FROM t))
, d AS (DELETE FROM support_drafts WHERE ticket_id IN (SELECT id FROM t))
SELECT 1;
DELETE FROM support_replies WHERE ticket_id IN (SELECT id FROM support_tickets WHERE status='CLOSED' AND texts_purged_at IS NULL);
DELETE FROM support_messages WHERE ticket_id IN (SELECT id FROM support_tickets WHERE status='CLOSED' AND texts_purged_at IS NULL);
INSERT INTO support_events (user_id, ticket_id, event, actor)
SELECT user_id, id, 'TEXTS_PURGED', 'SYSTEM' FROM support_tickets WHERE status='CLOSED' AND texts_purged_at IS NULL;
UPDATE support_tickets SET subject = NULL, customer_label = NULL, texts_purged_at = now() WHERE status='CLOSED' AND texts_purged_at IS NULL;
SELECT 'after purge' AS step, (SELECT count(*) FROM support_messages m JOIN support_tickets t ON t.id=m.ticket_id WHERE t.status='CLOSED') AS msgs,
       (SELECT count(*) FROM support_events e JOIN support_tickets t ON t.id=e.ticket_id WHERE t.status='CLOSED') AS events_kept,
       (SELECT count(*) FROM support_flags f JOIN support_tickets t ON t.id=f.ticket_id WHERE t.status='CLOSED' AND f.evidence IS NOT NULL) AS evidence_left;
-- 3) ai call ledger purge (7 days): FK SET NULL on drafts, kb_versions, flags
DELETE FROM support_ai_calls;
SELECT 'ledger purged' AS step, (SELECT count(*) FROM attempt_tombstones) AS tombstones,
       (SELECT count(*) FROM kb_versions WHERE origin='AI' AND call_id IS NULL) AS ai_versions_detached;
-- 4) the shared cap: fill to 2000 with tombstones
INSERT INTO attempt_tombstones (started_at, outcome, new_account)
SELECT now(), 'OK', false FROM generate_series(1, 2000 - ew_ai_spend(false)::integer);
SELECT 'spend' AS step, ew_ai_spend(false) AS total;
