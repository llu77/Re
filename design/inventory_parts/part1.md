# Storekeeper workspace: inventory and purchasing

Track spec for eyework. Status: ready to implement. Date: 2026-10-09.
The spec is in English; every string the user sees is Modern Standard Arabic and is given here verbatim.

---

## 0. Summary

The storekeeper portal opens on the inventory. The first action on screen is «فاتورة شراء جديدة». An employee records a supplier's invoice line by line. In each line they pick an item from a searchable list, or create the item on the spot with its unit and its purchase price. They see the subtotal, the VAT and the total, compare them with the printed invoice, and post it.

Posting does three things in one transaction:

- it writes stock-in movements at cost;
- it writes an entry in the purchases (expense) ledger;
- it takes the next number in the account's own gapless sequence.

Corrections never edit a posted document. Goods sent back become a return («مرتجع») drawn from the posted invoice's own lines. An invoice recorded by mistake is cancelled by a reversal («قيد عكسي»). The module also has:

- a stock-on-hand view at moving-average cost;
- issue, count and opening-balance vouchers;
- an expenses view with totals by month or by range;
- a dashboard with the totals the owner asked for.

**The AI reviewer, «مراجعة سيمبول».** It runs when the employee presses «راجِع وسجّل». It sits beside deterministic rules and never replaces them.

- **Hard rules** live in PostgreSQL and block what is impossible. Examples: a return larger than what remains on the line, stock below zero, a posted document being edited, a return with no reason.
- **Rule flags** are computed in SQL from the account's own history. They catch what is possible but suspicious: a price ten times the median, a duplicate supplier invoice number, VAT that is not 15%, a printed total that differs.
- **AI flags** come from claude-opus-5-5. They cover what rules cannot judge: a price that looks implausible for an item with no history, a unit that does not fit the item, a new item that is probably an existing one under another name, a return reason that does not fit the goods.

Each flag addresses the employee by name and gives the reason. The employee decides. The database refuses to post until every flag on the current content has been acknowledged, and it keeps that acknowledgment with the document. The AI never blocks: when it is unavailable, off or over its limit, posting goes ahead with the rule flags alone.

**Decisions already taken by the owner** (OWNER_BRIEF.md; not reopened here):

- **One unified portal.** This portal is the storekeeper's view of it.
- **Data is private to each account.** Row-level security is forced and keyed to `ew_current_user()`. Employer linking is a later decision; nothing here assumes one account per business, and §4.1 says what linking would add.
- **Two size modes.** Compact (≥ 44×44 pt) and gaze (72 px targets, 24 px gaps, no scrolling inside a step). Both are tested.
- **The AI proposes and never decides.** Deterministic rules block what is impossible.
- **Model and SDK.** claude-opus-5-5 through the Anthropic SDK, following `copywriter.py`, `prompt.py` and `self_check.py`.
- **Client.** React, TypeScript, Tailwind, shadcn/ui and 21st.dev components, served by FastAPI under the existing self-only CSP.

**Verified before writing** (§4.2 and §12):

- The migration in §4 goes up, down and up on PostgreSQL 16.13 on top of main's 0001–0006 and the registration track's 0007, with identical `pg_dump --schema-only` output each way. A full rollback to empty and back up gives the same schema.
- 96 functional checks pass, run as the real `eyework_app` role.

**Integration notes for whoever numbers the migrations** (these are not owner decisions):

1. **Order.** The migration is `NEXT_inventory`. It must run after the registration track's 0007, because it uses `ew_new_open_account()` and the `new_account` columns. It replaces `ew_begin_generation` with 0007's body plus two marked lines.
2. **Overlap with the work-tools draft.** The draft `redesign/work_sql/migrations/0008_work_tools.up.sql` (uncommitted, no down file) has its own stock register: `stock_items`, `stock_movements`, `stock_receipts` and receipt lines. Shipping both would give one item two balances. This module covers that ground with purchasing, returns, VAT and cost, so the draft's stock register should be dropped. Its receipt reader (photo to lines) could later fill a purchase-invoice draft through the line API in §5. All tables here are prefixed `inv_`, so nothing collides by name.
3. **Shared AI ledger.** If the draft's shared `ai_calls` ledger lands, `inv_review_calls` should become its feature `PURCHASE_REVIEW`. The invariants to keep are in §7.5:
   - every call is counted once in the app-wide 2,000;
   - new open accounts draw from the shared pool of 400;
   - deleting an account leaves tombstones.

   Until then, the `ew_begin_generation` replacement in §4.3 counts `inv_review_calls`.

---

## 1. Sources and the role's requirements

### 1.1 Sources fetched for this spec

