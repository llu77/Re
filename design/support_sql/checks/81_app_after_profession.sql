SELECT set_config('eyework.user_id', '44444444-4444-4444-4444-444444444444', false);
DO $$ DECLARE c text; BEGIN
  PERFORM ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, 'رسالة بعد تغيير المهنة', 0::smallint);
  RAISE NOTICE 'FAIL ticket after leaving SUPPORT';
EXCEPTION WHEN insufficient_privilege THEN GET STACKED DIAGNOSTICS c = CONSTRAINT_NAME;
  RAISE NOTICE '% no desk after leaving SUPPORT: %', CASE WHEN c='support_needs_support' THEN 'PASS' ELSE 'FAIL' END, c;
END $$;
