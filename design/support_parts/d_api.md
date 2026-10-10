
---

## 6. The API

### 6.1 Common rules

- **Prefix and gates.**
  - The prefix is `/api/support`.
  - Every route depends on `require_profession(Profession.SUPPORT)`: 401 `SESSION` without a session, 403 `PROFESSION` for another profession.
  - Every `POST` and `PUT` also passes the existing mutation checks: `X-Eyework: 1`, a matching `Origin`, and the `mutation` limiter.
  - **Model-calling routes** (drafts, review, KB review, proposals) also depend on `require_current_terms` (registration §7.10; 403 `TERMS`).
  - **Routes that take customer text or call the model** (`mask-preview`, ticket creation, messages, follow-ups and the four model routes) depend on `require_support_notice`: the accepted desk-notice version must equal `support_notice.VERSION` (409 `NOTICE`, §10.2). The database refuses them on its own when no version was ever accepted.
- **Bodies.** Pydantic models with `extra="forbid"`.
  - Strings are NFC-normalized; CRLF becomes LF; LRM, RLM, bidi controls and BOM are removed; then they are trimmed.
  - Lengths and enums are checked before the database, which checks them again.
  - Ids are UUIDs. `client_token` is a client-generated UUID v4.
- **Responses.** Times are ISO-8601 UTC; the client shows them in Riyadh time. Errors are `{"code": "…", "detail": "<Arabic>"}`, with `Retry-After` on 429 and 503. No database message reaches the client or the log (as in `web/errors.py`).
- **Transactions.** A model call is three steps:
  1. `begin`, in its own transaction;
  2. the call itself, with no transaction open;
  3. `record` or `finish`, in its own transaction.

  Everything else is one transaction per request. This follows `campaigns.py`.
- **The user** comes from the session cookie only (`require_user` → `db.session(user_id)` → `eyework.user_id`).

### 6.2 Routes

| Method and path | Body | Success | Limiter |
|---|---|---|---|
| `GET /home` | — | 200 `{counts:{decide, open, pending, escalated, kb_attention}, notice:{current, accepted, title, lines}}`. Runs `ew_support_close_due()` first. | `support_read` |
| `GET /decide?page=` | — | 200 `Page<DecisionItem>` | `support_read` |
| `GET /tickets?view=open\|pending\|escalated\|resolved\|closed&page=` | — | 200 `Page<TicketRow>` | `support_read` |
| `POST /mask-preview` | `{text}` | 200 `{text, masked:{email, link, number}, language:"AR"\|"EN"}`. Stores nothing. | `support_paste` |
| `POST /tickets` | `{client_token, channel, text, customer_label?, subject?, priority?, category?}` | 201 `TicketView` (200 with the same id on a repeated `client_token`) | `support_paste` |
| `GET /tickets/{id}` | — | 200 `TicketView` | `support_read` |
| `GET /tickets/{id}/events?page=` | — | 200 `Page<EventRow>` | `support_read` |
| `POST /tickets/{id}/messages` | `{client_token, expected_row_version, author:"CUSTOMER"\|"NOTE", text}` | 201 `TicketView` | `support_paste` |
| `POST /tickets/{id}/classification` | `{expected_row_version, category\|null, priority, subject\|null, accept_draft_id\|null}` | 200 `TicketView` | `mutation` |
| `POST /tickets/{id}/drafts` | `{expected_row_version, presets:[…], hint?, redraft_of?}` | 201 `TicketView` with `draft` | `support_ai` |
| `POST /drafts/{id}/reject` | `{reason, note?}` | 200 `TicketView` | `mutation` |
| `POST /tickets/{id}/replies` | `{client_token, expected_row_version, kind, draft_id?, core?, template_questions?:[code], kb_article_ids?:[uuid]}` | 201 `ReplyView` | `mutation` |
| `POST /replies/{id}/review` | `{kb_article_ids?:[uuid]}` (the articles inserted in the composer, 0–3) | 200 `ReplyView` | `support_ai` |
| `POST /flags/{id}` | `{action:"HEEDED"\|"DISMISSED", reason?}` | 200 `FlagView` | `mutation` |
| `POST /replies/{id}/release` | `{via:"COPY"\|"SHARE"\|"SCRIPT", body_sha256:"<64 hex>", skip_review:false}` | 200 `ReplyView` | `mutation` |
| `POST /replies/{id}/confirm` | `{sent: true\|false}` | 200 `TicketView` | `mutation` |
| `POST /tickets/{id}/escalate` | `{expected_row_version, target, note, notify_customer: bool}` | 200 `TicketView` (+ `live_reply` when `notify_customer`) | `mutation` |
| `POST /tickets/{id}/escalation-return` | `{expected_row_version, note}` | 200 `TicketView` | `mutation` |
| `POST /tickets/{id}/resolve` | `{expected_row_version, resolution, confirmed: bool}` | 200 `TicketView`; 409 `UNANSWERED` with `{flag: FlagView}` | `mutation` |
| `POST /tickets/{id}/reopen` | `{expected_row_version}` | 200 `TicketView` | `mutation` |
| `POST /tickets/{id}/follow-up` | `{client_token, text}` | 201 `TicketView` | `support_paste` |
| `GET /kb?view=published\|attention\|drafts\|proposals\|archived&q=&page=` | — | 200 `Page<ArticleRow>` (`q` uses `ew_kb_search`) | `support_read` (`support_search` with `q`) |
| `GET /kb/{id}` | — | 200 `ArticleView` | `support_read` |
| `POST /kb` | `{client_token, title, issue, environment?, resolution, cause?, source_ticket_id?}` | 201 `ArticleView` | `mutation` |
| `POST /kb/{id}/versions` | `{expected_row_version, title, issue, environment?, resolution, cause?}` | 200 `ArticleView` | `mutation` |
| `POST /kb/{id}/review` | `{version}` | 200 `ArticleView` with `flags` | `support_ai` |
| `POST /kb/{id}/publish` | `{expected_row_version, version}` | 200 `ArticleView` | `mutation` |
| `POST /kb/{id}/state` | `{expected_row_version, state:"ARCHIVED"\|"DISCARDED"}` | 200 `ArticleView` | `mutation` |
| `POST /kb/{id}/needs-review` | `{expected_row_version, needs_review: bool}` | 200 `ArticleView` | `mutation` |
| `POST /kb/proposals` | `{ticket_id}` | 201 `ArticleView` (`PROPOSED`) | `support_ai` |
| `GET /improve?days=30` | — | 200 `{rejections:[{reason, count}], gaps:[{draft_id, ticket_id, ticket_number, reason, note, at}], attention:[ArticleRow]}` | `support_read` |
| `GET /settings` · `PUT /settings` | `PUT {signature\|null, sla?:{URGENT:{first_reply_minutes, resolve_minutes}, …}}` | 200 `{signature, sla, ai_usage:[{kind, per_day, used}], notice:{current, accepted, title, lines}}` | `support_read` / `mutation` |
| `POST /notice` | `{version}` (must equal `support_notice.VERSION`) | 204 | `mutation` |
| `GET /phrases` | — | 200 `{phrases:[{id, ar, en}], questions:[{code, ar, en}], update_templates:[{code, ar, en}]}` (static, §8.6) | `support_read` |

