SELECT (SELECT count(*) FROM support_tickets) AS tickets,
       (SELECT count(*) FILTER (WHERE status='CLOSED') FROM support_tickets) AS closed,
       (SELECT count(*) FILTER (WHERE texts_purged_at IS NOT NULL) FROM support_tickets) AS purged,
       (SELECT count(*) FROM support_messages) AS msgs, (SELECT count(*) FROM support_drafts) AS drafts,
       (SELECT count(*) FROM support_replies) AS replies,
       (SELECT count(*) FROM support_replies WHERE state IN ('READY','RELEASED')) AS live_replies,
       (SELECT count(*) FROM support_events) AS events, (SELECT count(*) FROM support_ai_calls) AS calls,
       (SELECT string_agg(state, ',' ORDER BY number) FROM kb_articles) AS kb_states;
