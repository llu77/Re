SELECT 'after delete' AS step, (SELECT count(*) FROM support_tickets WHERE user_id='11111111-1111-1111-1111-111111111111') AS tickets,
       (SELECT count(*) FROM kb_articles WHERE user_id='11111111-1111-1111-1111-111111111111') AS articles,
       (SELECT count(*) FROM support_events WHERE user_id='11111111-1111-1111-1111-111111111111') AS events,
       (SELECT count(*) FROM attempt_tombstones) AS tombstones_from_deleted_account;