**Request field rules** (the server checks them; the database checks them again):

| Field | Rule |
|---|---|
| `channel` | `MESSAGING`, `EMAIL`, `PHONE`, `IN_PERSON`, `WEB_FORM`, `OTHER` |
| `text` | 1–4000 characters after normalization; masked by the server (§7.1) before the database |
| `customer_label` | 1–30 characters, Arabic or Latin letters and digits with single spaces, and no run of 9 or more digits |
| `subject` | 3–80 characters, one line, no email and no run of 9 or more digits |
| `priority` | `URGENT`, `HIGH`, `NORMAL` (the default), `LOW` |
| `category` | the nine codes in §1.3, or null |
| `presets` | 0–2 of `SHORTER`, `SIMPLER`, `MORE_FORMAL`, `WARMER`, `ASK_INFO`; never `MORE_FORMAL` with `WARMER` |
| `hint` | 1–200 characters, one line, masked |
| `reason` (reject) | `WRONG_INFO`, `NOT_IN_KB`, `MISUNDERSTOOD`, `TONE`, `TOO_LONG`, `INCOMPLETE`, `OUTDATED_ARTICLE`, `OTHER` |
| `note` (reject) | 1–200 characters, masked |
| `kind` | `ANSWER`, `ASK_INFO`, `UPDATE` |
| `core` | 20–1200 characters; required unless `template_questions` is given |
| `template_questions` | 1–4 distinct codes from §8.6; only with `kind = ASK_INFO` |
| `kb_article_ids` | 0–3 ids of the user's own published articles, inserted from the tools button or «أضف من قاعدة المعرفة». They count as grounding for `LINK_NOT_IN_KB`, and the client sends them again with the review request so the reviewer reads them (§8.4.1). |
| `target` | `TIER2`, `SUPERVISOR`, `VENDOR`, `FIELD_TECH`, `OTHER_TEAM` |
| escalation `note` | 10–1000 characters, masked |
| `resolution` | `BY_PHONE`, `IN_PERSON`, `DUPLICATE`, `NOT_SUPPORT`, `NO_RESPONSE` |
| flag `reason` | `FALSE_ALARM`, `EMPLOYER_APPROVED`, `KB_OUTDATED`, `OTHER` (and `CONFIRMED`, set by the server) |
| article fields | `title` 4–80 (one line); `issue` 10–400; `environment` 3–300 or null; `resolution` 20–4000; `cause` 3–400 or null; no national ID, card or IBAN |
| `signature` | 2–60 characters, one line, no email and no run of 9 or more digits, or null |
| SLA minutes | first reply ∈ {30, 60, 120, 240, 480, 1440}; resolution ∈ {240, 480, 1440, 2880, 4320, 7200}; first < resolution |

### 6.3 Response shapes