| # | Source | URL (fetched 2026-10-09) | Used for |
|---|---|---|---|
| S1 | O*NET OnLine 43-5071.00, Shipping, Receiving, and Inventory Clerks | https://www.onetonline.org/link/details/43-5071.00 | The role's tasks and importance (already in `professions.py`); "Inventory management software", "Accounting software" and "Procurement software" listed as the role's software |
| S2 | O*NET OnLine 43-3061.00, Procurement Clerks | https://www.onetonline.org/link/details/43-3061.00 | The purchasing tasks a small-business storekeeper also does: compare bills with orders, keep purchasing files and price lists, check stock sufficiency and reorder, track inventory movement for bookkeeping |
| S3 | ZATCA, *Guideline for Tax Invoicing and Records under VAT Provisions*, Version 3, May 2026 | https://zatca.gov.sa/en/HelpCenter/guidelines/Documents/Guideline-for-Tax-Invoicing-and-Records-under-VAT-Provisions.pdf | 15% standard rate (§1.3); tax invoice contents (§4.2.3); Arabic, numerals and invoice numbers (§4.2.1); rounding to the halala (§4.2.4, ex. 6); simplified invoice may state a VAT-inclusive total (§4.3.2); credit and debit notes are the supplier's and reference the original invoice (§7, §7.2); records kept 6 years, in the Kingdom, in Arabic, with anti-tampering controls (§8.3); input tax needs a tax invoice (§9.1) |
| S4 | ZATCA, *E-invoicing Regulation* (English, unofficial translation) | https://zatca.gov.sa/en/E-Invoicing/Introduction/LawsAndRegulations/Documents/E-invoicing-Regulations.pdf | Who must issue e-invoices (Art. 3): the taxable supplier, or a customer issuing on the supplier's behalf. A purchaser recording received invoices issues nothing |
| S5 | ZATCA, *Electronic Invoice XML Implementation Standard* v1.2 (2023-05-19) | https://zatca.gov.sa/ar/E-Invoicing/SystemsDevelopers/Documents/20230519_ZATCA_Electronic_Invoice_XML_Implementation_Standard_%20vF.pdf | VAT category codes S/Z/E/O and their Arabic names (§11.2); half-up rounding, rounding of final results only, category VAT rounded at document level (§10); BR-CO-17; seller VAT number of 15 digits with first and last digit 3 (BR-KSA-40); credit and debit notes must carry the billing reference (BR-KSA-56) |
| S6 | IFRS Foundation, *Educational Module 13: Inventories*, IFRS for SMEs, third edition (full text of Section 13) | https://www.ifrs.org/content/dam/ifrs/supporting-implementation/smes/2026-modules/module-13.pdf | 13.6: cost of purchase excludes taxes the entity recovers, and trade discounts are deducted. 13.18: FIFO or weighted average, LIFO not permitted. Example 44: perpetual (moving) average, used as a test vector |
| S7 | IFRS Foundation, jurisdiction profile: Saudi Arabia (updated 28 July 2022) | https://www.ifrs.org/use-around-the-world/use-of-ifrs-standards-by-jurisdiction/view-jurisdiction/saudi-arabia/ | All SMEs in Saudi Arabia are required to use the IFRS for SMEs Accounting Standard as endorsed there, so S6 applies to the businesses this portal serves |
| S8 | IFRS Foundation, IAS 2 *Inventories* summary | https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/ | FIFO or weighted average for interchangeable items (consistent with S6) |
| S9 | Anthropic privacy centre, "How long do you store my organization's data?" (updated 1 July 2026) | https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data | API inputs and outputs deleted within 30 days. Flagged content kept up to 2 years. Kept as the law requires. Used in the consent text |
| S10 | Anthropic docs, *API and data retention* | https://platform.claude.com/docs/en/manage-claude/api-and-data-retention | claude-opus-5-5 is not a "Covered Model" with mandatory 30-day retention. Flagged content up to 2 years |
| S11 | 21st.dev, Approval Card (Pasta UI) | https://21st.dev/@syeddhasnainn/components/approval-card | "A human-in-the-loop decision surface for questions, review steps, and consequential actions": the pattern for flag cards |
| S12 | 21st.dev, Combobox (Layro System) | https://21st.dev/@uvain/components/combobox-multi-create.md | A searchable select on cmdk with create-as-you-type: the pattern for the item and supplier pickers |

The 21st.dev Stepper (`@originui/components/stepper`) and the Number components were fetched earlier on this track's work branch. They are in `redesign/work_ref/` and were not refetched; §3 uses them only as patterns.

**Not used as a source.** Third-party summaries of the VAT rate (ClearTax, PwC, FedEx) came up in search but were not relied on; S3 states the rate. No Saudi rule is cited here except from S3, S4 and S5.

### 1.2 What the role needs, and what this module does about it

The O*NET tasks already shown in the storekeeper portal (S1) are about shipments. In a small Saudi business the same person usually also records what was bought and keeps the stock count, which is the work S2 describes. The table maps each relevant task to this module. Tasks with no row stay on-site work and keep their `ON_SITE` or `EMPLOYER_SYSTEM` mode in `professions.py`.

| Task (source, importance) | In this module |
|---|---|
| "Examine shipment contents and compare with records, such as manifests, invoices, or orders, to verify accuracy." (S1, 81) | The purchase invoice is entered line by line against the delivered goods. Its computed totals are compared with the printed totals (rule flags `TOTAL_MISMATCH`, `VAT_MISMATCH`). |
| "Record shipment data, such as weight, charges, space availability, damages, or discrepancies, for reporting, accounting, or recordkeeping purposes." (S1, 74) | Posting writes the stock movements and the ledger entry. Damaged or excess goods are recorded as a return with a reason. |
| "Confer or correspond with establishment representatives to rectify problems, such as damages, shortages, or nonconformance to specifications." (S1, 74) | The return records why goods went back (`DAMAGED`, `NOT_AS_SPECIFIED`, `EXCESS`, …) and then the supplier's credit-note number when it arrives. The dashboard lists returns still waiting for one. |
| "Calculate costs of orders, and charge or forward invoices to appropriate accounts." (S2, 84) | Line, VAT and invoice totals are computed by the database. Every posted invoice is an entry in the purchases ledger. |
| "Compare suppliers' bills with bids and purchase orders to verify accuracy." (S2, 74) | The price of each line is compared with the item's history (rule flag `PRICE_FAR_FROM_HISTORY`). Purchase orders are out of scope (§1.6). |
| "Prepare, maintain, and review purchasing files, reports and price lists." (S2, 79) | Suppliers, items with their purchase price, the expenses view by period, and the CSV export. |
| "Determine if inventory quantities are sufficient for needs, ordering more materials when necessary." (S2, 81) | A reorder level per item, the «تحت حدّ الطلب» filter and the dashboard count. The app lists what to reorder; it places no orders. |
| "Monitor in-house inventory movement and complete inventory transfer forms for bookkeeping purposes." (S2, 76) | Issue and count vouchers, and the movements list on each item card. |

**Change to `professions.py`.** The storekeeper portal gains `tools=("INVENTORY",)`. The first task ("Examine shipment contents…") becomes `Mode.IN_APP` with the note «في التطبيق: فاتورة الشراء تُدخَل سطراً سطراً ويُقارن إجماليها بالمطبوع.». The fifth ("Record shipment data…") becomes `IN_APP` with «في التطبيق: التسجيل يكتب حركات المخزون وقيد المصروف، والتالف يُسجَّل مرتجعاً بسببه.». Both notes are under `NOTE_MAX` (100 characters). `test_professions.py` checks this. Adding S2 as a second source is not needed: the screen cites S1, and S2 shapes the design only.

### 1.3 Saudi VAT facts this module relies on

All are from S3–S5 and quoted or closely paraphrased there.

