-- a fresh call within 24h, then the account deletes itself
SELECT set_config('eyework.user_id', '11111111-1111-1111-1111-111111111111', false);
SELECT call_id FROM ew_support_begin_draft((SELECT id FROM support_tickets WHERE number = 2), (SELECT row_version FROM support_tickets WHERE number = 2));
SELECT ew_support_finish_call((SELECT id FROM support_ai_calls WHERE finished_at IS NULL), 'OUTPUT_INVALID', 10, 10, 'claude-opus-5-5', 'support-2026-10-09.1', 'req_x');
SELECT ew_delete_me();