```jsonc
// TicketRow
{ "id": "uuid", "number": 12, "status": "OPEN", "priority": "HIGH", "category": "NETWORK", "channel": "MESSAGING",
  "customer_label": "سارة", "subject": "انقطاع الإنترنت", "preview": "الإنترنت مقطوع عن كل أجهزة…",
  "sla": { "kind": "FIRST_REPLY", "state": "DUE_SOON", "minutes": 35 },      // ON_TRACK | DUE_SOON (≤25% left) | BREACHED | MET | PAUSED
  "badges": { "draft_ready": true, "awaiting_confirmation": false, "open_flags": 0, "suggested_priority": "URGENT" },
  "row_version": 7, "updated_at": "2026-10-09T07:42:10Z" }

// TicketView = TicketRow + …
{ "messages": [ { "id": "uuid", "author": "CUSTOMER", "body": "…[رقم محذوف]…", "masked_count": 1, "at": "…" } ],
  "draft": { "id": "uuid", "seq": 2, "result": "DRAFT", "reply_kind": "ANSWER", "body": "…", "subject": "…",
             "note_to_employee": "استندتُ إلى KB-7.", "suggestion": { "category": "NETWORK", "priority": "URGENT",
             "impact": "WIDESPREAD", "urgency": "STOPPED", "security_concern": false, "escalate": null },
             "citations": [ { "article_id": "uuid", "number": 7, "title": "…", "version": 3, "quote": "…" } ],
             "rejected": null, "served_model": "claude-opus-5-5", "at": "…" },
  "live_reply": ReplyView | null,
  "escalation": { "target": "VENDOR", "note": "…", "at": "…", "returned_at": null } | null,
  "flags": [ FlagView ],                                   // ticket-level flags
  "allowed": { "send_as_is": true, "edit": true, "ask_info": true, "escalate": true, "reject": true,
               "resolve": true, "reopen": false, "follow_up": false, "draft": true },
  "ai": { "draft_left_today": 48 } }

// ReplyView
{ "id": "uuid", "ticket_id": "uuid", "kind": "ANSWER", "origin": "EDITED", "core": "…", "body": "مرحباً سارة،\n\n…\n\nفريق الدعم الفني",
  "body_sha256": "64 hex", "state": "READY", "review": "DONE", "flags": [ FlagView ], "release_via": null, "at": "…" }

// FlagView: the text is composed on the server from the code (§8.4). The client adds «يا {display_name}، » (AIFlag).
{ "id": "uuid", "source": "AI", "code": "UNSUPPORTED_CLAIM", "state": "OPEN",
  "message": "في الردّ معلومةٌ لا تسندها قاعدة المعرفة.",
  "reason": "العبارة «…» لا ترد في أيّ مقالةٍ منشورة، والعميل سيعمل بها كما هي.",
  "evidence": "…", "related_article": { "id": "uuid", "number": 7, "title": "…" } | null }

// ArticleRow / ArticleView
{ "id": "uuid", "number": 7, "state": "PUBLISHED", "title": "…", "published_version": 3, "latest_version": 3,
  "needs_review": false, "reuse_count": 5, "row_version": 9 }
// ArticleView adds: "versions": [{ "version", "title", "issue", "environment", "resolution", "cause", "origin", "at" }],
//                   "flags": [FlagView], "events": Page<EventRow>

// EventRow
{ "at": "…", "actor": "EMPLOYEE" | "ASSISTANT" | "SYSTEM", "event": "REPLY_SENT", "detail": "ANSWER",
  "from_status": null, "to_status": null }

// Page<T>
{ "items": [T], "page": 1, "pages": 3, "total": 47 }       // 20 per page; page ≥ 1 and ≤ 500
```

### 6.4 Errors (Arabic, as the server returns them)

