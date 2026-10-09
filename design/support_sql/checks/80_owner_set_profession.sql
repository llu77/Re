\set ON_ERROR_STOP 1
-- what admin set-profession runs when an account leaves SUPPORT (one transaction, user row locked first)
BEGIN;
SELECT 1 FROM users WHERE id = '44444444-4444-4444-4444-444444444444' FOR UPDATE;
UPDATE support_replies SET state = 'WITHDRAWN', withdrawn_at = now()
 WHERE user_id = '44444444-4444-4444-4444-444444444444' AND state IN ('READY', 'RELEASED');
UPDATE support_tickets SET status = 'CLOSED', close_reason = 'PROFESSION_CHANGED'
 WHERE user_id = '44444444-4444-4444-4444-444444444444' AND status <> 'CLOSED';
UPDATE users SET profession = 'MARKETING' WHERE id = '44444444-4444-4444-4444-444444444444';
COMMIT;
SELECT 'set-profession' AS step, count(*) FILTER (WHERE status = 'CLOSED' AND close_reason = 'PROFESSION_CHANGED') AS closed,
       count(*) FILTER (WHERE status <> 'CLOSED') AS still_open
  FROM support_tickets WHERE user_id = '44444444-4444-4444-4444-444444444444';
