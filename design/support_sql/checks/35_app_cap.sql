SELECT set_config('eyework.user_id', '11111111-1111-1111-1111-111111111111', false);
DO $$
DECLARE c text;
BEGIN
  PERFORM * FROM ew_support_begin_draft((SELECT id FROM support_tickets WHERE number = 2), (SELECT row_version FROM support_tickets WHERE number = 2));
  RAISE NOTICE 'FAIL: draft allowed over the global cap';
EXCEPTION WHEN check_violation THEN
  GET STACKED DIAGNOSTICS c = CONSTRAINT_NAME;
  RAISE NOTICE '% global cap on support draft: %', CASE WHEN c='generation_global_cap' THEN 'PASS' ELSE 'FAIL' END, c;
END $$;