| Code | HTTP | Source | `detail` |
|---|---|---|---|
| `SESSION` | 401 | `require_user` | «سجّل الدخول للمتابعة.» |
| `PROFESSION` | 403 | `require_profession`, `support_needs_support` | «هذه الأداة لبوابة مهنةٍ أخرى.» |
| `TERMS` | 403 | `require_current_terms` | (registration §7.7) |
| `NOTICE` | 409 | `support_notice_required` | «اقرأ إشعار مكتب الدعم ووافق عليه أولاً.» |
| `RATE` | 429 | memory limiters | «طلباتٌ كثيرة. حاول بعد قليل.» |
| `INVALID` | 422 | body validation, and its database second guards: `support_ticket_category`, `support_ticket_channel`, `support_ticket_priority`, `support_escalation_to`, `support_resolution`, `support_reply_kind`, `support_reply_via`, `support_flag_dismiss`, `support_draft_presets`, `support_draft_reject_reason`, `support_notice_version_shape`, `kb_article_state` | «قيمةٌ غير صالحة في الطلب.» |
| `TEXT_LENGTH` | 422 | `support_message_body`, `text` | «النصّ من حرفٍ إلى 4000 حرف.» |
| `CONTACT_LEFT` | 422 | `support_message_contact_free` and other contact checks | «بقي في النصّ بريدٌ أو رقمٌ طويل. احذفه وحاول مرة أخرى.» |
| `LABEL` | 422 | `support_customer_label_shape` | «اسم العميل: حروفٌ وأرقامٌ حتى 30، بلا رقم هاتف.» |
| `SUBJECT` | 422 | `support_subject_shape` | «الموضوع من 3 إلى 80 حرفاً في سطرٍ واحد، بلا بريدٍ ولا رقمٍ طويل.» |
| `STALE` | 409 | `stale_row_version`, `support_suggestion_mismatch` | Ticket: «تغيّرت التذكرة منذ عرضها. راجعها مرة أخرى.»; article: «تغيّرت المقالة منذ عرضها. راجعها مرة أخرى.» |
| `TICKET_CLOSED` | 409 | `support_ticket_closed` | «التذكرة مغلقة. إن ردّ العميل فافتح تذكرة متابعة.» |
| `TRANSITION` | 409 | `support_ticket_transition`, `support_follow_up_needs_closed` | «لا يصحّ هذا الإجراء في حال التذكرة الآن.» |
| `OPEN_CAP` | 409 | `support_open_ticket_cap` | «بلغت التذاكر المفتوحة حدّها. أغلق ما انتهى منها أولاً.» |
| `TICKET_DAILY` | 429 (3600) | `support_daily_ticket_cap` | «بلغتَ حدّ اليوم من التذاكر الجديدة. حاول غداً.» |
| `MESSAGE_CAP` | 409 | `support_message_cap` | «في هذه التذكرة ستون رسالة، وهو الحدّ.» |
| `MESSAGE_DAILY` | 429 (3600) | `support_daily_message_cap` | «بلغتَ حدّ اليوم من الرسائل الملصقة. حاول غداً.» |
| `NO_MESSAGE` | 409 | `support_draft_needs_message` | «لا رسالة من العميل في التذكرة بعد.» |
| `WRITING` | 409 | `support_ai_in_progress` | «سيمبول يعمل على طلبٍ آخر الآن. انتظر حتى ينتهي.» |
| `AI_RATE` | 429 (600) | `support_ai_rate` | «طلباتٌ كثيرة خلال وقتٍ قصير. حاول بعد دقائق.» |
| `AI_DAILY` | 429 (3600) | `support_ai_daily_cap` | «بلغتَ حدّ اليوم من طلبات سيمبول. اكتب الردّ بنفسك، أو حاول غداً.» |
| `AI_NEW_DAILY` | 429 (3600) | `support_ai_new_account_daily_cap` | «للحساب الجديد في أسبوعه الأول حدٌّ أصغر من طلبات سيمبول. اكتب الردّ بنفسك، أو حاول غداً.» |
| `AI_BUSY` | 503 (600) | `support_ai_app_cap`, `generation_global_cap`, `generation_new_accounts_cap`, `UPSTREAM_BUSY` | «سيمبول مشغولٌ الآن. اكتب الردّ بنفسك، أو حاول لاحقاً.» |
| `TICKET_DRAFTS` | 429 (3600) | `support_ticket_draft_cap` | «طُلبت لهذه التذكرة ثماني مسودات اليوم. اكتب الردّ بنفسك.» |
| `DRAFT_STALE` | 409 | `support_draft_stale`, `support_draft_needs_open_call`, `support_ai_call_not_open` | «وصلت رسالةٌ جديدة أو انتهت المهلة أثناء الكتابة. اطلب المسودة مرة أخرى.» |
| `KB_CHANGED` | 409 | `support_citation_not_published` | «تغيّرت قاعدة المعرفة أثناء الكتابة. اطلب المسودة مرة أخرى.» |
| `AI_REFUSED` | 422 | outcome `REFUSED` | «لم يكتب سيمبول مسودةً لهذه الرسالة. اكتب الردّ بنفسك.» |
| `AI_OUTPUT_INVALID` | 502 | outcome `OUTPUT_INVALID` (and the database grounding checks, should our check ever miss) | «لم تكتمل المسودة هذه المرة. حاول مرة أخرى، أو اكتب الردّ بنفسك.» |
| `AI_TIMEOUT` | 504 | `UPSTREAM_TIMEOUT` | «تأخّر سيمبول. حاول مرة أخرى.» |
| `AI_UNAVAILABLE` | 503 | `UPSTREAM_UNREACHABLE`, `UPSTREAM_ERROR` | «سيمبول غير متاحٍ الآن. اكتب الردّ بنفسك.» |
| `DRAFT_OLD` | 409 | `support_reply_draft_not_current` | «هذه ليست أحدث مسودة. افتح الأحدث.» |
| `DRAFT_IN_USE` | 409 | `support_draft_in_use` | «المسودة في ردٍّ جاهزٍ أو مرسل، فلا تُرفض الآن.» |
| `DRAFT_DONE` | 409 | `support_draft_immutable` | «رُفضت هذه المسودة من قبل.» |
| `LIVE_REPLY` | 409 | `support_one_live_reply`, `support_live_reply_exists` | «لهذه التذكرة ردٌّ جاهزٌ لم يُرسل. أرسله أو اسحبه أولاً.» |
| `ESCALATED` | 409 | `support_escalation_open` | «التذكرة مُصعَّدة. سجّل ما عاد من التصعيد قبل ردّ الحلّ.» |
| `REPLY_TEXT` | 422 | `support_reply_core`, `support_reply_body` | «الردّ من 20 إلى 1200 حرف، بلا رقم هويةٍ أو بطاقةٍ أو آيبان.» |
| `REPLY_CHANGED` | 409 | `support_reply_hash_mismatch` | «النصّ المنسوخ غير النصّ المحفوظ. لا ترسله؛ افتح الردّ وانسخه من جديد.» |
| `FLAGS_OPEN` | 409 | `support_flags_open` | «على هذا تنبيهٌ لم تقرّر فيه بعد.» |
| `REVIEW_WAITING` | 409 | `support_review_waiting` | «سيمبول يراجع الآن. انتظر قليلاً، أو أرسل دون انتظار المراجعة.» |
| `REVIEW_STATE` | 409 | `support_review_not_pending` | «لا مراجعة تنتظر هنا.» |
| `REPLY_STATE` | 409 | `support_reply_transition` | «تغيّرت حال الردّ. افتح التذكرة من جديد.» |
| `FLAG_STATE` | 409 | `support_flag_immutable` | «قُرّر في هذا التنبيه من قبل.» |
| `UNANSWERED` | 409 | `support_resolve_unanswered` | «آخر رسالةٍ من العميل بلا ردّ.» (+ `flag`) |
| `NOTE` | 422 | rejection, escalation and return notes, and the hint: `support_draft_reject_note`, `support_escalation_note`, `support_escalation_return`, `support_draft_hint` | «الملاحظة ضمن الطول المسموح، بلا بريدٍ ولا رقمٍ طويل.» |
| `SIGNATURE` | 422 | `support_signature_shape` | «التوقيع من حرفين إلى 60 في سطرٍ واحد.» |
| `SLA` | 422 | `support_sla_first`, `support_sla_resolve`, `support_sla_order`, `support_sla_priority` | «اختر من القيم المعروضة، وزمن أول ردٍّ أقصر من زمن الحلّ.» |
| `KB_FIELD` | 422 | `kb_versions_*_check` | «{العنوان من 4 إلى 80 حرفاً \| المشكلة من 10 إلى 400 \| البيئة من 3 إلى 300 \| الحلّ من 20 إلى 4000 \| السبب من 3 إلى 400}.» |
| `KB_SENSITIVE` | 422 | `kb_version_clean` | «في المقالة رقم هويةٍ أو بطاقةٍ أو آيبان. احذفه.» |
| `KB_CAP` | 409 | `kb_article_cap` | «في قاعدة المعرفة ثلاثمئة مقالة، وهو الحدّ. أرشف ما لا يُستعمل.» |
| `KB_VERSIONS` | 409 | `kb_version_cap` | «للمقالة ثلاثون نسخة، وهو الحدّ. أنشئ مقالةً جديدة.» |
| `KB_DAILY` | 429 (3600) | `kb_daily_version_cap` | «بلغتَ حدّ اليوم من نسخ المقالات. حاول غداً.» |
| `KB_STATE` | 409 | `kb_article_transition`, `kb_publish_latest_only`, `kb_article_starts_unpublished`, `kb_review_only_published` | «لا يصحّ هذا الإجراء في حال المقالة الآن.» |
| `KB_SOURCE` | 409 | `kb_proposal_needs_source` | «لا ردّ مرسل في هذه التذكرة ولا مسودةٌ رُفضت لنقصٍ في القاعدة.» |
| `KB_PROPOSALS` | 409 | `kb_ticket_proposal_cap` | «اقتُرحت من هذه التذكرة مقالتان، وهو الحدّ.» |
| `KB_NOT_ENOUGH` | 422 | proposal outcome `NOT_ENOUGH` | «لم يجد سيمبول في التذكرة ما يكفي لمقالة. اكتبها بنفسك.» |
| `SEARCH` | 422 | `kb_search_query` | «اكتب كلمتين على الأقل للبحث.» |
| `INTERNAL` | 500 | an invariant no request can reach (listed below) | «تعذّر حفظ الطلب. أعد المحاولة، وإن تكرّر فأخبر من يدير التطبيق.» |

