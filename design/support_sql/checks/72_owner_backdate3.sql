\set ON_ERROR_STOP 1
ALTER TABLE support_tickets DISABLE TRIGGER USER;
UPDATE support_tickets SET closed_at = now() - interval '366 days' WHERE status = 'CLOSED';
ALTER TABLE support_tickets ENABLE TRIGGER USER;
