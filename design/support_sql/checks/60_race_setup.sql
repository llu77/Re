SELECT set_config('eyework.user_id', '22222222-2222-2222-2222-222222222222', false);
SELECT ew_support_accept_notice('2026-10-09');
SELECT ew_support_create_ticket('dddddddd-0000-0000-0000-000000000001', 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'الطابعة لا تطبع منذ الصباح', 0::smallint);
SELECT ew_support_create_ticket('dddddddd-0000-0000-0000-000000000002', 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'البريد لا يصلني منذ أمس', 0::smallint);