- A test introspects the bodies of every `ew_support_*` and `ew_kb_*` function for `CONSTRAINT = '…'`, plus every named constraint on the 15 tables. Each must map to a code above.
- **In the record step of a model call** (§8.1), every constraint except `support_draft_stale`, `support_draft_needs_open_call`, `support_ai_call_not_open`, `support_citation_not_published` and `support_review_not_pending` maps to `AI_OUTPUT_INVALID` (502), logged at `critical`. The server's own checks should have refused that output first. This covers:
  - the draft's value and shape checks: `support_draft_result`, `support_draft_kind`, `support_draft_body`, `support_draft_subject`, `support_draft_note`, `support_draft_category`, `support_draft_impact`, `support_draft_urgency`, `support_draft_escalate`, `support_draft_language`, `support_draft_shape`;
  - `support_citation_count`, `support_citation_not_verbatim` and `support_answer_needs_citation`;
  - `support_flag_code`, `support_flag_evidence` and `support_flag_evidence_verbatim`;
  - `kb_ai_version_needs_open_call`, and the `kb_versions_*` checks on a proposal.
- **Invariants that no request can reach map to `INTERNAL`** (500). They are logged at `critical` with the constraint name only, never the data. Outside a record step, the AI-output constraints above are also `INTERNAL`, because only a server bug reaches them there. The invariants are:
  - **calls:** `support_ai_finished_iff_outcome`, `support_ai_kind`, `support_ai_new_within_user`, `support_ai_outcome`, `support_ai_outcome_needs_record`, `support_ai_target`;
  - **tickets:** `support_ticket_status`, `support_ticket_number`, `support_ticket_managed_columns`, `support_clock_runs`, `support_close_reason`, `support_closed_iff_time`, `support_escalated_has_target`, `support_escalation_target`, `support_resolved_complete`, `support_unresolved_clear`, `support_purge_after_close`;
  - **messages:** `support_message_author`, `support_message_agent_reply`, `support_message_agent_token`, `support_message_reply_fk`, `support_agent_message_needs_sent_reply`;
  - **replies:** `support_reply_origin`, `support_reply_origin_draft`, `support_reply_review`, `support_reply_review_origin`, `support_reply_running_time`, `support_reply_state`, `support_reply_state_times`, `support_reply_contains_core`, `support_reply_immutable`;
  - **drafts:** `support_draft_rejection`, `support_draft_priority`, `support_citation_needs_new_draft`;
  - **flags:** `support_flag_source`, `support_flag_source_call`, `support_flag_state`, `support_flag_target`, `support_flag_target_state`, `support_flag_resolution`;
  - **escalations:** `support_escalation_return_time`;
  - **events:** `support_event_actor`, `support_event_detail`, `support_event_kind`, `support_event_target`;
  - **settings:** `support_notice_complete`;
  - **articles:** `kb_archived_time`, `kb_discarded_time`, `kb_article_managed_columns`, `kb_article_number`, `kb_ever_published`, `kb_published_has_version`, `kb_review_iff_reason`, `kb_review_reason`, `kb_version_bound`, `kb_version_origin`.
