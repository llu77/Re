-- ════════════════════════════════════════════════════════════════════════
-- NEXT_ai_layer — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- يُتراجع عن ترحيلات الأدوات التي تستدعي ew_ai_* قبله: محفّز ew_ai_forget_subject على
-- جداولها يمنع حذف الدالّة هنا، فيفشل التراجع بوضوح لا بصمت.
--
-- السقف العام لا يُفرغه التراجع: حذف صفوف الدفتر يكتب أثر ما فُوتر في آخر يوم في
-- attempt_tombstones (محفّز الحذف)، فيعدّه ew_begin_generation بعد التراجع كما يعدّ أثر
-- المحاولات المحذوفة.

DROP TABLE ai_flag_decisions;
DROP TABLE ai_flags;
DELETE FROM ai_requests;

-- ew_begin_generation كما كانت قبل هذا الترحيل، حرفاً بحرف.
--@@BEGIN_GENERATION@@

DROP FUNCTION ew_assistant_finish(uuid, text, jsonb), ew_assistant_begin(), ew_ai_my_usage(),
              ew_ai_request_fail(uuid, text, jsonb), ew_ai_decide(uuid, text),
              ew_ai_erase_subject(text, uuid), ew_ai_forget_subject(), ew_ai_gate(text, uuid, bytea),
              ew_ai_flags_put(uuid, bytea, jsonb, jsonb), ew_ai_lock_subject(uuid),
              ew_ai_request_settle(uuid, text, smallint, jsonb), ew_ai_request_open(text, text, uuid, bytea),
              ew_ai_spend(boolean);
DROP TABLE ai_requests;
DROP FUNCTION ew_ai_request_tombstone(), ew_ai_flag_guard();
DROP TABLE ai_features;
DROP FUNCTION ew_ai_text_ok(text, integer, integer);