1. **Standard rate 15%.** "they must apply tax at a rate of 15% (assuming the standard rate applies to those supplies)… The VAT they pay to their suppliers is referred to as input tax." (S3 §1.3)
2. **Categories.** S standard rate, Z zero rated, E exempt, O not subject to VAT; "for all VAT categories except 'Not subject to VAT' (O), the VAT rate shall be provided". (S5 §8.2, §11.2)
3. **Calculation.** "VAT category tax amount (BT-117) = VAT category taxable amount (BT-116) x (VAT category rate (BT-119) / 100), rounded to two decimals" (BR-CO-17). "Rounding shall be performed by using 'half-up' rounding"; "Rounding shall be done on the final calculation results not on any intermediate results"; "VAT category tax amount (BT-110) shall be rounded on document level and not as a summation of rounded Invoice line VAT amounts." (S5 §10)
4. **Halalas.** The VAT amount is shown in riyals and halalas, "rounded to the nearest Halala". (S3 §4.2.4) The guideline's example 6 computes VAT on a VAT-inclusive SAR 1,255.00 as 15/115, which is SAR 163.70. This is a test vector in §10.1.
5. **Simplified invoices.** These are for supplies under SAR 1,000 or to individuals. They may show "the total consideration due… with a clear indication that this amount includes VAT at the basic rate". (S3 §4.3.2) So the purchaser must be able to enter VAT-inclusive prices.
6. **Supplier VAT number.** A tax invoice carries the "Supplier VAT registration number" (S3 §4.2.3). Its shape is "15 digits. The first and the last digits are '3'" (S5 BR-KSA-40).
7. **Invoice numbers** "may be specified using numerals only, or by using a combination of numerals and letters (Roman or Arabic), provided that the number is sequential and uniquely identifies the invoice." (S3 §4.2.1)
8. **Credit and debit notes are the supplier's.** "A credit note is a commercial document issued by the supplier/seller to the purchaser… when goods are damaged or do not meet the specifications… and are returned in full or in part to the supplier." It must state its type "and the serial number of the tax invoice that the notice amends". When the customer has deducted input tax, "the customer shall correct the input tax… in the tax period in which the credit or debit note was issued". Notes "must be issued no later than 15 days of the month following" the event. (S3 §7, §7.1.1, §7.2; S5 BR-KSA-56)
9. **Input tax** "may only be deducted if the taxable person holds a tax invoice". (S3 §9.1)
10. **Records.**
    - Records are kept for "no less than six (6) years from the end of the related tax period". (S3 §8.3.3)
    - They are kept "within the Kingdom in electronic form… the computer or server must be located within the Kingdom". (S3 §8.3.1)
    - They are kept in Arabic. (S3 §8.3.2)
    - The person must keep "adequate controls… to prevent tampering". (S3 §8.3.1)

**Not claimed here:** any rule on purchase returns beyond S3 §7, any Saudi advertising or consumer rule, and anything about Zakat. Decision 1 in §11 turns on point 10.

### 1.4 A purchaser records invoices but does not issue them: what that means for the fields

Under the E-invoicing Regulation (S4 Art. 3), e-invoices and e-notes are issued by the taxable supplier, or by a customer issuing on the supplier's behalf. A storekeeper recording a supplier's invoice issues nothing. So this module:

- **Generates no e-invoice artefact.** No UBL XML, no QR code, no invoice UUID, no invoice counter value or previous-invoice hash, no cryptographic stamp, and no connection to ZATCA's systems.
- **Never titles anything as a tax document.** Nothing it shows or exports is titled «فاتورة ضريبية», «إشعار دائن» or «إشعار مدين». S3 §2 notes that a non-registered person's document "intended to show the amount of tax" is treated as a tax invoice. The return is called «مرتجع مشتريات»; it is an internal record, not a note to the supplier.
- **Does not support self-billing.** Issuing on the supplier's behalf (S3 §5.1) is out of scope.

The fields kept are the ones needed to rely on the supplier's document and to match it later:

| Kept | Why |
|---|---|
| Supplier name; supplier VAT number (optional, checked against BR-KSA-40) | Identifies the issuer (S3 §4.2.3). Without a number, VAT on the invoice may not be deductible (§1.3 point 9), so the rule flag `VAT_WITHOUT_SUPPLIER_VAT_NUMBER` fires. |
| Supplier invoice number as printed, plus a normalised key | Unique per issuer (S3 §4.2.1). The key detects a duplicate entry. |
| Invoice date (issue date) | The expense and the stock movement are dated by it. Rule flag `OLD_INVOICE_DATE`. |
| Prices exclusive or inclusive of VAT | Simplified invoices state VAT-inclusive totals (§1.3 point 5). |
| Per line: item, quantity, unit price, discount, VAT category (S/Z/E/O) | The supply details of S3 §4.2.3 ("Description… Unit price… Quantity… Discount… Applied VAT rate"). |
| Printed total and printed VAT | To compare the user's entry with the paper. Computed values are what is posted. |
| On a return: the supplier's credit-note number and date, set once | The supplier's document that adjusts input tax (§1.3 point 8). Returns waiting for one are listed. |
| Snapshot at posting: supplier name and VAT number; item name and unit per line | A posted record does not change when master data is renamed (S3 §8.3.1, anti-tampering). |

Not kept: the supplier's address, the buyer's own details, the invoice's QR payload, and any supplier ID other than the VAT number. They identify nothing the module needs, and each extra field is more data to hold.

### 1.5 Accounting basis

- **The purchases journal is the expense.**
  - The owner asked that a purchase invoice "posts to expenses". Each posted invoice writes one `PURCHASE` entry: net, VAT and gross. Each return or reversal writes a negative entry.
  - The expenses view sums these by period. Net and VAT are shown apart because input VAT is a credit for a registered business (S3 §9.1).
- **Stock is valued separately**, at the perpetual moving-average cost (S6 13.18, example 44).
  - Inflows (purchase, opening, count surplus) add their cost and quantity.
  - Outflows (return, reversal, issue, count shortage) leave at the current average. Their value is `round(value × q / on_hand)`, or the whole value when the last unit leaves, so no value is left behind with zero quantity.
  - No unit cost is rounded mid-way. Example 44 gives 11,571.43 rather than the module's illustrative 11,574 computed from a rounded 12.86.
- **What a unit costs** (S6 13.6).
  - Cost is the line's net amount after discount. If the business cannot recover the VAT, the line VAT is added.
  - This is the one setting asked on first use: «هل تستردّ منشأتك ضريبة المشتريات؟». It locks after the first movement, because changing it would change the meaning of every past average.
- **Returns and reversals.** They reduce stock at the average and the ledger at the original line's amounts. A return takes its share of the original line's net and VAT, and the last return of a line takes exactly what remains, so returns never exceed the invoice by a halala.

### 1.6 Out of scope (stated so nobody builds against it)

- Purchase orders and approvals.
- Payments, supplier balances and accounts payable.
- Sales and selling prices.
- Unit conversion (carton to pieces). An item has one unit; buying in cartons and issuing in pieces needs two items.
- Landed-cost allocation. Shipping on an invoice is a SERVICE line: an expense with no stock.
- Invoice-level allowances and charges. Discounts are per line; an invoice-level discount shows as a `TOTAL_MISMATCH` flag until it is spread over lines.
- Foreign-currency invoices. Amounts are entered in SAR; S3 §4.2.2 requires the tax amount in SAR.
- Scanning QR codes (`Permissions-Policy: camera=()` stays).
- Multi-warehouse stock.