- `ew_begin_generation` keeps its campaign constraints and their existing codes.
- Anything not mapped would return 422 `CONSTRAINT` «الطلب يخالف قيداً. راجع القيم وحاول مرة أخرى.», and the introspection test fails on it.

### 6.5 Labels the client shows for the codes (`client/src/lib/support-labels.ts`; a test checks that every code has one)

| Group | Labels |
|---|---|
| Status | NEW «جديدة» · OPEN «مفتوحة» · PENDING «بانتظار العميل» · ESCALATED «مُصعَّدة» · RESOLVED «محلولة» · CLOSED «مغلقة» |
| Priority | URGENT «عاجلة» · HIGH «عالية» · NORMAL «عادية» · LOW «منخفضة» |
| Channel | MESSAGING «واتساب أو رسائل» · EMAIL «بريد» · PHONE «مكالمة» · IN_PERSON «حضوري» · WEB_FORM «نموذج جهة العمل» · OTHER «أخرى» |
| Reply kind | ANSWER «جوابٌ يحلّ المشكلة» · ASK_INFO «طلب معلومات» · UPDATE «إفادةٌ بالمتابعة» |
| Origin | AS_IS «كما كتبها سيمبول» · EDITED «عدّلتَها» · MANUAL «كتبتَها» · TEMPLATE «أسئلةٌ جاهزة» |
| Resolution | REPLIED «بالردّ» · BY_PHONE «بالهاتف» · IN_PERSON «حضورياً» · DUPLICATE «مكرّرة» · NOT_SUPPORT «ليست طلب دعم» · NO_RESPONSE «لم يردّ العميل» |
| Close reason | AFTER_RESOLVED «بعد أربعة أيام من حلّها» · IDLE «بلا نشاطٍ تسعين يوماً» · PROFESSION_CHANGED «تغيّرت مهنة الحساب» |
| Escalation target | TIER2 «فريق الدعم المتقدّم» · SUPERVISOR «المشرف» · VENDOR «المورّد أو الشركة المصنّعة» · FIELD_TECH «فنيّ ميداني» · OTHER_TEAM «فريقٌ آخر في جهة العمل» |
| Reject reason | WRONG_INFO «معلومةٌ خاطئة» · NOT_IN_KB «القاعدة لا تغطّي المسألة» · MISUNDERSTOOD «لم يفهم المشكلة» · TONE «الأسلوب غير مناسب» · TOO_LONG «أطول من اللازم» · INCOMPLETE «ناقصة» · OUTDATED_ARTICLE «المقالة قديمة» · OTHER «سببٌ آخر» |
| Article state | PROPOSED «اقتراح سيمبول» · DRAFT «مسودة» · PUBLISHED «منشورة» · ARCHIVED «مؤرشفة» · DISCARDED «متروكة» |
| Actor | EMPLOYEE «أنت» · ASSISTANT «سيمبول» · SYSTEM «النظام» |
| Events | TICKET_CREATED «فُتحت التذكرة» · FOLLOW_UP_CREATED «فُتحت تذكرة متابعة» · CUSTOMER_MESSAGE_ADDED «أُضيف ردّ العميل» · NOTE_ADDED «أُضيفت ملاحظة داخلية» · STATUS_CHANGED «تغيّرت الحال» · CLASSIFIED «صُنّفت» · SUBJECT_SET «غُيّر الموضوع» · DRAFT_REQUESTED «طُلبت مسودة» · DRAFT_PROPOSED «اقترح سيمبول مسودة» · DRAFT_FAILED «لم تكتمل المسودة» · DRAFT_REJECTED «رُفضت المسودة» · REPLY_PREPARED «جُهّز الردّ» · REVIEW_DONE «راجع سيمبول الردّ» · REVIEW_FAILED «تعذّرت المراجعة» · REVIEW_SKIPPED «أُرسل دون انتظار المراجعة» · FLAG_RAISED «تنبيه» · FLAG_HEEDED «أُخذ بالتنبيه» · FLAG_DISMISSED «تُجووز التنبيه» · REPLY_RELEASED «نُسخ الردّ» (COPY) / «شوركَ الردّ» (SHARE) / «قُرئ الردّ» (SCRIPT) · REPLY_SENT «أُرسل الردّ» · REPLY_WITHDRAWN «سُحب الردّ» · ESCALATED «صُعّدت» · ESCALATION_RETURNED «عاد التصعيد» · RESOLVED «حُلّت» · REOPENED «أُعيد فتحها» · TEXTS_PURGED «مُحيت نصوصها» · ARTICLE_CREATED «أُنشئت المقالة» · ARTICLE_PROPOSED «اقترح سيمبول مقالة» · ARTICLE_PROPOSAL_FAILED «لم يكتمل الاقتراح» · ARTICLE_VERSION_ADDED «نسخةٌ جديدة» · ARTICLE_PUBLISHED «اعتُمدت» · ARTICLE_ARCHIVED «أُرشفت» · ARTICLE_DISCARDED «تُركت» · ARTICLE_MARKED_REVIEW «عُلّمت: تحتاج مراجعة» · ARTICLE_REVIEW_CLEARED «رُفعت علامة المراجعة» |

