# Technical support workspace (human in the loop)

Track spec for eyework. Status: ready to implement. Date: 2026-10-09.
The spec is in English; every string a user sees is Modern Standard Arabic and is given here exactly.
Migration: `NEXT_support_desk` (the integrator numbers it; it comes after `NEXT_open_registration`).

---

## 0. Summary

- **Where work starts.** Per the owner's update of 2026-10-09, the support home is six buttons that start work, with counts and nothing to read first: «بانتظار قراري», «التذاكر المفتوحة», «تذكرة جديدة», «بانتظار العميل», «المُصعَّدة», «قاعدة المعرفة». The day starts at «بانتظار قراري» (§3, §4.1).
- **How tickets arrive.** The employee creates each ticket by pasting what the customer sent (a chat, an email) or typing what was said on a call. There is no public customer form, because a public page on this origin would tell every customer that the employee uses an app for people who work with their eyes (§2.1).
- **The AI is the support agent; the employee is the decision.** For each new customer message, «سيمبول» (claude-opus-5-5):
  - classifies the ticket (category, and the impact and urgency from which the database computes the suggested priority);
  - drafts a reply grounded only in the account's own published knowledge-base articles and the ticket thread, quoting each article it relies on word for word;
  - says so when the knowledge base does not answer the question, and what is missing.