---

## 2. The working day and every decision in it

### 2.1 Where the employee starts

After sign-in, the unified portal opens the storekeeper's home, `#/inventory`. On the first visit only, one setup question comes first (screen S1).

Every visit after that shows the same three blocks:

1. **«فاتورة شراء جديدة»**, the primary action, in the same place every day.
2. **«يحتاج انتباهك»** ("needs your attention"), with up to three counts, each opening its list:
   - drafts not yet posted;
   - items at or below their reorder level;
   - returns waiting for the supplier's credit note, with those past the 15th of the following month marked «متأخر».
3. **«هذا الشهر»** ("this month"): purchases before VAT, purchase VAT, returns, net, and current stock value.

### 2.2 The flows

The diagrams use `>` for a press and `?` for a decision the employee makes. Every ? is the employee's; the system only computes, checks and flags.

**A. A delivery arrives with an invoice**

```
Home > «فاتورة شراء جديدة»
  ? Supplier: pick from the list, or > «مورّد جديد» (name, VAT number if printed)
  ? Supplier invoice number (as printed)                 [draft is saved after every step]
  ? Invoice date: «اليوم» / «أمس» / «تاريخٌ آخر»
  ? Prices on the invoice: «قبل الضريبة» / «شاملة الضريبة»
  Lines (repeat):
    ? Item: pick from the list, or > «صنف جديد باسم "…"» (unit, purchase price, VAT category)
    ? Quantity
    ? Unit price (prefilled from the item; keep or change)
    ? VAT category (prefilled from the item; keep or change)
    ? Discount (default none)
  ? Printed total (and printed VAT if shown)
  > «راجِع وسجّل»
     system: rule flags at once; «مراجعة سيمبول» if enabled (a few seconds)
  ? No flags  → «سجّل الفاتورة»                      → posted «فاتورة الشراء ش-0007»
  ? Flags     → «عدّل» (opens the flagged step)  or  «سجّل رغم التنبيهات»
  After posting: > «فاتورة جديدة» / «الرئيسية»
```

**B. Goods go back to the supplier**

```
Home or posted invoice > «مرتجع من فاتورة»
  ? Which invoice (search: supplier, our number ش-…, supplier's number)
  ? Which lines and how much of each (≤ what remains; the screen shows it)
  ? Reason: «تالفة» / «صنفٌ غير المطلوب» / «مخالفة للمواصفات» / «زائدة عن الطلب» / «منتهية الصلاحية» / «سببٌ آخر» (+ note)
  ? Date (default today)
  > «راجِع وسجّل» → flags as in A → ? «سجّل المرتجع»
  Later, when the supplier's credit note arrives: ? its number and date (once)
```

**C. An invoice was recorded by mistake**

```
Posted invoice > «قيد عكسي»
  system: refuses if the invoice has returns, and says to use a return for what remains
  ? Reason: «سُجّلت مرتين» / «المورّد خطأ» / «بياناتها خطأ» / «سببٌ آخر» (+ note)
  Confirmation screen states the effect: stock out, negative entry dated today
  ? «سجّل القيد العكسي»
  Optional > «انسخها مسودةً جديدة» to re-enter it correctly
```

**D. Stock leaves without a purchase document (sale, internal use, damage)**

```
Item card or tools button > «صرف»
  ? Item  ? Quantity (≤ on hand)  ? Reason: «بيع» / «استعمالٌ داخلي» / «تلف» / «سببٌ آخر»  ? Date (≤ 30 days back)
  > «سجّل الصرف»  (no draft; one press; replaying the same press records nothing twice)
```

**E. Counting the shelf**

```
Item card > «جرد»
  screen shows on-hand as recorded
  ? Counted quantity → screen shows the difference and its value at the average
  ? «سجّل الجرد»  (refused if on-hand changed since the screen opened: count again)
  First use of an item that already has stock: > «رصيد افتتاحي» (quantity + unit cost; only before any movement)
```

**F. End of day**

```
Home: totals for the month update; «يحتاج انتباهك» shows what is left.
«المصروفات» ? month or range → totals and entries; > «تنزيل CSV» for the accountant.
```

### 2.3 Who decides what

| Decision | Made by | What the system does |
|---|---|---|
| Which supplier, item, quantity, price, VAT category | Employee | Prefills price and category from the item; checks shapes; computes amounts |
| Create an item or supplier | Employee | Refuses a name that, once normalised, is already active; the AI may flag a likely duplicate |
| Post despite flags | Employee | Refuses to post unless every current flag is acknowledged; stores the acknowledgment |
| Return quantity and reason | Employee | Refuses more than remains, or more than on hand; requires a reason, and a note for «سببٌ آخر» |
| Reverse an invoice | Employee | Refuses after returns, or when stock no longer covers it; requires a reason |
| Count result | Employee | Refuses a count taken against a stale on-hand |
| Cost basis (VAT in cost or not) | Employee, once | Locks it after the first movement |
| Enable «مراجعة سيمبول» | Employee | Off until the notice is read; can be turned off any time |

---

## 3. Screens

### 3.0 Shared rules

**Size modes.** These use the tokens of the v2 client (`redesign/v2/client/tailwind.config.js` and `src/styles/globals.css`).

| | Compact (default) | Gaze |
|---|---|---|
| Hit region | `h-ctl` 44 px (`ctl-lg` 48 for primary) | 72 px |
| Gap between targets | `gap-tg` 12 px (rows: `tg-min` 8 px) | 24 px |
| Table row | `row` 52 px, target 44 inside | 72 px, the row is the target |
| Body text | 16 px | 18 px |
| Scrolling | The page may scroll; lists still page (20 per page) | No scrolling inside a step. Lists page: 4 rows per page at 375×635, 5 at ≥ 390×664 |
| Forms | One screen per document, in sections | One decision per step; the draft is saved after every step |
| Commit buttons | Bottom-end of the section | Bottom-end slot of the bottom bar, never the nearest control after the press that opened the step |

**Gaze contract** (the same rules as registration §8.3, applied here):

- Bars and commits.
  - A top bar holds «رجوع» at the start slot, the title, and «حسابي» at the end slot.
  - A bottom bar holds the secondary action at the start and the primary at the end.
  - A step that commits (post, reverse, count, issue) has nothing that commits nearest to, or under, the spot of the press that opened it.
- No hover, no timers, and activation by click alone.
- Motion is off in gaze mode; elsewhere `prefers-reduced-motion` is respected.
- Paging. A list that pages shows «السابق» and «التالي» in the bottom bar and «الصفحة 2 من 5» as text. Dashboard and list tests audit size, gap, edge, at most 10 targets, no scroll and nothing clipped. The same audits from `tests/ui` run at 320, 375 and 390 px widths and at Text Size 17, 23 and 53.