### 6.6 Rate limits

| Limiter (server memory, key = user id) | Limit | Routes |
|---|---|---|
| `mutation` (existing) | 120 / min | every `POST` and `PUT` |
| `support_paste` | 60 / min | `mask-preview`, ticket creation, messages, follow-up |
| `support_ai` | 20 / min | drafts, reply review, KB review, proposals (the database caps are the real budget, §7.6) |
| `support_search` | 60 / min | `GET /kb?q=` |
| `support_read` | 300 / min | every `GET` |

As registration §5.2 notes, memory limits are per process. What costs money is limited in the database (§7.6), which holds across processes.

---

## 7. Deterministic rules (the AI is never the only guard)

### 7.1 Masking: server first, then the database

`support_rules.mask(text) → (masked, counts)` runs on every customer message, note, hint, rejection note and escalation note, before any database call.

1. **Normalize.** NFC; CRLF and CR become LF; remove U+200E, U+200F, U+202A–U+202E, U+2066–U+2069 and U+FEFF; tabs become spaces; trim trailing spaces on each line; collapse three or more blank lines to two; trim.
2. **Emails.** `[^\s@]+@[^\s@]+\.[^\s@]+` → «[بريد محذوف]».
3. **Links.** `(?i)\b(?:https?://|www\.)\S+` → «[رابط محذوف: {host}]». The host is the parsed hostname, lowercased and IDNA-encoded (for example `example.com`); it becomes «[رابط محذوف]» if parsing fails. Paths and queries can carry tokens or personal data; the host tells the employee which service was meant.
4. **Long numbers.** `\+?(?:[0-9٠-٩۰-۹][ -]?){8}[0-9٠-٩۰-۹](?:[ -]?[0-9٠-٩۰-۹])*` → «[رقم محذوف]». That is nine or more digits, Latin, Arabic-Indic or Persian, with single spaces or hyphens between them. It covers mobile and landline numbers, national IDs and iqamas, cards and IBANs. It keeps error and update codes of up to 8 digits, such as `0x80070005` and `KB5034441`.
5. The function is idempotent: `mask(mask(x)) == mask(x)`.

The database re-checks with `ew_support_contact_free` (`support_message_contact_free`, and the label, subject, hint and note constraints). Text that still holds an email or a run of nine or more digits is refused. Names inside free text cannot be found reliably. The desk notice and the paste step say so, and ask the employee to remove what is not needed.

### 7.2 Text rules (database + server)

- **Controls.** No control characters except LF in multi-line fields; no bidi controls; no leading or trailing whitespace (`ew_support_text_ok`).
- **Lengths.** As in §6.2, enforced by CHECK constraints.
- **Replies and articles** may carry the employer's phone, email or link, which the employee writes. They may not carry a national ID or iqama (10 digits starting with 1 or 2), a run of 13 or more digits, or an IBAN (`ew_support_kb_clean`).

### 7.3 Grounding (server, then database)

1. A draft whose kind is `ANSWER` needs 1–3 quotes. Each quote must be 8–300 characters, from an article that `search_knowledge_base` returned **in this call**, and a substring of that article's text after `kb_norm`.
   - Server: `OUTPUT_INVALID`.
   - Database: `support_answer_needs_citation` (deferred) and `support_citation_not_verbatim`. The version must also still be the published one (`support_citation_not_published`).
2. Every email, link and run of 7 or more digits in a draft's body must appear in one of the articles it quotes. Server: `OUTPUT_INVALID`.
3. The draft must come after a `read_ticket` call in the same attempt (server).
4. The suggested priority is computed by `ew_support_priority_for`. The model's text never sets it.
5. For a reply the employee edited or wrote:
   - the same contact rule produces the rule flag `LINK_NOT_IN_KB`, not a refusal: the employee may know a number the knowledge base lacks;
   - the grounding articles are the draft's quotes plus any article inserted from the tools button.

### 7.4 State machines (database)

- **Ticket.** The 18 rows of `support_ticket_transition`. `CLOSED` is final, except for the text purge.
  - A customer message moves `PENDING` or `RESOLVED` to `OPEN`.
  - A confirmed reply moves the ticket by kind: `ANSWER` → `RESOLVED`; `ASK_INFO` → `PENDING`; `UPDATE` → `OPEN`; while `ESCALATED`, `ASK_INFO` and `UPDATE` keep it `ESCALATED`, and `ANSWER` is refused.
  - Escalation is from `NEW`, `OPEN` or `PENDING` only; the return is `ESCALATED` → `OPEN`.
