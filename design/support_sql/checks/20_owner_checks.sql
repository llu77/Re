\set ON_ERROR_STOP 1
-- 1) automatic close: pretend t1 was resolved 5 days ago (scratch only: triggers off for the backdate)
ALTER TABLE support_tickets DISABLE TRIGGER USER;
UPDATE support_tickets SET resolved_at = now() - interval '5 days' WHERE number = 1 AND user_id = '11111111-1111-1111-1111-111111111111';
ALTER TABLE support_tickets ENABLE TRIGGER USER;
-- notice withdrawn by the owner (scratch only) → the model gate in ew_support_ai_open holds on its own
UPDATE support_settings SET notice_version = NULL, notice_accepted_at = NULL WHERE user_id = '11111111-1111-1111-1111-111111111111';