- **Five decisions, all the employee's.** «أرسل كما هي», «عدّل ثم أرسل», «اطلب معلومات», «صعّد», «ارفض المسودة» (with a reason, kept to improve the knowledge base). There are also resolving without a written reply, reopening and follow-ups. Every decision is a row in an append-only audit trail (§3.2).
- **What "send" does.** The app sends nothing. «أرسل» saves the exact final text. The employee then copies it, shares it to the channel app through the iOS share sheet, or reads it out on a call, and confirms «أرسلتُه». Only that press marks the ticket replied (§2.2).
- **Knowledge base.** Articles have the KCS structure (issue in the customer's words, environment, resolution, cause). The employee writes and approves them; the AI may propose an article from a solved ticket, and the proposal is used only after the employee approves it. A rejected draft that relied on a wrong article marks that article «تحتاج مراجعة» (§1.3, §5).
- **Guards that do not depend on the AI** (§7). The database refuses:
  - an answer without a verbatim quote from a published article;
  - customer text that still holds an email or a long number;
  - releasing a reply whose text differs from what was saved, or that has an open flag;
  - any write by another account or another profession;
  - model calls beyond the per-user, per-feature and app-wide caps, which are shared with the campaigns.
- **The AI reviewer** (§8.4). It checks replies the employee edited or wrote, and articles before they are published. Each flag is addressed to the user by name («يا سارة، …») with the reason. The employee heeds or dismisses it; the flag never blocks a decision, only an undecided release.
- **Privacy** (§10). Before anything is stored, the server removes emails, links and any run of nine or more digits (phones, national IDs, cards, IBANs).
  - Never sent to Anthropic: the customer's label, the employee's name, the ticket number and the channel.
  - The ticket's texts are deleted 30 days after it closes, and the codes-only audit after a year.
  - A desk notice, which the database requires, comes before the first paste.
- **Verified** (§5.6). The migration was checked on PostgreSQL 16.13:
  - it cycles up, down and up with identical schema dumps, from the registration migration and from empty, and down restores the base exactly even with live data;
  - 70 functional checks pass as the real `eyework_app` role;
  - the purge, account deletion, the shared AI cap and a concurrency race behave as specified.

### 0.1 Decisions this spec inherits (stated, not reopened)

- **Data.** Each account's tickets, knowledge base and audit are private to that account, under forced row-level security. Linking accounts to an employer is a later owner decision. Every table here keys on `user_id` and every function reads it from the session, so an organisation key can be added later beside it without rewriting.
- **Size modes.** «باللمس» (compact, the default: smaller type, and no hit region under 44×44 pt) and «بتتبّع العين» (gaze: 72 px targets, 24 px gaps, no scrolling inside a step). The user chooses at sign-up and can change it in «حسابي». Both modes are specified and tested.
- **AI.** The AI only proposes. Deterministic rules in the database and server block impossible actions. The AI reviewer flags actions that are possible but suspicious, by name and with the reason, and the user decides.
- **Support desk.** Customer messages are sent to Anthropic to draft replies, at the owner's request. Anthropic is named in the consent notice, and only the minimum is sent.
- **Client and model.** React + TypeScript + Tailwind + shadcn/ui with 21st.dev components, in `eyework/client`, served by FastAPI under the self-only CSP. The model is `claude-opus-5-5` through the Anthropic SDK, following `copywriter.py`, `prompt.py` and `self_check.py`. Web only. Production-ready: no mocks, no TODO.
- **Owner update of 2026-10-09.** The «المهامّ» and «المهارات» screens are gone. The sourced tasks and skills stay in `professions.py` as internal data that decide which tools the profession gets (§1.2). Home is action buttons, and the floating tools button is on every screen.

### 0.2 What this track changes elsewhere

| File | Change |
|---|---|
| `eyework/professions.py` | `_SUPPORT.tools = ("SUPPORT_DESK",)`. The tagline becomes «ردودٌ يكتبها سيمبول وتعتمدها أنت» (32 characters; registration §9.3 H). Tasks and skills stay as data. |
| `eyework/support_rules.py` (new, pure) | Masking, language, composing a reply, the rule flags, the priority matrix, the transitions, the AI limits, template questions and phrases (§7, §8). |
| `eyework/support_prompt.py` (new, pure) | The drafter's and reviewers' prompts, tools and output schemas (§8). |
| `eyework/support_notice.py` (new, pure) | The desk notice's title, lines, version and digests (§10.2). |
| `eyework/support_agent.py` (new) | The Anthropic client loop. It joins `copywriter.py` in the architecture test's allowlist of modules that may import `anthropic`. |
| `eyework/scripts/support_smoke.py` + `support_smoke_cases.json` (new) | The operator's pre-release measurement with synthetic cases (§8.7). |
| `eyework/support.py` (new) | The service layer: transactions, database errors mapped to `ErrorSpec`. |
| `eyework/web/routes_support.py` (new), `web/errors.py`, `web/schemas.py`, `web/deps.py` | Routes, Arabic errors, schemas and limiters (§6). |
| `eyework/admin.py` | `purge` runs §5.5. `set-profession` away from SUPPORT closes the account's open tickets (§5.5). |
| `eyework/terms.py` | The SUPPORT line of the registration notice (§10.3). |
| `eyework/client` | The screens in §4, the support entry of `lib/workspace.ts` (§4.0), and the tools in §9. |
| `README.md` | The «ما لم يُبنَ» item on a support tool is removed. «ما يغادر بنيتنا» and the retention table gain the rows in §10. |

---

## 1. Sources and the role's requirements

### 1.1 Sources fetched for this spec (all on 2026-10-09)

| # | Source | URL | Used for |
|---|---|---|---|
| S1 | O*NET OnLine, 15-1232.00 Computer User Support Specialists ("Updated 2026") | https://www.onetonline.org/link/details/15-1232.00 | 16 tasks with importance; work activities; essential and transferable skills; work context; "Helpdesk or call center software"; sample job titles («Help Desk Analyst», «Technical Support Specialist») |
| S2 | ILO, ISCO-08 structure and definitions (workbook) | https://www.ilo.org/ilostat-files/ISCO/newdocs-08-2021/ISCO-08/ISCO-08%20EN%20Structure%20and%20definitions.xlsx | Unit group 3512, *ICT user support technicians*: definition and tasks (a)–(i) |
| S3 | Zendesk, *About the ticket lifecycle and ticket statuses* | https://support.zendesk.com/hc/en-us/articles/8263915942938-About-the-ticket-lifecycle-and-ticket-statuses | New, Open, Pending, On-hold, Solved, Closed; a requester reply returns Pending or Solved to Open; a reply to a closed ticket creates a follow-up |
| S4 | Zendesk, *About the standard Support automations* | https://support.zendesk.com/hc/en-us/articles/4408835051546-About-the-standard-Support-automations | "closes a ticket four days after it is set to solved"; adjustable "up to 28 days"; cannot be disabled |
| S5 | Zendesk API, Tickets | https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/ | Status values; priority "urgent", "high", "normal", "low"; ticket types |
| S6 | Zendesk, *Defining SLA policies* | https://support.zendesk.com/hc/en-us/articles/4408829459866-Defining-SLA-policies | First reply time; requester wait time ("pauses when the ticket has a Pending status"); a target per priority; calendar or business hours |
| S7 | Atlassian, *Escalation policies for effective incident management* | https://www.atlassian.com/incident-management/on-call/escalation-policies | Hierarchical escalation (by seniority) and functional escalation (by skills or systems knowledge) |
| S8 | Atlassian, *Best practices for managing escalations* (Jira Service Management) | https://support.atlassian.com/jira-service-management-cloud/docs/best-practices-for-managing-escalations/ | An "Escalated" status; statuses per tier; internal versus public comments |
| S9 | Atlassian, *Create an impact urgency priority matrix* | https://support.atlassian.com/jira-service-management-cloud/docs/how-do-i-create-a-matrix-using-impact-and-urgency-values/ | Priority from impact × urgency; "the priority values listed here are just examples" |
| S10 | Consortium for Service Innovation, KCS v6 Practices Guide: index; Technique 5.2 *Article State*; 5.1 *Article Structure*; 1.2 *Capture the Requestor's Context*; 4.1 *Reuse is Review*; 4.2 *Flag It or Fix It* | https://library.serviceinnovation.org/KCS/KCS_v6/KCS_v6_Practices_Guide ; …/030/040/010/030 ; …/030/040/010/020 ; …/030/030/010/020 ; …/030/030/040/020 ; …/030/030/040/030 | Article confidence states; the issue/environment/resolution/cause structure; issue in the requestor's words; reuse is review; flag it or fix it |
| S11 | Help Scout, *Talking to customers* | https://helpscout.com/talking-to-customers/ | Tone: friendly but professional, positive language, brief not brusque, get the name right, steps in order, apologize without lingering, admit what you don't know, offer further help |
| S12 | Anthropic, *Customer support agent* | https://platform.claude.com/docs/en/about-claude/use-case-guides/customer-support-chat | Splitting support into tasks; escalation accuracy as a success criterion; guardrails (citations, cross-checking against policy, no contractual commitments, jailbreak mitigation, removing PII) |
| S13 | Anthropic, *Reduce hallucinations* | https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations | Allow "I don't know"; ground in direct quotes; verify with citations and retract unsupported claims; restrict to the provided documents |
| S14 | Anthropic, *Mitigate jailbreaks and prompt injections* | https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks | Third-party content only in tool results; say what it is; state the policy in the system prompt; JSON-encode; keep your own instructions out of tool results; least privilege |
| S15 | Anthropic, *Citations* | https://platform.claude.com/docs/en/build-with-claude/citations | "Citations and structured outputs are incompatible" (400) |
| S16 | Anthropic, *Search results* | https://platform.claude.com/docs/en/build-with-claude/search-results | `search_result` blocks returned from a custom tool; citations "disabled by default" |
| S17 | Anthropic, *Structured outputs* | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | `output_config.format`; no `minLength`/`maxLength`; `minItems` 0 or 1; enum capitalization not guaranteed; works with tools |
| S18 | Anthropic, *Refusals and fallback* | https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback | `fallbacks: "default"` with header `server-side-fallback-2026-07-01`; the response names the serving model |
| S19 | Anthropic, *Prompt caching* | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | Minimum cacheable prompt of 512 tokens for Claude Opus 5.5 |
| S20 | Anthropic, *Effort* | https://platform.claude.com/docs/en/build-with-claude/effort | Opus 5.5 defaults to `medium`; set it explicitly |
| S21 | Anthropic, *API and data retention* | https://platform.claude.com/docs/en/manage-claude/api-and-data-retention | ZDR on request; flagged content kept up to 2 years; structured-output schemas cached up to 24 h, so no personal data in schemas |
| S22 | Anthropic Privacy Center, *How long do you store my organization's data?* | https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data | API inputs and outputs deleted "within 30 days"; up to 2 years if flagged |
| S23 | SDAIA, National Data Governance Platform, knowledge centre (PDPL FAQ) | https://dgp.sdaia.gov.sa/wps/portal/pdp/knowledgecenter | Minimum data (Art. 11); no fixed retention period, keep only while needed (Art. 18); applies to processing about residents from abroad (Art. 2); controller and processor (Art. 1 ¶18–19) |
| S24 | Personal Data Protection Law, official text (PDF linked from S23) | https://dgp.sdaia.gov.sa/wps/wcm/connect/d60cac13-b94f-4e58-9af5-14c4979c376d/ (نظام_حماية_البيانات_الشخصية.pdf) | Arts. 11, 12, 18, 19 and 29 (transfer outside the Kingdom) |
| S25 | Regulation on Personal Data Transfer outside the Kingdom, version 02, August 2024 (PDF linked from S23) | https://dgp.sdaia.gov.sa/wps/wcm/connect/666d32b6-b6fd-4296-8be2-cce891ebca52/ (لائحة نقل البيانات خارج المملكة.pdf) | Art. 7: the controller's risk assessment before transferring personal data abroad, and what it must contain |
| S26 | MDN, *Clipboard API* (security considerations) and *Navigator.share()*; MDN browser-compat-data `api/Clipboard.json`, `api/Navigator.json` | https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API ; https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share ; https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/Clipboard.json ; https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/Navigator.json | Safari: writing needs transient activation, and a read shows a "Paste" prompt; `writeText`/`readText` since Safari 13.1 (iOS mirrors it); `navigator.share` since 12.1, which needs transient activation and throws `AbortError` when cancelled |

### 1.2 What the role requires, and what this workspace does about it

O*NET's summary of the occupation (S1): "Provide technical assistance to computer users. Answer questions or resolve computer problems for clients in person, via telephone, or electronically."
ISCO-08 3512 (S2) says the same "directly or by telephone, email or other electronic means", covering "software, hardware, computer peripheral equipment, networks, databases and the Internet".

Per the owner's update, the tasks below are no longer screens. They decide what this workspace is for. A task is **in the workspace** only if a tool here performs part of it; the rest happens in the employer's systems or on site.

| O*NET task (importance) / ISCO-08 3512 task | In this workspace | How |
|---|---|---|
| Answer user inquiries regarding computer software or hardware operation to resolve problems (70) / ISCO (a) | **Yes** | The ticket, the draft and the five decisions (§3) |
| Read technical manuals, confer with users, or conduct computer diagnostics to investigate and resolve problems (74) / ISCO (h) "consulting user guides, technical manuals and other documents" | **Partly** | Searching the knowledge base; «اطلب معلومات» with diagnostic questions (§8.6). The diagnostics themselves happen on the employer's systems. |
| Maintain records of daily … problems and remedial actions taken (62) / ISCO (f) | **Yes** | The ticket, its internal notes and the audit trail (§5, `support_events`) |
| Refer major hardware or software problems or defective products to vendors or technicians for service (60) | **Yes** | «صعّد» to `VENDOR`, `FIELD_TECH`, `TIER2`, `SUPERVISOR` or `OTHER_TEAM`, with a copyable summary (§9) |
| Develop training materials and procedures, or train users (58) | **Partly** | Knowledge-base articles: procedures written for customers (§4.10) |
| Oversee daily performance (75); set up equipment (74); install and repair (69); confer to set requirements (68); enter commands and observe (64); prepare evaluations (60); inspect equipment (55); read trade magazines (51) / ISCO (b)(c)(d)(e)(g)(i) | No | The employer's systems or on site. The app does not claim them. |

| Skill (S1, importance) | Where the workspace supports it |
|---|---|
| Active Listening (75), Reading Comprehension (75) | The thread is shown one message at a time, and the draft quotes the article it relies on |
| Writing (63), Service Orientation (53), Social Perceptiveness (53) | The drafter's style rules from S11, and the reviewer's `TONE` check |
| Critical Thinking (69), Complex Problem Solving (66), Troubleshooting (50) | «اطلب معلومات» with diagnostic questions; CANNOT_ANSWER tells the employee what is missing |
| Judgment and Decision Making (56) | Every outcome is the employee's press; the AI's suggestions are labelled as suggestions |
| Time Management (50) | SLA chips and the queue order (§4.3) |

Work context (S1): email "every day" (100%), telephone conversations, and dealing with external customers.
That is why channels are recorded, and why «اقرأه للعميل» exists for calls.

### 1.3 Established practice this workspace follows

**Lifecycle (S3, S4).** The statuses map to Zendesk's:

| This app | Zendesk | Meaning here |
|---|---|---|
| `NEW` «جديدة» | New | Created; no reply sent, nothing decided |
| `OPEN` «مفتوحة» | Open | Waiting for the employee |
| `PENDING` «بانتظار العميل» | Pending | Waiting for the customer's answer to a request for information |
| `ESCALATED` «مُصعَّدة» | On-hold | Waiting for someone other than the customer |
| `RESOLVED` «محلولة» | Solved | A solution was sent or given |
| `CLOSED` «مغلقة» | Closed | Final; only the system sets it |

- A customer's reply moves `PENDING` or `RESOLVED` back to `OPEN`.
- `RESOLVED` closes automatically after 4 days. That is Zendesk's default (adjustable "up to 28 days"); this app fixes it at 4.
- A customer reply after `CLOSED` starts a follow-up ticket that points to the old one. It does not reopen it.

**Priority and SLA (S5, S6, S9).**

- Four priorities, as in Zendesk: `URGENT`, `HIGH`, `NORMAL`, `LOW`.
- Two clocks, as Zendesk defines them:
  - first reply time, from creation to the first reply the employee confirms sent;
  - requester wait time, which runs in `NEW`, `OPEN` and `ESCALATED` and pauses in `PENDING`.
- Targets are set per priority, in calendar hours. Business hours would need a work calendar the account does not have.
- The default targets are this app's choice, not a standard, and the employee can change them (§4.12): `URGENT` 1 h / 8 h, `HIGH` 4 h / 24 h, `NORMAL` 8 h / 72 h, `LOW` 24 h / 120 h.
- The suggested priority comes from an impact × urgency matrix, as in S9's example. Its values are this app's own (S9 itself says "just examples"):

| impact \ urgency | STOPPED (work stopped) | DEGRADED (works with difficulty) | REQUEST (question or request) |
|---|---|---|---|
| WIDESPREAD (more than one user or a whole service) | URGENT | HIGH | NORMAL |
| SINGLE | HIGH | NORMAL | LOW |
| …with `security_concern` | at least HIGH | at least HIGH | at least HIGH |

**Categories.** These come from the scope in S1's summary ("printing, installation, word processing, electronic mail, and operating systems") and S2's definition ("software, hardware, computer peripheral equipment, networks, databases and the Internet"):
`ACCOUNT` «الحساب والدخول», `SOFTWARE` «البرامج والتطبيقات», `HARDWARE` «الأجهزة», `PRINTING` «الطابعات والملحقات», `NETWORK` «الشبكة والإنترنت», `EMAIL` «البريد الإلكتروني», `INSTALL` «التثبيت والإعداد», `HOW_TO` «سؤال عن الاستخدام», `OTHER` «أخرى».

**Escalation (S1, S7, S8).**

- Escalation is functional (to whoever has the skills) or hierarchical (by seniority).
- The targets here are `TIER2` «فريق الدعم المتقدّم», `VENDOR` «المورّد أو الشركة المصنّعة» (S1: "refer … to vendors or technicians"), `FIELD_TECH` «فنيّ ميداني», `OTHER_TEAM` «فريقٌ آخر في جهة العمل», and the hierarchical `SUPERVISOR` «المشرف».
- An escalated ticket has its own status (S8). The escalation note is internal; the customer gets a separate update reply.

**Knowledge base (S10, KCS v6).**

- An article has an issue "in the requestor's words", an environment, a resolution (numbered steps) and an optional cause.
- KCS confidence states map to this app's states:

| KCS | Here |
|---|---|
| Work in Progress / Not Validated | `PROPOSED` (from the AI, untouched) and `DRAFT` (the employee's, unapproved) |
| Validated | `PUBLISHED` (approved by the employee; the only articles the AI reads) |
| Archived | `ARCHIVED` |

- "Reuse is review": `reuse_count` counts sent replies that quoted the article.
- "Flag it or fix it": a draft rejected as wrong marks the articles it quoted «تحتاج مراجعة», and the employee fixes the article or clears the mark.

**Tone (S11).** The rules are listed in the drafter's prompt (§8.2):

- friendly but professional;
- positive language ("Customers don't care about what you can't do");
- brief, not brusque;
- numbered steps in order;
- a sincere apology that does not linger;
- "Admit what you don't know";
- offer further help.

### 1.4 Human-in-the-loop drafting: Anthropic's guidance and how it is applied

| Guidance | Applied as |
|---|---|
| Break support into tasks; measure escalation accuracy (S12) | Classification, drafting, the escalation suggestion, review and article proposals are separate calls with separate schemas and limits |
| Ground in the provided information; cite; no contractual commitments; remove PII (S12) | The KB-only rule; the `UNAUTHORIZED_PROMISE` and `PROMISE` flags; masking before storage (§7.1) |
| "Allow Claude to say 'I don't know'" (S13) | `CANNOT_ANSWER` with `note_to_employee`; the UI shows it as useful, not as an error |
| "Verify with citations … If it can't find a quote, it must retract the claim"; "Explicitly instruct Claude to only use information from provided documents" (S13) | Every `ANSWER` carries 1–3 verbatim quotes, checked three times: by the self-check tool, by the server, and by a database trigger (`support_citation_not_verbatim`, `support_answer_needs_citation`) |
| Put third-party content only in tool results, say what it is, JSON-encode it, and keep your own instructions in the user turn (S14) | The thread comes from the `read_ticket` tool as a JSON string with a stated source; articles come as `search_result` blocks from `search_knowledge_base`; the employee's redraft request is in the user turn; the model has no tool that writes |
| Citations cannot be combined with structured outputs (S15); search results can come from a custom tool with citations off by default (S16) | The quotes are a field of the JSON output, verified by our code. The API's citation feature is not enabled. |
| No length constraints in the schema, and enum capitalization is not guaranteed (S17) | Lengths and counts are checked in the server and the database; enums are compared case-insensitively |
| `fallbacks: "default"` (S18); effort `medium` (S20); a 512-token caching minimum (S19) | As in `copywriter.py`. The system prompt and tools come first and do not change, so they cache. |
| Retention (S21, S22) | The notice says 30 days, and up to 2 years if flagged. The schemas hold no customer data. |

### 1.5 Saudi rules, checked against official sources

What this spec relies on, from the official PDPL text and SDAIA's FAQ (S23–S25):

- **Art. 11(3):** "the content of personal data must be appropriate and limited to the minimum necessary to achieve the purpose of collecting it" (translated). This is why the server masks contacts and IDs before storing anything, and sends the model only the thread, never the customer label.
- **Art. 18(1):** destroy personal data once the purpose of collecting it ends. This is why a closed ticket's texts are deleted after 30 days. The FAQ confirms the law sets no fixed period.
- **Art. 29:** transfer outside the Kingdom is allowed for listed purposes, provided it does not harm national security, the destination has an adequate level of protection by the competent authority's assessment, and only the minimum data is transferred.
- **Transfer Regulation, Art. 7:** the controller must carry out a risk assessment before certain transfers (exemption cases, and sensitive data continuously or at large scale). The assessment must cover the purpose and legal basis, the nature of the transfer, the safeguards, the minimum-data measures, the impacts and the mitigations.
- **Controller and processor (Art. 1 ¶18–19, per the FAQ).** The customers belong to the employer, so the employer decides why their messages are processed and is the controller. This app and Anthropic act for it. Whether the employer's basis and Art. 29's conditions are met is a legal question, not an engineering one: open decision 1 (§12).

**Unverified (not checked against an official source):** whether any Saudi rule requires telling a customer that a reply was drafted with AI. That is open decision 3; by default nothing is added.

**Not relevant here:** VAT, ZATCA and advertising rules. The desk issues no invoices and publishes nothing.

---

## 2. Decisions of this track

### 2.1 How tickets arrive: the employee creates them

**Chosen.** «تذكرة جديدة» takes:

- the channel: «واتساب أو رسائل», «بريد», «مكالمة», «حضوري», «نموذج جهة العمل», «أخرى»;
- the customer's message, pasted with «الصق من الحافظة» or typed;
- optionally, a short label for the customer, a subject and a priority.

Later customer messages are pasted into the same ticket with «أضف ردّ العميل».

**Not built: a public per-account customer form.**

1. **It would expose the employee.** A form served from this origin tells every customer of the employer that the employee uses this app. The README treats the list of users as health information ("قائمة مستخدمي هذا التطبيق معلومةٌ صحّية").
2. **The abuse surface is new.** Unauthenticated strangers would write third-party text into a database that holds health-adjacent data. Abuse protection that works on phones is a third-party challenge, which the self-only CSP forbids and which would send visitors' data elsewhere. Proof-of-work is weak on phones.
3. **It could not complete the loop.** The app sends no email, so a form can neither acknowledge receipt nor deliver replies. That would need a public status page with a secret link: another surface.
4. **The channels already exist.** They are the employer's (S1: email every day, telephone). The desk's value is the decision, not the channel.

**Cost.** One paste per message. Safari shows its own "Paste" prompt after the press, which works by touch and by dwell (S26), and the text field is the fallback.

### 2.2 What «أرسل» does, exactly

1. **Prepare.** The server composes and saves the final text. In Arabic that is «مرحباً {label}،» or «مرحباً،», then the core, then the signature; in English, «Hello {label},» or «Hello,». The reply is `READY`, with a SHA-256 of the text.
2. **Review.** If the employee edited the draft or wrote the reply, the AI reviewer runs (§8.4). Rule flags are computed at once.
3. **Release.** One press:
   - «انسخ الردّ» calls `navigator.clipboard.writeText(text)` inside the press, because Safari requires transient activation for writing (S26);
   - «شارك الردّ» calls `navigator.share({ text })`, which opens the iOS share sheet to WhatsApp, Mail, Messages and so on (S26); `AbortError` means not shared, and nothing is recorded;
   - «اقرأه للعميل», for phone and in-person tickets, shows the text alone, page by page.

   The client sends `{via, body_sha256}`. The server records `RELEASED` only if the hash equals the saved text, no flag on the reply is still open, and no review is pending, unless the employee chose «أرسل دون انتظار المراجعة».
4. **The employee sends it in their own channel.** The app cannot see this happen.
5. **Confirm.** Back in the app, the reply screen and the home count «بانتظار قراري» ask «هل أرسلتَ الردّ إلى العميل؟».
   - «نعم، أرسلته» marks it `SENT`: the reply is added to the thread, the ticket moves according to the reply's kind, the first-reply time is set, and the quoted articles' reuse is counted.
   - «لا، لم أرسله» marks it `WITHDRAWN`, and the ticket is unchanged.

The app never sends email or messages, calls no messaging API and has no webhook. Nothing reaches a customer without the employee's press, and nothing is counted as sent without their second press.

### 2.3 What the AI does and does not do

| Does (a proposal) | Does not |
|---|---|
| Suggests a category, impact, urgency and security concern; the database computes the suggested priority | Set the ticket's category, priority or status |
| Drafts an `ANSWER`, `ASK_INFO` or `UPDATE` with verbatim quotes, or says `CANNOT_ANSWER` or `NOT_SUPPORT` | Send, release or confirm anything |
| Suggests an escalation target and a subject | Read unpublished articles, or another account's anything |
| Reviews replies the employee edited or wrote, and articles before they are published | See the customer's label, the employee's name, the ticket number or the channel |
| Proposes an article from a ticket | Publish an article, or use general knowledge for facts |

### 2.4 Integration with the other tracks (for the integrator)

- **Depends on `NEXT_open_registration`** (registration spec v2): `ew_new_open_account(uuid)`, `attempt_tombstones.new_account`, `ew_is_billable`, `ew_attempt_settle_once`, `ew_forbid_update`, `ew_riyadh_today` and `ew_my_display_name` (0003). Its `ew_begin_generation` body is replaced here with two marked lines, and restored word for word by the down migration.
- **`ew_ai_spend(p_new_only boolean)` is the one function that sums AI ledgers.**
  - This migration defines it over `generation_attempts`, `support_ai_calls` and `attempt_tombstones`, and points `ew_begin_generation` at it.
  - The work-tools draft also defines `ew_ai_spend(boolean)`. Whichever migration lands second must `CREATE OR REPLACE` it to sum every ledger.
  - The DB test `test_global_cap_counts_every_ledger` (§11.1, DB50) lists every table with `outcome`, `started_at` and `new_account` columns and fails if one is not counted.
- **Supersedes the support part of the work-tools draft** (`work_sql/migrations/0008_work_tools.up.sql`): `support_tickets`, `support_ticket_actions`, `reply_requests`, `reply_options`, the `REPLY` AI feature, and the `ew_reply_*` and `ew_support_*` functions. The table name `support_tickets` collides, so the integrator drops that section of the draft. Its shared `ai_features`/`ai_calls` layer may stay, with `ew_ai_spend` merged as above.
- **Consent.** Registration §9.3, items A–H, are supplied in §10.3.
- **Visual track (v2 client).** This spec uses its size tokens (`h-ctl`, `gap-tg`, `row`, `fab`), its `AIFlag`, `ToolsFab`, `Stepper`, `Sheet`, `DataTable`, `RadioCards`, `EmptyState` and `Toast`, and the 21st.dev `approval-card`, `inline-citation` and `question-tool` it adapted. It replaces the SUPPORT placeholder in `lib/workspace.ts` with §4.0.
- **«المصادر».** This workspace shows no O*NET-derived text, so it neither needs nor removes the «المصادر» screen. The owner's rule keeps that screen only if another track shows O*NET text.
- **«اسأل سيمبول» in the shared tools button** is another track's tool. In this workspace it must not receive ticket content (§9).