- **Reply.** `READY` → `RELEASED` → `SENT`; `READY` or `RELEASED` → `WITHDRAWN`. The text is immutable. Review: `PENDING` → `RUNNING` → `DONE`/`FAILED`/`SKIPPED`; `FAILED` → `RUNNING` (retry) or `SKIPPED`.
- **Draft.** Immutable, except for one rejection. Only the latest draft can become a reply.
- **Article.** `PROPOSED` → `DRAFT`, `PUBLISHED` or `DISCARDED`; `DRAFT` → `PUBLISHED` or `DISCARDED`; `PUBLISHED` ↔ `ARCHIVED`. Only the latest version is published. Versions are append-only.
- **Flag.** `OPEN` → `HEEDED` or `DISMISSED`, once. Its quote must be verbatim in the text it flags.

### 7.5 What "send" requires (database)

- Release needs `READY`, `sha256(body)` equal to the client's hash, no `OPEN` flag on the reply, and a review that is not `PENDING` or `RUNNING` (under 5 minutes old) unless the employee skipped it. A skip is logged.
- Confirming "sent" needs `RELEASED`. It writes the `AGENT` message, whose body must equal the reply's, in the same transaction.
- One live (`READY` or `RELEASED`) reply per ticket.
- A ticket closed by the system or a profession change withdraws its live reply.

### 7.6 Caps (database) and rates (memory)

| What | Limit | Constraint |
|---|---|---|
| Open tickets | 300 (30 for a new open account) | `support_open_ticket_cap` |
| Tickets created per 24 h | 200 (30) | `support_daily_ticket_cap` |
| Messages per ticket | 60 | `support_message_cap` |
| Pasted or typed messages per 24 h | 400 (60) | `support_daily_message_cap` |
| Articles | 300 (excluding discarded) | `kb_article_cap` |
| Versions per article / per 24 h | 30 / 100 | `kb_version_cap` / `kb_daily_version_cap` |
| AI calls at once per user | 1 (5-minute lease) | `support_ai_in_progress` |
| AI per kind: per 10 min / per day / per new account per day / app per day | `DRAFT` 10/60/20/800 · `REPLY_REVIEW` 10/60/20/600 · `ARTICLE_PROPOSAL` 3/10/3/150 · `ARTICLE_REVIEW` 5/20/5/200 | `support_ai_rate`, `support_ai_daily_cap`, `support_ai_new_account_daily_cap`, `support_ai_app_cap` |
| Drafts per ticket per 24 h | 8 | `support_ticket_draft_cap` |
| Proposals per ticket | 2 | `kb_ticket_proposal_cap` |
| App-wide AI per 24 h, campaigns included | 2,000; of which new open accounts together ≤ 400 | `generation_global_cap`, `generation_new_accounts_cap` |

- Only outcomes that may have been billed count (`ew_is_billable`).
- Deleting an account refunds nothing: tombstones keep the app-wide count. The per-kind app caps count live rows only, while the 2,000 cap counts tombstones too.
- **Why a new account gets 20 drafts a day.** Registration §9.3 E warned that 5 would stop a support employee in their first week. Twenty drafts and twenty reviews let a new employee work a normal day. The 400-a-day pool for all new accounts still bounds a burst of sign-ups.

### 7.7 Isolation and identity (database)

- FORCE RLS everywhere; the web role reads only its own rows.
- Every function reads `ew_current_user()` and checks for an active `SUPPORT` account. The ticket and article insert triggers check it again, `FOR SHARE` against a concurrent profession change.
- Customer text and model calls require the accepted desk notice (`support_notice_required`).

### 7.8 Time (database)

- SLA due times, the requester-wait clock, resolution times and automatic closing are computed in the database, never from the device clock.
- `ew_support_close_due()` runs when the home loads, for the session user; `purge` runs daily, for everyone.

### 7.9 Rule flags (server, no model; soft: shown, then decided)

`support_rules.rule_flags(core, kind, customer_language, grounding_texts) → [(code, evidence)]` runs on every prepared reply, `AS_IS` included.

| Code | When | Evidence |
|---|---|---|
| `PROMISE` | The core matches a promise pattern that no grounding text contains (after `kb_norm`). Arabic: `خلال \d+ (دقيقة\|دقائق\|ساعة\|ساعات\|يوم\|أيام)`, `غداً`, `اليوم نفسه`, `نضمن`, `مضمون`, `تعويض`, `استرداد`, `استرجاع المبلغ`, `مجاناً`, `\d+ ?(ريال\|ر\.س\|٪\|%)`. English: `within \d+ (minutes?\|hours?\|days?)`, `guarantee`, `refund`, `compensat`, `free of charge`, `\d+ ?(SAR\|%)`. | the matched phrase |
| `ASKS_SECRET` | The core contains `كلمة المرور`, `كلمة السر`, `رمز التحقق`, `الرمز المرسل`, `OTP`, `رقم البطاقة`, `CVV`, `رقم الهوية`, `الآيبان`, `password` or `verification code` | the matched phrase |
| `NO_QUESTION` | The kind is `ASK_INFO` and the core has no «؟» and no "?" | — |
| `LINK_NOT_IN_KB` | The core has an email, a link or 7+ digits that no grounding text contains | the token |
| `LANGUAGE_MISMATCH` | `language_of(core) ≠ language_of(last customer message)` (Arabic letters ≥ 30% of letters → AR) | — |
| `PRIORITY_BELOW_SUGGESTION` | Set in the database by `ew_support_set_ticket` | — |
| `RESOLVE_UNANSWERED` | Raised by `ew_support_resolve`. It refuses and asks for confirmation; once confirmed, the flag is stored as `DISMISSED` with `CONFIRMED`. | — |