**Components** (21st.dev patterns ported into `eyework/client`, never loaded from a CDN, since the CSP is self only):

| Component | Pattern | Used for |
|---|---|---|
| `Combobox` | 21st.dev Combobox (S12): cmdk + Radix Popover, create-as-you-type | Item and supplier pickers in compact mode. In gaze mode the same data renders as a full step: a search field plus 4 paged results plus «… جديد باسم "…"» as the last row, with no popover. |
| `Stepper` | 21st.dev Stepper (`@originui`) | Progress through the invoice and return steps (text «الخطوة 3 من 7» in gaze; compact shows it as a header). |
| `FlagCard` | 21st.dev Approval Card (S11) | One card per flag: a badge («تنبيه» for rules in the `warning` token, «مراجعة سيمبول» for AI in the `ai` token), the text, and a link «اذهب إلى السطر 3». The approve/deny decision is made once for all flags, at the bottom of the review step, not per card. |
| `Amount` | 21st.dev Number | Totals. Western digits grouped, two decimals, then « ر.س» (as `money.budget_short`). No count-up animation in gaze mode. |
| `Button`, `DropdownNavigation` | already ported (`a519ddb`) | Actions; the portal menu |
| `DataPager` | new, shadcn primitives | Paged lists and tables in both modes |
| `NumberField` | new | `inputmode="decimal"` (or `numeric` for counted units). Arabic-Indic digits are accepted and normalised to Western digits before sending. Money is parsed to halalas without floats (`parseRiyals`). Gaze mode adds «−1» and «+1» stepper buttons for quantities. |

**No emoji anywhere.** Icons are lucide-react (`AlertTriangle` for rule flags, `Sparkles` for the AI badge, `PackagePlus`, `Undo2`, `Boxes`, `Receipt`).

**Digits.** Western digits everywhere, as the existing UI does («الخطوة 1 من 5», `toLocaleString('en-US')`); Arabic-Indic digits typed into a field are accepted and normalised.

**Labels used everywhere:**

- **Units:** PIECE «قطعة», BOX «علبة», CARTON «كرتون», PACK «عبوة», PALLET «منصّة», KG «كغ», LITRE «لتر», METRE «م», SERVICE «خدمة».
- **VAT categories** (S5 Arabic names, shortened): S «خاضع 15%», Z «نسبة الصفر», E «معفى», O «غير خاضع».
- **Document numbers** (display only; the integer is stored): «ش-0007» purchase, «ر-0003» return, «ع-0001» reversal, «س-0012» stock voucher.
- **Status badges:** «مسودة», «مسجّلة», «معكوسة».

### 3.1 S1: First-use setup (`#/inventory/setup`)

Shown when `GET /api/inventory/settings` returns 404 `INV_SETUP`.

- **Title:** «قبل أول فاتورة»
- **Question:** «هل تستردّ منشأتك ضريبة المشتريات؟»
- **Two options**, each a full-width target:
  - «نعم، المنشأة مسجّلة في الضريبة وتستردّها» → `cost_includes_vat=false`
  - «لا، الضريبة جزءٌ من التكلفة» → `true`
- **Help:** «يحدّد هذا تكلفة الصنف في المخزون: قبل الضريبة إن كانت تُستردّ، وشاملةً لها إن لم تُستردّ. لا يتغيّر بعد أول تسجيل.»
- **Second help line:** «هذا السجلّ لعملك في التطبيق، ولا يُغني عن حفظ فواتير المورّدين الأصلية في سجلات المنشأة.» (§11 decision 1)
- **Second step (both modes): the review notice (§9.3)**, with «فعّل مراجعة سيمبول» (bottom-end) and «ليس الآن» (bottom-start). The commit is never nearest to the option pressed on the previous step; measured as in registration §8.4.

Compact puts both on one screen. Gaze uses two steps.

### 3.2 S2: Home (`#/inventory`)

**Compact**, one page:

- Header: «المخزون».
- Primary `Button` «فاتورة شراء جديدة».
- Card «يحتاج انتباهك»: up to three `ListRow`s in the form «noun: count», so no number agreement is needed: «مسوداتٌ لم تُسجَّل: 2», «أصنافٌ بلغت حدّ الطلب: 3», «مرتجعاتٌ تنتظر إشعار المورّد الدائن: 1 (متأخر: 1)». Rows with a zero count are hidden. With nothing to show, the card reads «لا شيء ينتظرك.».
- Card «هذا الشهر» (current Riyadh month): `Amount` rows «المشتريات قبل الضريبة», «ضريبة المشتريات», «المرتجعات», «الصافي», and «قيمة المخزون» as a separate line.
- Section links: «الأصناف والأرصدة», «المصروفات», «المرتجعات», «الموردون», «سند مخزون», «إعدادات المخزون».

**Gaze, page 1:** «فاتورة شراء جديدة», «يحتاج انتباهك: 3» (one target opening the list), the «هذا الشهر» totals as text (three lines: «الصافي», «الضريبة», «قيمة المخزون»), and «المزيد».

**Gaze, page 2 («المزيد»):** the six section links, 4 per page.

### 3.3 S3: Purchase invoice draft (`#/inventory/purchases/:id`)

**Compact**, one screen:

1. Card «فاتورة المورّد»:
   - `Combobox` «المورّد» (create row: «مورّد جديد باسم "…"»)
   - field «رقم فاتورة المورّد»
   - date field «تاريخ الفاتورة» (default today in Riyadh, from `/summary`)
   - `Switch` «الأسعار شاملة الضريبة»
2. Table «الأسطر», columns «الصنف · الكمية · سعر الوحدة · الخصم · الضريبة · المبلغ».
   - The last row is the add row: `Combobox` item (create row «صنف جديد باسم "…"»), quantity, unit price (prefilled), category (prefilled), «أضف».
   - Each row's own menu has «تعديل» and «احذف السطر».
   - «الخصم» is hidden until «أضف خصماً» is used.
3. Card «المجاميع»: «المجموع قبل الضريبة», «الضريبة», «الإجمالي». These are computed by the server (`ew_inv_purchase_calc`) and refreshed after every change.
4. Card «كما في الفاتورة المطبوعة»: «الإجمالي المطبوع» (required to post), «الضريبة المطبوعة» (optional). A live line under them: «يطابق المحسوب» or «الفرق: 0.01 ر.س».
5. Bottom: «احذف المسودة» (start, opens a confirmation) and «راجِع وسجّل» (end).

