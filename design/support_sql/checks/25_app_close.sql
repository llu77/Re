SELECT set_config('eyework.user_id', '11111111-1111-1111-1111-111111111111', false);
DO $$ DECLARE c text; BEGIN
  PERFORM * FROM ew_support_begin_draft((SELECT id FROM support_tickets WHERE number = 2), (SELECT row_version FROM support_tickets WHERE number = 2));
  RAISE NOTICE 'FAIL draft without notice';
EXCEPTION WHEN check_violation THEN GET STACKED DIAGNOSTICS c = CONSTRAINT_NAME;
  RAISE NOTICE '% model call refused without the desk notice: %', CASE WHEN c='support_notice_required' THEN 'PASS' ELSE 'FAIL' END, c;
END $$;
SELECT ew_support_accept_notice('2026-10-09');
SELECT ew_support_close_due() AS closed;
SELECT status, close_reason, (SELECT actor FROM support_events e WHERE e.ticket_id = t.id AND e.event='STATUS_CHANGED' ORDER BY id DESC LIMIT 1) AS actor FROM support_tickets t WHERE number = 1;
SELECT ew_support_follow_up((SELECT id FROM support_tickets WHERE number = 1), gen_random_uuid(), 'عاد الانقطاع اليوم مرة أخرى', 0::smallint) IS NOT NULL AS follow_up_created;
SELECT number, status, follow_up_of IS NOT NULL AS linked FROM support_tickets WHERE number IN (1,3) ORDER BY number;
