SELECT set_config('eyework.user_id', '22222222-2222-2222-2222-222222222222', false);
BEGIN;
SELECT call_id IS NOT NULL AS a_opened FROM ew_support_begin_draft((SELECT id FROM support_tickets WHERE client_token='dddddddd-0000-0000-0000-000000000001'), 1);
SELECT pg_sleep(2);
COMMIT;
