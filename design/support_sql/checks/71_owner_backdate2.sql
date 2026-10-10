\set ON_ERROR_STOP 1
ALTER TABLE support_tickets DISABLE TRIGGER USER;
ALTER TABLE kb_articles DISABLE TRIGGER USER;
UPDATE support_tickets SET closed_at = now() - interval '31 days' WHERE status = 'CLOSED';
UPDATE kb_articles SET discarded_at = now() - interval '31 days' WHERE state = 'DISCARDED';
ALTER TABLE support_tickets ENABLE TRIGGER USER;
ALTER TABLE kb_articles ENABLE TRIGGER USER;
