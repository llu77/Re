-- admin purge — مكتب الدعم الفني (بدور المالك، بلا جلسة، في معاملةٍ واحدة)
-- ١) الإغلاق الآلي: المحلولة بعد أربعة أيام، وما خمل تسعين يوماً؛ والردّ الحيّ على المغلقة يُسحب.
UPDATE support_tickets SET status = 'CLOSED', close_reason = 'AFTER_RESOLVED'
 WHERE status = 'RESOLVED' AND resolved_at < now() - interval '4 days';
UPDATE support_tickets SET status = 'CLOSED', close_reason = 'IDLE'
 WHERE status <> 'CLOSED' AND last_activity_at < now() - interval '90 days';
UPDATE support_replies r SET state = 'WITHDRAWN', withdrawn_at = now()
  FROM support_tickets t
 WHERE t.id = r.ticket_id AND t.status = 'CLOSED' AND r.state IN ('READY', 'RELEASED');
-- ٢) نصوص التذكرة بعد ثلاثين يوماً من إغلاقها: الرسائل والمسودات والردود والتصعيد واقتباسات التنبيهات،
--    والموضوع واسم العميل. يبقى السجلّ (رموزٌ وأوقات) والتذكرة بلا نصّ.
UPDATE support_flags f SET evidence = NULL
  FROM support_tickets t
 WHERE t.id = f.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL
   AND t.closed_at < now() - interval '30 days' AND f.evidence IS NOT NULL;
DELETE FROM support_drafts d USING support_tickets t
 WHERE t.id = d.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL
   AND t.closed_at < now() - interval '30 days';
DELETE FROM support_replies r USING support_tickets t
 WHERE t.id = r.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL
   AND t.closed_at < now() - interval '30 days';
DELETE FROM support_messages m USING support_tickets t
 WHERE t.id = m.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL
   AND t.closed_at < now() - interval '30 days';
DELETE FROM support_escalations e USING support_tickets t
 WHERE t.id = e.ticket_id AND t.status = 'CLOSED' AND t.texts_purged_at IS NULL
   AND t.closed_at < now() - interval '30 days';
INSERT INTO support_events (user_id, ticket_id, event, actor)
SELECT user_id, id, 'TEXTS_PURGED', 'SYSTEM' FROM support_tickets
 WHERE status = 'CLOSED' AND texts_purged_at IS NULL AND closed_at < now() - interval '30 days';
UPDATE support_tickets SET subject = NULL, customer_label = NULL, texts_purged_at = now()
 WHERE status = 'CLOSED' AND texts_purged_at IS NULL AND closed_at < now() - interval '30 days';
-- ٣) التذكرة نفسها وسجلّها بعد سنةٍ من إغلاقها.
DELETE FROM support_tickets WHERE status = 'CLOSED' AND closed_at < now() - interval '365 days';
-- ٤) دفتر الاستدعاءات بعد سبعة أيام (أثر آخر يومٍ يكتبه محفّز الحذف، ولا شيء منه هنا).
DELETE FROM support_ai_calls WHERE started_at < now() - interval '7 days';
-- ٥) اقتراحٌ لم يمسّه الموظف ثلاثين يوماً يُسقط، والمُسقط يُحذف بعد ثلاثين يوماً.
UPDATE kb_articles SET state = 'DISCARDED' WHERE state = 'PROPOSED' AND updated_at < now() - interval '30 days';
DELETE FROM kb_articles WHERE state = 'DISCARDED' AND discarded_at < now() - interval '30 days';
