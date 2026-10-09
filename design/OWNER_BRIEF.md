# Owner brief — 2026-10-08 (verbatim Arabic, then an English rendering)

> هل هي اكثر من بوابه ام واحده وهذا بالنسبه لبوابه المهم والتوضيف، مفترض بعد تسجيل حساب جديد يفتح بوابه موحده (بوابه العمل لذوي الاعاقه بالنسبه للمهنه المحتاره في تسجيل الحساب) .
> صغر الخط والازرار ان امكن .
> راجع المهنه ومتطلباته مثدا المخزون يفتح المخزون وتظهر انشاء فاتوره شراء. ومايتطلبه مثل انشاء /اختيار من منسدل للقطع والايتم. عند انشاء قطعه تحديد سعرها. تظهر المجاميع ، اضافه فاتوره شراء وتسجل في المصاريف ، انشاء مسترجع من فاتوره سابقه … الخ
> ايضا التسويق ومايتطلبه من موظف التسويق والحملات . فهمت بحيث يكون جاهز للعمل. وكيف يراجع الدكاء الاصطناعي في الخلفيه ويكون مساعد مع الموظف بكيث لو كان الاجراء خاطىء يظهر رفع مع رساله الذكاء باسم المستخدم وسبب الخطاء .
> ايضا زر عائم صغير يملك ادوات بحيث يساعد الموظف لط اجراء المهام .
> ايضا بالنسبه للدعم الفني ومتطلبات(ابحث في المصادر عن الدعم الفني ومايتطلبه والرد على العملاء ويكون الموظف (يومن ان لوب بحيث يتخذ قرار بعد الذكاء الاصطناعي الذي يعمل ك دعم فني ويرد على العملاء … الخ . ) وجهز البوابه كامله لذلك وكيف يبدا العمل الموظف وكيف يتخذ القرارات

Earlier the same day: registration must be open, with no invitation. The design, buttons and components must be improved; the current ones are "bad and primitive". The interface and components should be built with 21st.dev.

## English rendering

1. **One portal.** After a new account registers, it opens ONE unified portal: the work portal for people with disabilities, for the profession chosen at sign-up. The app is one portal, not several.
2. **Size.** Make the font and the buttons smaller, if possible.
3. **Storekeeper portal.** It opens the inventory. The employee can:
   - create a purchase invoice;
   - create items, or pick them from a drop-down, setting an item's price when it is created;
   - see totals;
   - record a purchase invoice, which posts to expenses;
   - create a return from an earlier invoice;
   - and so on.
4. **Marketing portal.** Everything a marketing employee needs for campaigns, ready for real work.
5. **AI reviewer.** The AI reviews in the background and assists the employee. When an action is wrong, a flag appears with the AI's message, addressed to the user by name, giving the reason.
6. **Floating tools button.** A small floating button holds tools that help the employee carry out tasks.
7. **Technical support portal.** Research from sources what technical support requires, including replying to customers. The employee is the human in the loop: the AI acts as technical support and drafts replies to customers, and the employee decides. Prepare the full portal, including how the employee starts work and how they make decisions.

## Decisions taken for the owner (state them in specs; do not reopen)

- **Data.** Each account's work data (inventory, invoices, campaigns, tickets) is private to that account, with forced row-level security per user. Linking accounts to an employer or organisation is a later owner decision; design so it can be added without rewriting.
- **Size modes.**
  - "Compact" is the default and meets the owner's ask: smaller type and buttons, never below Apple's HIG minimum hit region of 44×44 pt for any input.
  - "Gaze" is the large mode: 72 px targets and 24 px gaps, as today.
  - The user chooses the mode during sign-up and can change it on the account screen. Both modes are tested.
- **AI.** The AI only proposes; it never decides or changes data by itself. Deterministic rules (database and server) block impossible actions. The AI reviewer flags suspicious but possible actions, addressing the user by name and giving the reason, and the user decides.
- **Support desk.** Customer messages are sent to the model provider (Anthropic) to draft replies; the owner asked for this. It must be named in the consent notice, with the minimum data sent.
- **Client.** The new client is React + TypeScript + Tailwind + shadcn/ui with 21st.dev components, in eyework/client. FastAPI serves it under the same strict CSP (self only).
- **Model.** claude-opus-5-5 via the Anthropic SDK, following the existing patterns in eyework/copywriter.py, prompt.py and self_check.py.
- **Unchanged.** Web only. Production-ready, with no mocks and no TODO.

## Owner update — 2026-10-09 (verbatim, then English). This overrides anything above or in any spec.

> لا حاجه لزر المهارات والمهام. ازلها.
> اضف ازرار للبدء فالمهام والعمل وكل مايتطلب كل مهنه.

1. **Remove the «المهامّ» and «المهارات» buttons.** Also remove the reading screens they open (portal-item, one task or skill per screen) from the user interface. The sourced tasks and skills stay in eyework/professions.py as internal data only. They decide which work tools each profession gets, and they ground the assistant. They are no longer screens a user reads. Keep the «المصادر» screen with the O*NET notice only if some O*NET-derived text is still shown to the user (for example, in an assistant answer); otherwise remove it as well, and say which you chose.
2. **Home is action buttons.** The profession's home opens with buttons that START real work, with nothing to read before it. These are examples; derive the full set from each profession's spec:
   - **Storekeeper:** «فاتورة شراء جديدة», «مرتجع من فاتورة», «صنف جديد», «المخزون», «المصاريف», «المجاميع».
   - **Marketing:** «حملة جديدة», «حملاتي», «ما ينتظر الاعتماد», «أدخل النتائج», «تقويم المحتوى».
   - **Technical support:** «التذاكر المفتوحة», «تذكرة جديدة», «بانتظار قراري», «قاعدة المعرفة».

   Each button opens a working screen, never a description. The floating tools button stays on every screen.
3. **Release rule.** The buttons are removed in the same release that adds the work buttons, so no profession's home is ever left empty or with a placeholder.

## Owner rule — 2026-10-09 (verbatim, then English)

> توقف ماهي المفاتيح ومادخلها … لاتضيف اي شي لم اطلبه

**Build only what the owner asked for.** Do not add any feature, screen, setting or step that the owner did not request. Where a spec needs something beyond the request to be safe, it must be the minimum: validation, rate limits, row isolation, or a deterministic rule that blocks an impossible action. List it under "Not requested, required for safety", with one line of why, so the owner can see it.

**Passkeys: the owner's decision.**

> اضف الباس كي ولكن كزر للدخول بدون اضافه في حسابي . كل شي احترافي مثل التطبيقات . تاكد

- The passkey is a sign-in button only («ادخل بمفتاح المرور» on the sign-in screen).
- Nothing on the account screen adds passkeys.
- The browser saves a passkey automatically after a password sign-in (WebAuthn conditional create, "automatic passkey upgrades"), as professional apps do.
- This is being implemented now in eyework/migrations/0007_passkey_hardening. New migrations in these specs start at 0008.
- Design nothing else around passkeys.

