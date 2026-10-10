\set ON_ERROR_STOP 1
-- scratch only: backdate S2's tickets and articles to exercise every purge branch
ALTER TABLE support_tickets DISABLE TRIGGER USER;
ALTER TABLE kb_articles DISABLE TRIGGER USER;
ALTER TABLE support_ai_calls DISABLE TRIGGER USER;
UPDATE support_tickets SET resolved_at = now() - interval '5 days' WHERE status = 'RESOLVED';
UPDATE support_tickets SET last_activity_at = now() - interval '91 days' WHERE status IN ('NEW', 'OPEN', 'PENDING', 'ESCALATED');
UPDATE kb_articles SET updated_at = now() - interval '31 days' WHERE state = 'PROPOSED';
UPDATE support_ai_calls SET started_at = now() - interval '8 days';
ALTER TABLE support_tickets ENABLE TRIGGER USER;
ALTER TABLE kb_articles ENABLE TRIGGER USER;
ALTER TABLE support_ai_calls ENABLE TRIGGER USER;