**Gaze**, steps (the `Stepper` text shows the position):

1. «المورّد»: search field, 4 paged results, last row «مورّد جديد باسم "…"».
2. «رقم فاتورة المورّد»: field and «التالي».
3. «تاريخ الفاتورة»: «اليوم», «أمس», «تاريخٌ آخر». The last opens year, month and day pickers, reusing the sign-up birth-date steps.
4. «الأسعار في الفاتورة»: «قبل الضريبة» or «شاملة الضريبة».
5. «الأسطر»:
   - 4 lines per page, each row reading «كرتونة ماء 330 مل — 10 كرتون × 45.50 = 455.00».
   - «أضف سطراً» opens S3a. A row opens S3a for that line, with «احذف السطر».
   - The bottom bar holds «السابق» and «التالي»; «انتهت الأسطر» moves on.
6. «الإجمالي المطبوع»: field (and «الضريبة المطبوعة», optional) with the computed values shown as text.
7. «راجِع وسجّل» → S5.

### 3.4 S3a: Line editor (gaze steps; compact edits inline)

1. «الصنف»: search field, results paged by 4. The last row is «صنف جديد باسم "…"» → S4. Each result shows its unit and its last purchase price.
2. «الكمية»: `NumberField` with «−1» and «+1», and the unit name after the field. Help: «بالعدد الصحيح للقطعة والكرتون ونحوهما، وبثلاث خاناتٍ عشرية للوزن والحجم والطول.»
3. «سعر الوحدة»: prefilled (the item's price, or price × 1.15 for an inclusive invoice; the server provides it). «كما هو» or «تعديل».
4. «فئة الضريبة»: four options, with the item's own category first and marked «المعتادة».
5. «الخصم»: «بلا خصم» (default, bottom-end) or «خصم بمبلغ…».
6. «احفظ السطر».

### 3.5 S4: New item (opened from the item picker)

- «اسم الصنف» (prefilled with the typed text)
- «النوع»: «صنفٌ يُخزَّن» / «خدمة (شحن، تركيب…)»
- «الوحدة»: 8 options. Gaze shows them on 2 pages of 4; compact uses a select. Hidden for a service.
- «سعر الشراء للوحدة قبل الضريبة» (required)
- «فئة الضريبة» (default S)
- In compact, an expandable «تفاصيل أخرى» holds «رمز الصنف» (optional) and «حدّ الطلب» (optional). Gaze offers it as an optional last step.
- «أنشئ الصنف» returns to the line with the item chosen and the price filled.

On 409 `INV_ITEM_EXISTS`, the screen offers «اختر الصنف الموجود».

### 3.6 S5: Review and decide (`#/inventory/purchases/:id/review`, and the return equivalent)

- **Header:** «مراجعة الفاتورة قبل تسجيلها» with the totals summary.
- **Flags.** `FlagCard`s, strongest first (`DUPLICATE_SUPPLIER_INVOICE`, then mismatches, then line flags, then AI flags). Compact lists them all; gaze shows 2 per page.
- **The AI part:**
  - While it runs, a status line reads «سيمبول يراجع الأسطر…». Only the commit is disabled; «عدّل» stays live.
  - On failure it reads «لم تكتمل مراجعة سيمبول هذه المرة. التنبيهات أعلاه من قواعد التطبيق، والتسجيل متاح.»
  - When off: «مراجعة سيمبول متوقّفة.»
  - Over a limit: the server's message.
- **No flags:** «لا تنبيهات.» with «سجّل الفاتورة» (bottom-end) and «عدّل» (bottom-start).
- **With flags:** «عدّل» (bottom-start), which goes to the first flagged step, and «سجّل رغم التنبيهات» (bottom-end).
  - In gaze mode the commit appears only on the last page of flags, so every flag has been on screen before it can be pressed.
  - The request sends the keys of the flags shown. If they changed meanwhile (409 `FLAGS_CHANGED`), the page reloads the flags with «تغيّرت التنبيهات منذ عرضها. راجعها ثم سجّل.».
- **After posting:** «سُجّلت فاتورة الشراء ش-0007.» with «فاتورة جديدة» and «الرئيسية». Gaze places them away from the spot of the commit.

### 3.7 S6: Posted invoice (`#/inventory/purchases/:id`, read-only)

- Header «فاتورة الشراء ش-0007» with the badge «مسجّلة» or «معكوسة».
- Supplier snapshot, the supplier's number and date, lines (paged 4 in gaze), totals, and printed totals.
- Section «التنبيهات التي أُقرّ بها» (if any): the acknowledged flags as stored, with their time.
- «المرتجعات منها»: the list with links.
- **Actions:**
  - «مرتجع من هذه الفاتورة» (hidden when nothing remains returnable or the invoice is reversed)
  - «قيد عكسي» (hidden after returns or reversal)
  - «انسخها مسودةً جديدة»
- A reversed invoice also shows «عُكست بالقيد ع-0001 في … — السبب: سُجّلت مرتين».

### 3.8 S7–S10: Return

- **S7 «من أيّ فاتورة؟»:** search (supplier, «ش-»number, the supplier's number), then posted, non-reversed invoices with something left to return, paged.
- **S8 «ما الذي يُرجَع؟»:**
  - The invoice's lines, each with «بقي للإرجاع: 3 كرتون».
  - A row opens «الكمية المرجَعة» (`NumberField`, max shown, «−1» / «+1», «كلّ الباقي»).
  - Lines with nothing returned are not part of the return.
- **S9 «سبب الإرجاع»:** six options. «سببٌ آخر» adds the step «اكتب السبب». Then «تاريخ الإرجاع»: «اليوم» / «تاريخٌ آخر». Then review (S5) and «سجّل المرتجع».
- **S10, on a posted return:** «رقم إشعار المورّد الدائن» and «تاريخه», then «احفظ». Help: «الإشعار الدائن يصدره المورّد ويذكر رقم فاتورته الأصلية، ويعدّل ضريبة مشترياتك في الفترة التي صدر فيها.» (S3 §7). Once saved it shows as text and cannot be changed.

### 3.9 S11: Reversal

- **Step 1, «سبب القيد العكسي»:** four options, plus a note for «سببٌ آخر».
- **Step 2, «ما الذي سيحدث»:** text listing the effect:
  - «يخرج من المخزون: …» per stock line;
  - «قيدٌ سالب في المصروفات بتاريخ اليوم: −1,161.50 ر.س»;
  - «تبقى الفاتورة ش-0007 ظاهرةً، معلَّمةً «معكوسة».».
- Buttons: «رجوع» and «سجّل القيد العكسي» (bottom-end, never nearest to the reason just pressed).

### 3.10 S12: Stock on hand (`#/inventory/stock`)

- **Filters** (tabs): «الكل», «تحت حدّ الطلب», «الخدمات», «المؤرشفة». A search field.
- **Compact table:** «الصنف · الرصيد · متوسط التكلفة · القيمة · حدّ الطلب», 20 rows per page. The «تحت الحدّ» badge uses the `destructive-tint` token with text, not colour alone. Footer: «قيمة المخزون: …».
- **Gaze:** 4 rows per page. Each row is one 72 px target reading «أرز بسمتي — 12.5 كغ — 112.50 ر.س», with the badge as text («تحت الحدّ»).
- A row opens S13.

### 3.11 S13: Item card (`#/inventory/items/:id`)

- **Facts:** name, unit, kind, VAT category, code, «سعر الشراء المحدَّد», «حدّ الطلب», «الرصيد», «متوسط التكلفة», «القيمة».
- «آخر المشتريات»: the last 5 posted lines, each with date, supplier and «10 كرتون × 45.50».
- «الحركات»: paged list of type, date, quantity and the balance after.
- **Actions:** «صرف», «جرد», «تعديل», «أرشفة».
  - «أرشفة» is hidden while stock is held; the server would answer `INV_ITEM_HAS_STOCK` anyway.
  - «رصيد افتتاحي» appears only before any movement.

### 3.12 S14: Stock voucher (issue, count, opening)

- **«صرف من المخزون»:** item, quantity (max shown), reason (4 options), note for «سببٌ آخر», date. Ends with «سجّل الصرف».
- **«جرد»:**
  - Shows «الرصيد المسجَّل: 12 كرتون».
  - The «المعدود فعلاً» field.
  - A live line «الفرق: −2 كرتون (−91.00 ر.س بمتوسط التكلفة)».
  - Ends with «سجّل الجرد».
  - When there is no stock and the count is above zero, it asks for «تكلفة الوحدة».
- **«رصيد افتتاحي»:** quantity, «تكلفة الوحدة», date. Ends with «سجّل الرصيد الافتتاحي».

Each voucher screen creates its `client_token` when it opens, so a double press records once.

### 3.13 S15: Expenses (`#/inventory/expenses`)

- **Period.** Compact: month picker with «الشهر السابق» and «الشهر التالي», plus «فترة مخصّصة» (from/to, at most 366 days). Gaze: «الشهر السابق» and «الشهر التالي», with the month name as text.
- **Totals card:**
  - «المشتريات» (net, VAT, gross)
  - «المرتجعات»
  - «القيود العكسية»
  - «الصافي قبل الضريبة»
  - «صافي الضريبة» (with the help line «ضريبة المدخلات بعد المرتجعات؛ خصمها يحتاج الفاتورة الضريبية.»)
  - «الصافي شاملاً الضريبة»
- **Entries**, paged (20 / 4): date, a type badge («شراء» / «مرتجع» / «عكسي»), the document number, supplier, net, VAT, gross.
- «تنزيل CSV» (compact; in gaze it is in the tools button).

### 3.14 S16: Suppliers (`#/inventory/suppliers`)

- List: search, paged, showing name and the VAT number in `bdi dir=ltr`.
- «مورّد جديد».
- Supplier form: «اسم المورّد», «الرقم الضريبي (إن وُجد)» with the help «خمس عشرة خانة، أولها وآخرها 3، كما في فاتورته.», and «أرشفة» / «إعادة تفعيل».

### 3.15 S17: Inventory settings (`#/inventory/settings`)

- «ضريبة المشتريات والتكلفة»: the answer from S1. After the first movement it is shown as text with «لا يتغيّر بعد أول تسجيل.».
- «مراجعة سيمبول»: a switch. Turning it on shows the notice (§9.3) with «فعّل» / «ليس الآن». Also shown: «بقي اليوم: 27 من 30».
- «قراءة الإشعار»: shows the accepted notice again, with its version date.

---

## 4. Database

### 4.1 Design notes

**Tables** (all keyed to `user_id`, RLS enabled and forced, owner policy plus a web-role policy on `user_id = ew_current_user()`):

| Table | Holds | Web role |
|---|---|---|
| `inv_settings` | Cost basis; review switch and notice version | SELECT; INSERT (`user_id`, `cost_includes_vat`); UPDATE (`cost_includes_vat`, `review_enabled`, `review_notice_version`) |
| `inv_counters` | Last number per kind (`PURCHASE`, `RETURN`, `REVERSAL`, `VOUCHER`) | nothing (owner policy only) |
| `inv_suppliers` | Name, normalised key, VAT number, active | SELECT; INSERT (`user_id`, `name`, `vat_number`); UPDATE (`name`, `vat_number`, `is_active`) |
| `inv_items` | Name and key, code, kind, unit, VAT category, price, reorder level; on hand and value (written by movements only) | SELECT; INSERT and UPDATE on the descriptive columns only |
| `inv_purchases` | Header; posted snapshot and totals; reversal | SELECT; INSERT/UPDATE of the header fields only (status, number and totals are function-only) |
| `inv_purchase_lines` | Item, quantity, price, discount, category; posted figures | SELECT; INSERT/UPDATE of the five entry columns |
| `inv_returns`, `inv_return_lines` | Return header (date, reason, note, totals, credit note); per original line quantity and posted figures | SELECT; header fields; line quantity |
| `inv_vouchers` | Opening, issue, count | SELECT only (written by `ew_inv_stock_voucher`) |
| `inv_movements` | The stock ledger: kind, quantity, value, balance after, source | SELECT only |
| `inv_ledger` | Purchases journal: `PURCHASE` (+), `RETURN` (−), `REVERSAL` (−) | SELECT only |
| `inv_review_calls` | One row per model call: digest, outcome, tokens, model, `new_account` | SELECT only |
| `inv_review_flags` | Rule flags (stored at posting, acknowledged) and AI flags (stored when they arrive) | SELECT only |

No web-role DELETE or TRUNCATE on any table. Lines are removed and drafts discarded through `ew_inv_remove_purchase_line`, `ew_inv_remove_return_line` and `ew_inv_discard_draft`.

**Immutability.**

- A posted invoice or return refuses every UPDATE (`inv_document_is_final`), with two exceptions:
  - the reversal function's single transition to `REVERSED`;
  - setting a return's credit-note number and date once.
- Lines of posted documents refuse UPDATE (`inv_document_not_draft`).
- Movements, ledger entries and vouchers refuse UPDATE (`ew_forbid_update` from 0002).
- Posted documents, their lines, movements, ledger entries, vouchers, items and suppliers refuse DELETE at trigger depth 1, which means any direct DELETE, the owner's included (`inv_record_is_permanent`).
  - A delete cascading from `users` arrives at depth ≥ 2 and is allowed, so `ew_delete_me` and `admin delete-user` still remove everything.
  - In-account references cascade so the whole account goes in one statement. Items and suppliers can never be deleted directly, so a cascade can only start from the account. This guarantee is tested.

**Gapless numbering.**

- `ew_inv_next_no` does `INSERT … ON CONFLICT DO UPDATE SET last_no = last_no + 1`. It runs inside the posting transaction, after every check that can fail, so a refused posting rolls the counter back.
- Drafts have no number.
- Nothing posted can be deleted except with the whole account.
- A partial unique index on `(user_id, number)` makes a duplicate impossible as well.

**Concurrency.**

- **The row version.** Every posting function locks the document row (`FOR UPDATE`) and requires the row version the user saw. Every line insert, update or delete bumps the header's row version through the line trigger. So:
  - two tabs posting one draft: the second waits on the lock, then gets `inv_document_not_draft` (tested with a real lock wait);
  - a tab that reviewed an older version gets `inv_stale_row_version`.
- **Item locks.** Items are locked in id order (`ew_inv_lock_items`) before any movement, so two postings that share items cannot deadlock.
- **Returns.** A return locks its purchase row, so two returns cannot both take the same remainder, and a reversal cannot race a return.
- **Caps.** Per-account caps (20 open drafts of each kind, 2,000 suppliers, 5,000 items) run under a per-user advisory lock.

**Amounts.**

- Integer halalas everywhere; quantities are in thousandths of the unit (`*_milli`).
- Counted units must be whole (`quantity_milli % 1000 = 0`); KG, LITRE and METRE take up to three decimals.
- `ew_inv_purchase_calc` implements §1.3 point 3:
  - line amount = round(quantity × price) − discount;
  - category VAT = round(Σ amounts × 15/100), or × 15/115 when prices include VAT, half-up;
  - the category VAT is spread over its lines by largest remainder, so lines sum to the category exactly and none is negative. A test with 40 lines of 0.10 shows this.
- The posting writes these figures onto the lines; the header totals are their sums.

**Average cost.** As in §1.5. The movement trigger writes `on_hand_milli`, `stock_value_halalas`, and each movement's value and balance-after, under the item row lock.

**Flags.**

- `ew_inv_purchase_flags` and `ew_inv_return_flags` are SQL functions run with the caller's rights, so they see only the caller's rows.
- `ew_inv_flag_keys` returns the keys of every current flag: «CODE» or «CODE:line», plus «AI:CODE:line» for AI flags whose digest matches the current content.
- Posting calls `ew_inv_check_ack` and refuses unless every key is in the acknowledged list. It then:
  - stores the rule flags with `acknowledged_at`;
  - marks the AI flags acknowledged;
  - deletes AI flags about content that was never posted.
- The thresholds live in SQL only; Python does not duplicate them. They are:
  - price at least 1.5× (or at most 1/1.5×) the median of the last 10 posted unit nets, or the item's own price if it has none;
  - quantity at least 5× (or at most 1/5×) the median of the last 10, when there are at least 3;
  - an invoice date older than 90 days;
  - a return of a purchase older than 90 days.

**Review calls and caps.**

- `ew_inv_review_begin` opens a call, with every limit checked under the same locks as `ew_begin_generation`:
  - the user row lock;
  - then the global advisory lock `eyework.generation_global_cap`.
- The limits it checks:
  - one call in flight per user;
  - 6 per 10 minutes;
  - 30 billable per 24 hours, or 10 for a new open account (0007);
  - 600 a day for reviews app-wide;
  - the shared 2,000, counted over campaign attempts, tombstones and review calls;
  - the shared 400 for new open accounts.
- `ew_begin_generation` is replaced so that campaigns also count review calls.
- Deleting a review call within its day writes a tombstone. The down migration does the same for recent calls, so dropping the table frees no room either.
- `ew_inv_review_record` stores AI flags only when the document is still a draft with the same digest; otherwise it closes the call as `DISCARDED`. It accepts only the portal's own codes for the document type, and only lines that exist.

**Profession.** Every insert into a user-owned inventory table and every function call checks `users.profession = 'STOREKEEPER'` (`FOR SHARE`, as the campaign insert guard does), raising `inv_needs_storekeeper`. Moving an account to another profession leaves its records in place. They reappear if it moves back, and drafts are purged after 30 days idle.

**Employer linking later.** Every table is keyed to `user_id`, and all policies use `ew_current_user()`. Linking would add an `organisation_id` and a membership table, and change the policies to `organisation_id = ew_current_org()`. The functions already take the user from the session, so their signatures would not change.

**Grants added outside the new tables:**

- `GRANT EXECUTE ON FUNCTION ew_riyadh_today() TO eyework_app`. The rule flags run with the caller's rights and measure "old" by Riyadh's date. The function returns only today's date. The down migration revokes it.
- `test_roles_and_grants.APP_FUNCTIONS` gains it and the new functions (§10.1).

### 4.2 Verified on PostgreSQL 16.13

Scratch databases `invspec_cycle` and `invspec_check` were created from main's 0001–0006, the registration track's 0007 (`registration_check/migrations/`), and this migration as 0008. Both were dropped afterwards.

- **Cycle** (`inventory_tools/cycle.py`):
  - NEXT up, down, up: the `pg_dump --schema-only` after down equals the dump before up (0007's schema); the second up equals the first.
  - A full down from NEXT to empty and up again equals the first up.
  - Results are in `inventory_sql/cycle_results.txt`.
- **Functional:** 96 checks pass as `eyework_app` (`inventory_tools/check_inventory.py`; output in `inventory_sql/check_results.txt`). They include:
  - every hard rule in §6;
  - every rule flag;
  - ZATCA example 6 (163.70);
  - the largest-remainder case;
  - IFRS example 44 at the halala (11,571.43 out, 6,428.57 left);
  - two tabs posting one draft, with a real lock wait;
  - two drafts posted at once, with consecutive numbers;
  - every review cap, including a campaign refused because reviews used up the 2,000;
  - account deletion removing everything;
  - the down migration refusing while posted records exist.
- **Generated, not retyped.** `ew_begin_generation` in both files comes from `inventory_tools/build_generation.py`: the down copy is 0007's text byte for byte, and the up copy adds exactly the two marked lines.

The SQL below is the exact content of `inventory_sql/NEXT_inventory.up.sql` and `.down.sql`, the files that passed those checks. Its comments are in Arabic, as in every existing migration.

