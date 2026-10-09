-- ════════════════════════════════════════════════════════════════════════
-- 0010_inventory — المخزون والمشتريات في بوابة أمين المخزون
-- ════════════════════════════════════════════════════════════════════════
-- ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم أو المساعد، فيُفرض هنا:
--
--   • المستند المسجَّل لا يتغيّر ولا يُحذف: فاتورة الشراء والمرتجع وسند المخزون
--     وحركاته وقيود دفتر المشتريات. التصحيح بمرتجعٍ أو بقيدٍ عكسي، ولكلٍّ منهما أثره.
--     ولا يُحذف شيءٌ منها إلا مع الحساب كلّه.
--   • الترقيم لكل حساب بلا فجوات: الرقم يُؤخذ في معاملة التسجيل نفسها، والمسودة
--     بلا رقم، فما تراجع لا يستهلك رقماً.
--   • ما يُسجَّل هو ما رآه صاحبه: التسجيل يشترط رقم الصفّ الذي رآه، وكل تعديلٍ في
--     الأسطر يزيده. فنافذتان تسجّلان المسودة نفسها: الأولى تنجح، والثانية تُرفض.
--   • لا رصيد تحت الصفر، ولا مرتجعٌ أكثر ممّا بقي من سطر فاتورته، ولا سببٌ ناقص.
--   • المبالغ بالهللة الصحيحة؛ والضريبة 15% للفئة S، تُقرَّب نصفاً إلى أعلى على
--     مستوى الفئة كما في معيار ZATCA للفاتورة الإلكترونية، وتُوزَّع على الأسطر بأكبر
--     الكسور فلا تضيع هللة. ومتوسط التكلفة متحرّك: الوارد يغيّره، والصادر بمتوسطه.
--   • تنبيهات القواعد لا تمنع؛ لكن لا تسجيل قبل أن يقرّ صاحب المستند بكل تنبيهٍ قائم
--     الآن، ويُحفظ إقراره مع المستند. وتنبيهات سيمبول في طبقة الذكاء (0009: ai_flags)
--     بقرار صاحبها، وبوّابتها ew_ai_gate عند التسجيل.
--   • مراجعة سيمبول استدعاءٌ في الدفتر الواحد (ai_requests، الميزة STOCK_REVIEW) بسقوفه
--     هناك؛ لا دفتر هنا ولا تفعيلٌ ولا إشعارٌ لها: إشعار التسجيل يغطّيها.
--   • العزل بالصفّ على eyework.user_id، مفروضٌ على المالك أيضاً (FORCE)، والمنح
--     بالأعمدة، ولا DELETE ولا TRUNCATE لدور الويب.
-- ════════════════════════════════════════════════════════════════════════

-- ── أدوات القيود ────────────────────────────────────────────────────────
-- نصٌّ يُعرض: مقصوص الطرفين، بلا محارف تحكّمٍ أو اتجاهٍ خفية، وبلا مسافتين متتاليتين.
CREATE FUNCTION ew_inv_text_ok(p text, p_max integer) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT p IS NOT NULL AND char_length(p) BETWEEN 1 AND p_max AND p = btrim(p)
       AND p !~ '[[:cntrl:] ​-‏‪-‮⁦-⁩﻿]'
       AND strpos(p, '  ') = 0
$$;

-- الكمية بالألف من الوحدة: الوزن والحجم والطول بثلاث خاناتٍ عشرية، وما يُعدّ صحيحٌ.
CREATE FUNCTION ew_inv_qty_ok(p_unit text, p_milli bigint) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT p_milli BETWEEN 1 AND 1000000000
       AND (p_unit IN ('KG', 'LITRE', 'METRE') OR p_milli % 1000 = 0)
$$;

-- نسبة الضريبة بأجزاء العشرة آلاف لكل فئة (S خاضعة، Z نسبة الصفر، E معفاة، O غير خاضعة).
CREATE FUNCTION ew_inv_vat_bp(p_category text) RETURNS integer
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT CASE p_category WHEN 'S' THEN 1500 WHEN 'Z' THEN 0 WHEN 'E' THEN 0 WHEN 'O' THEN 0 END
$$;

-- مفتاح الاسم: «أ إ آ ٱ» ← «ا»، «ى» ← «ي»، «ة» ← «ه»، والأرقام الهندية ← العربية،
-- بلا تطويلٍ ولا تشكيل، ومسافاتٌ مفردة. «كرتونة ماء» و«كرتونه ماء» صنفٌ واحد.
CREATE FUNCTION ew_inv_name_key(p text) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT btrim(regexp_replace(regexp_replace(
               translate(lower(normalize(p, NFKC)),
                         'أإآٱىة٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹ـ', 'اااايه01234567890123456789'),
               '[ً-ْٰ]', '', 'g'), '\s+', ' ', 'g'))
$$;

-- مفتاح رقم المستند للمقارنة: أرقامٌ عربية، وحروفٌ كبيرة، بلا فواصل ولا مسافات.
CREATE FUNCTION ew_inv_doc_key(p text) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT upper(regexp_replace(translate(normalize(p, NFKC),
                                          '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'),
                                '[\s/._#-]', '', 'g'))
$$;

-- رقم المستند كما يُكتب: حروفٌ لاتينية أو عربية وأرقامٌ وفواصل بسيطة.
CREATE FUNCTION ew_inv_doc_no_ok(p text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT ew_inv_text_ok(p, 40)
       AND p ~ '^[A-Za-z0-9ء-ي٠-٩۰-۹/._ #-]+$'
       AND ew_inv_doc_key(p) <> ''
$$;

-- ── الإعدادات ───────────────────────────────────────────────────────────
-- سؤالٌ واحد قبل أول تسجيل: هل تدخل ضريبة المشتريات في تكلفة الصنف؟ (تدخل حين لا
-- تستردّها المنشأة.) يُقفل بعد أول حركة: تغييره يغيّر معنى كل متوسطٍ سابق.
CREATE TABLE inv_settings (
    user_id               uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    cost_includes_vat     boolean NOT NULL,
    row_version           integer NOT NULL DEFAULT 1,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now()
);

-- عدّادات الترقيم. لا يقرؤها دور الويب ولا يكتبها: تأخذ منها دوالّ التسجيل وحدها.
CREATE TABLE inv_counters (
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    kind    text NOT NULL CONSTRAINT inv_counter_kind CHECK (kind IN ('PURCHASE', 'RETURN', 'REVERSAL', 'VOUCHER')),
    last_no integer NOT NULL CONSTRAINT inv_counter_range CHECK (last_no BETWEEN 1 AND 999999),
    PRIMARY KEY (user_id, kind)
);

-- ── الموردون والأصناف ───────────────────────────────────────────────────
CREATE TABLE inv_suppliers (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name        text NOT NULL CONSTRAINT inv_supplier_name_shape CHECK (ew_inv_text_ok(name, 60)),
    -- يكتبه المحفّز من الاسم.
    name_key    text NOT NULL DEFAULT '',
    -- الرقم الضريبي كما في معيار ZATCA (BR-KSA-40): خمس عشرة خانة، أولها وآخرها 3.
    vat_number  text CONSTRAINT inv_supplier_vat_shape CHECK (vat_number IS NULL OR vat_number ~ '^3[0-9]{13}3$'),
    is_active   boolean NOT NULL DEFAULT true,
    row_version integer NOT NULL DEFAULT 1,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id)
);
CREATE UNIQUE INDEX inv_suppliers_name ON inv_suppliers (user_id, name_key) WHERE is_active;
CREATE INDEX inv_suppliers_user ON inv_suppliers (user_id, is_active, name_key);

CREATE TABLE inv_items (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name                text NOT NULL CONSTRAINT inv_item_name_shape CHECK (ew_inv_text_ok(name, 60)),
    name_key            text NOT NULL DEFAULT '',
    code                text CONSTRAINT inv_item_code_shape CHECK (code IS NULL OR code ~ '^[A-Za-z0-9][A-Za-z0-9._/-]{0,19}$'),
    -- STOCK يُخزَّن ويُعدّ؛ SERVICE مصروفٌ بلا رصيد (شحن، تركيب).
    kind                text NOT NULL CONSTRAINT inv_item_kind CHECK (kind IN ('STOCK', 'SERVICE')),
    unit                text NOT NULL CONSTRAINT inv_item_unit
                            CHECK (unit IN ('PIECE', 'BOX', 'CARTON', 'PACK', 'PALLET', 'KG', 'LITRE', 'METRE', 'SERVICE')),
    vat_category        text NOT NULL DEFAULT 'S' CONSTRAINT inv_item_vat_category CHECK (vat_category IN ('S', 'Z', 'E', 'O')),
    -- سعر الشراء المعتاد للوحدة قبل الضريبة، يُحدَّد عند الإنشاء ويُقترح في كل سطرٍ جديد.
    price_halalas       bigint NOT NULL CONSTRAINT inv_item_price_range CHECK (price_halalas BETWEEN 1 AND 1000000000),
    reorder_level_milli bigint,
    -- يكتبها محفّز الحركات وحده.
    on_hand_milli       bigint NOT NULL DEFAULT 0 CONSTRAINT inv_item_on_hand_range CHECK (on_hand_milli BETWEEN 0 AND 1000000000000),
    stock_value_halalas bigint NOT NULL DEFAULT 0 CONSTRAINT inv_item_value_range CHECK (stock_value_halalas >= 0),
    last_movement_at    timestamptz,
    is_active           boolean NOT NULL DEFAULT true,
    row_version         integer NOT NULL DEFAULT 1,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    CONSTRAINT inv_item_unit_matches_kind CHECK ((kind = 'SERVICE') = (unit = 'SERVICE')),
    CONSTRAINT inv_item_service_has_no_stock
        CHECK (kind = 'STOCK' OR (on_hand_milli = 0 AND stock_value_halalas = 0 AND reorder_level_milli IS NULL)),
    CONSTRAINT inv_item_empty_has_no_value CHECK (on_hand_milli > 0 OR stock_value_halalas = 0),
    CONSTRAINT inv_item_on_hand_shape CHECK (unit IN ('KG', 'LITRE', 'METRE') OR on_hand_milli % 1000 = 0),
    CONSTRAINT inv_item_reorder_shape
        CHECK (reorder_level_milli IS NULL OR reorder_level_milli = 0 OR ew_inv_qty_ok(unit, reorder_level_milli))
);
CREATE UNIQUE INDEX inv_items_name ON inv_items (user_id, name_key) WHERE is_active;
CREATE UNIQUE INDEX inv_items_code ON inv_items (user_id, upper(code)) WHERE code IS NOT NULL AND is_active;
CREATE INDEX inv_items_user ON inv_items (user_id, is_active, name_key);
CREATE INDEX inv_items_low ON inv_items (user_id)
    WHERE is_active AND reorder_level_milli IS NOT NULL AND on_hand_milli <= reorder_level_milli;

-- ── فاتورة الشراء ───────────────────────────────────────────────────────
CREATE TABLE inv_purchases (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status                text NOT NULL DEFAULT 'DRAFT'
                              CONSTRAINT inv_purchase_status CHECK (status IN ('DRAFT', 'POSTED', 'REVERSED')),
    -- يزيده المحفّز مع كل تعديلٍ في الرأس أو الأسطر.
    row_version           integer NOT NULL DEFAULT 1,
    supplier_id           uuid,
    -- رقم فاتورة المورّد كما طُبع عليها، ومفتاحه للمقارنة (يكتبه المحفّز).
    supplier_invoice_no   text CONSTRAINT inv_purchase_no_shape CHECK (supplier_invoice_no IS NULL OR ew_inv_doc_no_ok(supplier_invoice_no)),
    supplier_invoice_key  text,
    invoice_date          date CONSTRAINT inv_purchase_date_floor CHECK (invoice_date IS NULL OR invoice_date >= DATE '2000-01-01'),
    -- الأسعار في الأسطر شاملةٌ الضريبة (فاتورةٌ مبسّطة تذكر الإجمالي شاملاً) أم قبلها.
    prices_include_vat    boolean NOT NULL DEFAULT false,
    -- ما طُبع على فاتورة المورّد، للمقارنة بالمحسوب.
    printed_total_halalas bigint CONSTRAINT inv_purchase_printed_total CHECK (printed_total_halalas BETWEEN 0 AND 100000000000000),
    printed_vat_halalas   bigint CONSTRAINT inv_purchase_printed_vat CHECK (printed_vat_halalas BETWEEN 0 AND 100000000000000),
    note                  text CONSTRAINT inv_purchase_note_shape CHECK (note IS NULL OR ew_inv_text_ok(note, 200)),
    -- تكتبها دالّة التسجيل.
    number                integer,
    posted_at             timestamptz,
    supplier_name         text,
    supplier_vat_number   text,
    subtotal_halalas      bigint,
    vat_halalas           bigint,
    total_halalas         bigint,
    -- تكتبها دالّة القيد العكسي.
    reversal_number       integer,
    reversed_at           timestamptz,
    reversal_reason       text CONSTRAINT inv_purchase_reversal_reason
                              CHECK (reversal_reason IS NULL OR reversal_reason IN ('DUPLICATE', 'WRONG_SUPPLIER', 'WRONG_DETAILS', 'OTHER')),
    reversal_note         text CONSTRAINT inv_purchase_reversal_note CHECK (reversal_note IS NULL OR ew_inv_text_ok(reversal_note, 200)),
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    FOREIGN KEY (supplier_id, user_id) REFERENCES inv_suppliers (id, user_id) ON DELETE CASCADE,
    CONSTRAINT inv_purchase_draft_unposted CHECK (status <> 'DRAFT' OR (
        number IS NULL AND posted_at IS NULL AND supplier_name IS NULL AND supplier_vat_number IS NULL
        AND subtotal_halalas IS NULL AND vat_halalas IS NULL AND total_halalas IS NULL)),
    CONSTRAINT inv_purchase_posted_complete CHECK (status = 'DRAFT' OR (
        supplier_id IS NOT NULL AND supplier_invoice_no IS NOT NULL AND invoice_date IS NOT NULL
        AND printed_total_halalas IS NOT NULL AND number IS NOT NULL AND posted_at IS NOT NULL
        AND supplier_name IS NOT NULL AND subtotal_halalas >= 0 AND vat_halalas >= 0
        AND total_halalas = subtotal_halalas + vat_halalas)),
    CONSTRAINT inv_purchase_reversal_complete CHECK (
        (status = 'REVERSED') = (reversed_at IS NOT NULL)
        AND (reversed_at IS NULL) = (reversal_number IS NULL)
        AND (reversed_at IS NULL) = (reversal_reason IS NULL)
        AND (reversal_reason IS DISTINCT FROM 'OTHER' OR reversal_note IS NOT NULL))
);
CREATE UNIQUE INDEX inv_purchases_number ON inv_purchases (user_id, number) WHERE number IS NOT NULL;
CREATE UNIQUE INDEX inv_purchases_reversal_number ON inv_purchases (user_id, reversal_number) WHERE reversal_number IS NOT NULL;
CREATE INDEX inv_purchases_user_recent ON inv_purchases (user_id, status, updated_at DESC);
CREATE INDEX inv_purchases_supplier_no ON inv_purchases (user_id, supplier_id, supplier_invoice_key) WHERE status = 'POSTED';

CREATE TABLE inv_purchase_lines (
    purchase_id        uuid NOT NULL,
    user_id            uuid NOT NULL,
    -- يكتبه المحفّز: التالي بعد أكبر رقم.
    line_no            smallint NOT NULL CONSTRAINT inv_line_no_range CHECK (line_no BETWEEN 1 AND 999),
    item_id            uuid NOT NULL,
    quantity_milli     bigint NOT NULL CONSTRAINT inv_line_quantity_range CHECK (quantity_milli BETWEEN 1 AND 1000000000),
    -- بأساس الفاتورة: قبل الضريبة، أو شاملاً لها إن كانت prices_include_vat.
    unit_price_halalas bigint NOT NULL CONSTRAINT inv_line_price_range CHECK (unit_price_halalas BETWEEN 0 AND 1000000000),
    discount_halalas   bigint NOT NULL DEFAULT 0 CONSTRAINT inv_line_discount_range CHECK (discount_halalas >= 0),
    vat_category       text NOT NULL CONSTRAINT inv_line_vat_category CHECK (vat_category IN ('S', 'Z', 'E', 'O')),
    -- تكتبها دالّة التسجيل: ما حُسب، واسم الصنف ووحدته يومها.
    vat_rate_bp        integer,
    amount_halalas     bigint,
    net_halalas        bigint,
    line_vat_halalas   bigint,
    cost_halalas       bigint,
    item_name          text,
    unit               text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (purchase_id, line_no),
    FOREIGN KEY (purchase_id, user_id) REFERENCES inv_purchases (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id, user_id) REFERENCES inv_items (id, user_id) ON DELETE CASCADE,
    CONSTRAINT inv_line_posted_complete CHECK (
        num_nulls(vat_rate_bp, amount_halalas, net_halalas, line_vat_halalas, cost_halalas, item_name, unit) IN (0, 7)),
    CONSTRAINT inv_line_posted_figures CHECK (amount_halalas IS NULL OR (
        vat_rate_bp = ew_inv_vat_bp(vat_category) AND amount_halalas >= 0 AND net_halalas >= 0
        AND line_vat_halalas >= 0 AND cost_halalas >= net_halalas))
);
CREATE INDEX inv_purchase_lines_item ON inv_purchase_lines (item_id);

-- ── المرتجع ─────────────────────────────────────────────────────────────
-- من فاتورةٍ مسجّلة، سطراً سطراً، بسبب. يُسجّل خروج البضاعة وقيداً سالباً في الدفتر.
-- إشعار المورّد الدائن (المستند الذي يعدّل به ضريبة المدخلات) يُكتب رقمه حين يصل.
CREATE TABLE inv_returns (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status           text NOT NULL DEFAULT 'DRAFT' CONSTRAINT inv_return_status CHECK (status IN ('DRAFT', 'POSTED')),
    row_version      integer NOT NULL DEFAULT 1,
    purchase_id      uuid NOT NULL,
    return_date      date,
    reason           text CONSTRAINT inv_return_reason
                         CHECK (reason IS NULL OR reason IN ('DAMAGED', 'WRONG_ITEM', 'NOT_AS_SPECIFIED', 'EXCESS', 'EXPIRED', 'OTHER')),
    note             text CONSTRAINT inv_return_note_shape CHECK (note IS NULL OR ew_inv_text_ok(note, 200)),
    number           integer,
    posted_at        timestamptz,
    net_halalas      bigint,
    vat_halalas      bigint,
    total_halalas    bigint,
    credit_note_no   text CONSTRAINT inv_return_credit_note_shape CHECK (credit_note_no IS NULL OR ew_inv_doc_no_ok(credit_note_no)),
    credit_note_date date,
    credit_note_at   timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    FOREIGN KEY (purchase_id, user_id) REFERENCES inv_purchases (id, user_id) ON DELETE CASCADE,
    CONSTRAINT inv_return_draft_unposted CHECK (status <> 'DRAFT' OR (
        number IS NULL AND posted_at IS NULL AND net_halalas IS NULL AND vat_halalas IS NULL AND total_halalas IS NULL)),
    CONSTRAINT inv_return_posted_complete CHECK (status = 'DRAFT' OR (
        return_date IS NOT NULL AND reason IS NOT NULL AND (reason <> 'OTHER' OR note IS NOT NULL)
        AND number IS NOT NULL AND posted_at IS NOT NULL AND net_halalas >= 0 AND vat_halalas >= 0
        AND total_halalas = net_halalas + vat_halalas)),
    CONSTRAINT inv_return_credit_note_complete CHECK (
        num_nulls(credit_note_no, credit_note_date, credit_note_at) IN (0, 3))
);
CREATE UNIQUE INDEX inv_returns_number ON inv_returns (user_id, number) WHERE number IS NOT NULL;
CREATE INDEX inv_returns_user_recent ON inv_returns (user_id, status, updated_at DESC);
CREATE INDEX inv_returns_purchase ON inv_returns (purchase_id);

CREATE TABLE inv_return_lines (
    return_id      uuid NOT NULL,
    user_id        uuid NOT NULL,
    -- فاتورة المرتجع نفسها (يكتبها المحفّز)، ورقم سطرها الأصلي.
    purchase_id    uuid NOT NULL,
    line_no        smallint NOT NULL,
    quantity_milli bigint NOT NULL CONSTRAINT inv_return_line_quantity_range CHECK (quantity_milli BETWEEN 1 AND 1000000000),
    -- تكتبها دالّة التسجيل.
    net_halalas    bigint,
    vat_halalas    bigint,
    cost_halalas   bigint,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (return_id, line_no),
    FOREIGN KEY (return_id, user_id) REFERENCES inv_returns (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (purchase_id, line_no) REFERENCES inv_purchase_lines (purchase_id, line_no) ON DELETE CASCADE,
    CONSTRAINT inv_return_line_posted_complete CHECK (num_nulls(net_halalas, vat_halalas, cost_halalas) IN (0, 3)),
    CONSTRAINT inv_return_line_posted_figures CHECK (net_halalas IS NULL OR (net_halalas >= 0 AND vat_halalas >= 0 AND cost_halalas >= 0))
);
CREATE INDEX inv_return_lines_purchase ON inv_return_lines (purchase_id, line_no);

-- ── سند المخزون: رصيدٌ افتتاحي، وصرف، وجرد ──────────────────────────────
-- يُسجَّل بضغطةٍ واحدة بلا مسودة. client_token يولّده العميل عند فتح الخطوة، فالضغطة
-- المكرّرة تعيد السند نفسه ولا تكتب حركةً ثانية.
CREATE TABLE inv_vouchers (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    number            integer NOT NULL,
    kind              text NOT NULL CONSTRAINT inv_voucher_kind CHECK (kind IN ('OPENING', 'ISSUE', 'COUNT')),
    item_id           uuid NOT NULL,
    -- OPENING وISSUE: الكمية الواردة أو المصروفة. COUNT: المعدود فعلاً (صفرٌ ممكن).
    quantity_milli    bigint NOT NULL CONSTRAINT inv_voucher_quantity_range CHECK (quantity_milli BETWEEN 0 AND 1000000000000),
    -- COUNT: الرصيد قبل الجرد كما رآه صاحبه.
    on_hand_before_milli bigint,
    unit_cost_halalas bigint CONSTRAINT inv_voucher_cost_range CHECK (unit_cost_halalas IS NULL OR unit_cost_halalas BETWEEN 0 AND 1000000000),
    reason            text CONSTRAINT inv_voucher_reason CHECK (reason IS NULL OR reason IN ('SALE', 'USE', 'DAMAGE', 'OTHER')),
    note              text CONSTRAINT inv_voucher_note_shape CHECK (note IS NULL OR ew_inv_text_ok(note, 200)),
    occurred_on       date NOT NULL,
    client_token      uuid NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    UNIQUE (user_id, client_token),
    UNIQUE (user_id, number),
    FOREIGN KEY (item_id, user_id) REFERENCES inv_items (id, user_id) ON DELETE CASCADE,
    CONSTRAINT inv_voucher_fields CHECK (CASE kind
        WHEN 'OPENING' THEN quantity_milli > 0 AND unit_cost_halalas IS NOT NULL AND reason IS NULL AND on_hand_before_milli IS NULL
        WHEN 'ISSUE'   THEN quantity_milli > 0 AND unit_cost_halalas IS NULL AND reason IS NOT NULL AND on_hand_before_milli IS NULL
                            AND (reason <> 'OTHER' OR note IS NOT NULL)
        WHEN 'COUNT'   THEN reason IS NULL AND on_hand_before_milli IS NOT NULL END)
);
CREATE INDEX inv_vouchers_user_recent ON inv_vouchers (user_id, created_at DESC);

-- ── حركات المخزون ───────────────────────────────────────────────────────
-- الكمية والقيمة بلا إشارة؛ النوع يقول الاتجاه. القيمة الصادرة يكتبها المحفّز من
-- المتوسط الحالي، والواردة من مصدرها. لا تُعدَّل أبداً.
CREATE TABLE inv_movements (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seq                 bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    user_id             uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    item_id             uuid NOT NULL,
    kind                text NOT NULL CONSTRAINT inv_movement_kind CHECK (kind IN (
                            'PURCHASE_IN', 'OPENING_IN', 'COUNT_IN', 'RETURN_OUT', 'REVERSAL_OUT', 'ISSUE_OUT', 'COUNT_OUT')),
    quantity_milli      bigint NOT NULL CONSTRAINT inv_movement_quantity_range CHECK (quantity_milli BETWEEN 1 AND 1000000000000),
    value_halalas       bigint NOT NULL CONSTRAINT inv_movement_value_range CHECK (value_halalas >= 0),
    on_hand_after_milli bigint NOT NULL DEFAULT 0,
    value_after_halalas bigint NOT NULL DEFAULT 0,
    purchase_id         uuid,
    purchase_line_no    smallint,
    return_id           uuid,
    return_line_no      smallint,
    voucher_id          uuid,
    occurred_on         date NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (item_id, user_id) REFERENCES inv_items (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (purchase_id, purchase_line_no) REFERENCES inv_purchase_lines (purchase_id, line_no) ON DELETE CASCADE,
    FOREIGN KEY (return_id, return_line_no) REFERENCES inv_return_lines (return_id, line_no) ON DELETE CASCADE,
    FOREIGN KEY (voucher_id, user_id) REFERENCES inv_vouchers (id, user_id) ON DELETE CASCADE,
    CONSTRAINT inv_movement_source CHECK (CASE
        WHEN kind IN ('PURCHASE_IN', 'REVERSAL_OUT') THEN num_nonnulls(purchase_id, purchase_line_no) = 2
                                                         AND num_nonnulls(return_id, return_line_no, voucher_id) = 0
        WHEN kind = 'RETURN_OUT' THEN num_nonnulls(return_id, return_line_no) = 2
                                      AND num_nonnulls(purchase_id, purchase_line_no, voucher_id) = 0
        ELSE voucher_id IS NOT NULL AND num_nonnulls(purchase_id, purchase_line_no, return_id, return_line_no) = 0 END)
);
CREATE INDEX inv_movements_item ON inv_movements (item_id, seq DESC);
CREATE INDEX inv_movements_user ON inv_movements (user_id, seq DESC);

-- ── دفتر المشتريات (المصروفات) ──────────────────────────────────────────
-- قيدٌ لكل فاتورةٍ مسجّلة، وقيدٌ سالب لكل مرتجعٍ ولكل قيدٍ عكسي. منه تُجمع الفترات.
CREATE TABLE inv_ledger (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seq           bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    kind          text NOT NULL CONSTRAINT inv_ledger_kind CHECK (kind IN ('PURCHASE', 'RETURN', 'REVERSAL')),
    entry_date    date NOT NULL,
    net_halalas   bigint NOT NULL,
    vat_halalas   bigint NOT NULL,
    gross_halalas bigint NOT NULL,
    purchase_id   uuid NOT NULL,
    return_id     uuid,
    supplier_id   uuid NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (purchase_id, user_id) REFERENCES inv_purchases (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (return_id, user_id) REFERENCES inv_returns (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id, user_id) REFERENCES inv_suppliers (id, user_id) ON DELETE CASCADE,
    CONSTRAINT inv_ledger_sum CHECK (gross_halalas = net_halalas + vat_halalas),
    CONSTRAINT inv_ledger_sign CHECK (CASE kind WHEN 'PURCHASE' THEN net_halalas >= 0 AND vat_halalas >= 0
                                                 ELSE net_halalas <= 0 AND vat_halalas <= 0 END),
    CONSTRAINT inv_ledger_return CHECK ((kind = 'RETURN') = (return_id IS NOT NULL))
);
CREATE UNIQUE INDEX inv_ledger_one_per_purchase ON inv_ledger (purchase_id, kind) WHERE kind IN ('PURCHASE', 'REVERSAL');
CREATE UNIQUE INDEX inv_ledger_one_per_return ON inv_ledger (return_id) WHERE return_id IS NOT NULL;
CREATE INDEX inv_ledger_user_date ON inv_ledger (user_id, entry_date, seq);


-- ── تنبيهات القواعد ─────────────────────────────────────────────────────
-- التنبيه: رمزه وسطره وتفاصيله؛ والنصّ العربي يكتبه الخادم من قالبه باسم صاحب الحساب.
-- يُحسب من القواعد ويُحفظ عند التسجيل مع إقرار صاحبه. (تنبيهات سيمبول في ai_flags.)
CREATE TABLE inv_review_flags (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    purchase_id     uuid,
    return_id       uuid,
    content_digest  bytea NOT NULL CHECK (octet_length(content_digest) = 32),
    code            text NOT NULL CONSTRAINT inv_flag_code CHECK (code ~ '^[A-Z_]{3,40}$'),
    line_no         smallint,
    detail          jsonb NOT NULL DEFAULT '{}'
                        CONSTRAINT inv_flag_detail_shape CHECK (jsonb_typeof(detail) = 'object' AND octet_length(detail::text) <= 2000),
    acknowledged_at timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (purchase_id, user_id) REFERENCES inv_purchases (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (return_id, user_id) REFERENCES inv_returns (id, user_id) ON DELETE CASCADE,
    CONSTRAINT inv_flag_one_document CHECK (num_nonnulls(purchase_id, return_id) = 1),
    UNIQUE NULLS NOT DISTINCT (purchase_id, return_id, content_digest, code, line_no)
);
CREATE INDEX inv_review_flags_return ON inv_review_flags (return_id);

-- ════════════════════════════════════════════════════════════════════════
-- المحفّزات
-- ════════════════════════════════════════════════════════════════════════

-- المهنة تُفحص حيث يقع الأثر. FOR SHARE يقف أمام admin set-profession كما في الحملة.
CREATE FUNCTION ew_inv_require_storekeeper(p_user uuid) RETURNS void
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM 1 FROM users WHERE id = p_user AND is_active AND profession = 'STOREKEEPER' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'inv_needs_storekeeper';
    END IF;
END
$$;

CREATE FUNCTION ew_inv_settings_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM ew_inv_require_storekeeper(NEW.user_id);
        IF NEW.row_version <> 1 THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
        END IF;
        NEW.created_at := now();
        NEW.updated_at := now();
        RETURN NEW;
    END IF;
    IF NEW.user_id <> OLD.user_id OR NEW.row_version <> OLD.row_version OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
    END IF;
    IF NEW.cost_includes_vat <> OLD.cost_includes_vat
       AND (EXISTS (SELECT 1 FROM inv_movements WHERE user_id = NEW.user_id)
            OR EXISTS (SELECT 1 FROM inv_ledger WHERE user_id = NEW.user_id)) THEN
        RAISE EXCEPTION 'locked' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_cost_basis_locked';
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_settings BEFORE INSERT OR UPDATE ON inv_settings
    FOR EACH ROW EXECUTE FUNCTION ew_inv_settings_guard();

-- المورّد: لأمين المخزون، وألفان لكل حساب، ومفتاح اسمه من المحفّز.
CREATE FUNCTION ew_inv_supplier_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM ew_inv_require_storekeeper(NEW.user_id);
        PERFORM pg_advisory_xact_lock(hashtextextended('eyework.inv_suppliers:' || NEW.user_id::text, 0));
        IF (SELECT count(*) FROM inv_suppliers WHERE user_id = NEW.user_id) >= 2000 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_supplier_cap';
        END IF;
        IF NEW.row_version <> 1 OR NOT NEW.is_active THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
        END IF;
        NEW.created_at := now();
    ELSE
        IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.row_version <> OLD.row_version
           OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
        END IF;
        NEW.row_version := OLD.row_version + 1;
    END IF;
    NEW.name_key := ew_inv_name_key(NEW.name);
    IF NEW.name_key = '' THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_supplier_name_shape';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_supplier BEFORE INSERT OR UPDATE ON inv_suppliers
    FOR EACH ROW EXECUTE FUNCTION ew_inv_supplier_guard();

-- الصنف: لأمين المخزون، وخمسة آلاف لكل حساب، ويبدأ بلا رصيد. وحدته ونوعه يتغيّران
-- ما لم يُستعمل في سطرٍ أو حركة؛ ولا يُؤرشف وفيه رصيد. الرصيد والقيمة من الحركات وحدها
-- (لا منح لدور الويب عليهما).
CREATE FUNCTION ew_inv_item_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM ew_inv_require_storekeeper(NEW.user_id);
        PERFORM pg_advisory_xact_lock(hashtextextended('eyework.inv_items:' || NEW.user_id::text, 0));
        IF (SELECT count(*) FROM inv_items WHERE user_id = NEW.user_id) >= 5000 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_item_cap';
        END IF;
        IF NEW.row_version <> 1 OR NOT NEW.is_active OR NEW.on_hand_milli <> 0 OR NEW.stock_value_halalas <> 0
           OR NEW.last_movement_at IS NOT NULL THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
        END IF;
        NEW.created_at := now();
    ELSE
        IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.row_version <> OLD.row_version
           OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
        END IF;
        IF (NEW.unit, NEW.kind) IS DISTINCT FROM (OLD.unit, OLD.kind)
           AND (EXISTS (SELECT 1 FROM inv_movements WHERE item_id = OLD.id)
                OR EXISTS (SELECT 1 FROM inv_purchase_lines WHERE item_id = OLD.id)
                OR EXISTS (SELECT 1 FROM inv_vouchers WHERE item_id = OLD.id)) THEN
            RAISE EXCEPTION 'unit' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_item_unit_locked';
        END IF;
        IF OLD.is_active AND NOT NEW.is_active AND NEW.on_hand_milli > 0 THEN
            RAISE EXCEPTION 'stock' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_item_has_stock';
        END IF;
        NEW.row_version := OLD.row_version + 1;
    END IF;
    NEW.name_key := ew_inv_name_key(NEW.name);
    IF NEW.name_key = '' THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_item_name_shape';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_item BEFORE INSERT OR UPDATE ON inv_items
    FOR EACH ROW EXECUTE FUNCTION ew_inv_item_guard();

-- الفاتورة تبدأ مسودة، وعشرون مسودةً مفتوحة لكل حساب.
CREATE FUNCTION ew_inv_purchase_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM ew_inv_require_storekeeper(NEW.user_id);
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.number IS NOT NULL OR NEW.reversal_number IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_starts_as_draft';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.inv_drafts:' || NEW.user_id::text, 0));
    IF (SELECT count(*) FROM inv_purchases WHERE user_id = NEW.user_id AND status = 'DRAFT') >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_open_draft_cap';
    END IF;
    IF NEW.supplier_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM inv_suppliers WHERE id = NEW.supplier_id AND user_id = NEW.user_id AND is_active) THEN
        RAISE EXCEPTION 'supplier' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_supplier_archived';
    END IF;
    NEW.supplier_invoice_key := ew_inv_doc_key(NEW.supplier_invoice_no);
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_purchase_insert BEFORE INSERT ON inv_purchases
    FOR EACH ROW EXECUTE FUNCTION ew_inv_purchase_insert_guard();

-- المسودة تتعدّل؛ والمسجَّلة لا يتغيّر فيها شيءٌ إلا أن تُعكس، مرةً واحدة.
CREATE FUNCTION ew_inv_purchase_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
    END IF;
    IF OLD.status = 'REVERSED' THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_is_final';
    END IF;
    IF OLD.status = 'POSTED' THEN
        IF NEW.status <> 'REVERSED'
           OR ROW(NEW.supplier_id, NEW.supplier_invoice_no, NEW.supplier_invoice_key, NEW.invoice_date,
                  NEW.prices_include_vat, NEW.printed_total_halalas, NEW.printed_vat_halalas, NEW.note,
                  NEW.number, NEW.posted_at, NEW.supplier_name, NEW.supplier_vat_number,
                  NEW.subtotal_halalas, NEW.vat_halalas, NEW.total_halalas)
              IS DISTINCT FROM
              ROW(OLD.supplier_id, OLD.supplier_invoice_no, OLD.supplier_invoice_key, OLD.invoice_date,
                  OLD.prices_include_vat, OLD.printed_total_halalas, OLD.printed_vat_halalas, OLD.note,
                  OLD.number, OLD.posted_at, OLD.supplier_name, OLD.supplier_vat_number,
                  OLD.subtotal_halalas, OLD.vat_halalas, OLD.total_halalas) THEN
            RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_is_final';
        END IF;
    ELSE
        IF NEW.status = 'REVERSED' OR NEW.reversal_number IS NOT NULL THEN
            RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_transition';
        END IF;
        IF NEW.supplier_id IS DISTINCT FROM OLD.supplier_id AND NEW.supplier_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM inv_suppliers WHERE id = NEW.supplier_id AND user_id = NEW.user_id AND is_active) THEN
            RAISE EXCEPTION 'supplier' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_supplier_archived';
        END IF;
        NEW.supplier_invoice_key := ew_inv_doc_key(NEW.supplier_invoice_no);
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_purchase_guard BEFORE UPDATE ON inv_purchases
    FOR EACH ROW EXECUTE FUNCTION ew_inv_purchase_guard();

-- سطر الفاتورة: في المسودة وحدها، وأربعون سطراً على الأكثر، والكمية بشكل وحدة الصنف،
-- والخصم لا يتجاوز مبلغ السطر. وكل تعديلٍ يزيد رقم صفّ الفاتورة.
CREATE FUNCTION ew_inv_purchase_line_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    p    inv_purchases%ROWTYPE;
    item inv_items%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.purchase_id, NEW.user_id, NEW.line_no, NEW.created_at)
           IS DISTINCT FROM ROW(OLD.purchase_id, OLD.user_id, OLD.line_no, OLD.created_at) THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
        END IF;
    END IF;
    SELECT * INTO p FROM inv_purchases WHERE id = NEW.purchase_id AND user_id = NEW.user_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'purchase' USING ERRCODE = 'foreign_key_violation',
                                         CONSTRAINT = 'inv_purchase_lines_purchase_id_user_id_fkey';
    END IF;
    IF p.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
    END IF;
    -- ما تكتبه دالّة التسجيل وحده (الأرقام المحسوبة) لا يُفحص ولا يمسّ الرأس.
    IF TG_OP = 'UPDATE' AND ROW(NEW.item_id, NEW.quantity_milli, NEW.unit_price_halalas, NEW.discount_halalas, NEW.vat_category)
                            IS NOT DISTINCT FROM
                            ROW(OLD.item_id, OLD.quantity_milli, OLD.unit_price_halalas, OLD.discount_halalas, OLD.vat_category) THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF (SELECT count(*) FROM inv_purchase_lines WHERE purchase_id = p.id) >= 40 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_line_cap';
        END IF;
        NEW.line_no := coalesce((SELECT max(line_no) FROM inv_purchase_lines WHERE purchase_id = p.id), 0) + 1;
        NEW.created_at := now();
    END IF;
    SELECT * INTO item FROM inv_items WHERE id = NEW.item_id AND user_id = NEW.user_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'foreign_key_violation', CONSTRAINT = 'inv_purchase_lines_item_id_user_id_fkey';
    END IF;
    IF NOT item.is_active THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_item_archived';
    END IF;
    IF NOT ew_inv_qty_ok(item.unit, NEW.quantity_milli) THEN
        RAISE EXCEPTION 'quantity' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_quantity_unit';
    END IF;
    IF NEW.discount_halalas > round(NEW.quantity_milli::numeric * NEW.unit_price_halalas / 1000) THEN
        RAISE EXCEPTION 'discount' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_line_discount_exceeds';
    END IF;
    NEW.updated_at := now();
    UPDATE inv_purchases SET updated_at = now() WHERE id = p.id;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_purchase_line BEFORE INSERT OR UPDATE ON inv_purchase_lines
    FOR EACH ROW EXECUTE FUNCTION ew_inv_purchase_line_guard();

-- المرتجع من فاتورةٍ مسجّلة غير معكوسة، ويبدأ مسودةً بتاريخ اليوم في الرياض.
CREATE FUNCTION ew_inv_return_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM ew_inv_require_storekeeper(NEW.user_id);
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.number IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_starts_as_draft';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.inv_drafts:' || NEW.user_id::text, 0));
    IF (SELECT count(*) FROM inv_returns WHERE user_id = NEW.user_id AND status = 'DRAFT') >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_open_draft_cap';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM inv_purchases WHERE id = NEW.purchase_id AND user_id = NEW.user_id AND status = 'POSTED') THEN
        RAISE EXCEPTION 'purchase' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_needs_posted_purchase';
    END IF;
    NEW.return_date := coalesce(NEW.return_date, ew_riyadh_today());
    IF NEW.credit_note_no IS NOT NULL THEN
        NEW.credit_note_at := now();
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_return_insert BEFORE INSERT ON inv_returns
    FOR EACH ROW EXECUTE FUNCTION ew_inv_return_insert_guard();

-- المسودة تتعدّل؛ والمسجَّل لا يتغيّر إلا بإضافة رقم إشعار المورّد الدائن مرةً واحدة.
CREATE FUNCTION ew_inv_return_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    invoice_date date;
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version OR NEW.purchase_id <> OLD.purchase_id THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
    END IF;
    IF OLD.status = 'POSTED' THEN
        IF ROW(NEW.status, NEW.return_date, NEW.reason, NEW.note, NEW.number, NEW.posted_at,
               NEW.net_halalas, NEW.vat_halalas, NEW.total_halalas)
           IS DISTINCT FROM
           ROW(OLD.status, OLD.return_date, OLD.reason, OLD.note, OLD.number, OLD.posted_at,
               OLD.net_halalas, OLD.vat_halalas, OLD.total_halalas)
           OR OLD.credit_note_no IS NOT NULL OR NEW.credit_note_no IS NULL THEN
            RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_is_final';
        END IF;
    END IF;
    IF NEW.credit_note_no IS DISTINCT FROM OLD.credit_note_no OR NEW.credit_note_date IS DISTINCT FROM OLD.credit_note_date THEN
        SELECT p.invoice_date INTO invoice_date FROM inv_purchases p WHERE p.id = NEW.purchase_id;
        IF NEW.credit_note_date IS NOT NULL
           AND (NEW.credit_note_date > ew_riyadh_today() OR NEW.credit_note_date < invoice_date) THEN
            RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_credit_note_date';
        END IF;
        NEW.credit_note_at := CASE WHEN NEW.credit_note_no IS NULL THEN NULL ELSE now() END;
    ELSE
        NEW.credit_note_at := OLD.credit_note_at;
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_return_guard BEFORE UPDATE ON inv_returns
    FOR EACH ROW EXECUTE FUNCTION ew_inv_return_guard();

-- سطر المرتجع: في المسودة، ومن سطرٍ في فاتورته، بشكل وحدة الصنف، وما لا يتجاوز ما
-- بقي من السطر بعد المرتجعات المسجّلة. (يُعاد الفحص تحت القفل عند التسجيل.)
CREATE FUNCTION ew_inv_return_line_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    r        inv_returns%ROWTYPE;
    bought   bigint;
    unit     text;
    returned bigint;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.return_id, NEW.user_id, NEW.line_no, NEW.purchase_id, NEW.created_at)
           IS DISTINCT FROM ROW(OLD.return_id, OLD.user_id, OLD.line_no, OLD.purchase_id, OLD.created_at) THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_managed_columns';
        END IF;
    END IF;
    SELECT * INTO r FROM inv_returns WHERE id = NEW.return_id AND user_id = NEW.user_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'return' USING ERRCODE = 'foreign_key_violation',
                                       CONSTRAINT = 'inv_return_lines_return_id_user_id_fkey';
    END IF;
    IF r.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.quantity_milli = OLD.quantity_milli THEN
        RETURN NEW;
    END IF;
    NEW.purchase_id := r.purchase_id;
    SELECT l.quantity_milli, i.unit INTO bought, unit
      FROM inv_purchase_lines l JOIN inv_items i ON i.id = l.item_id
     WHERE l.purchase_id = r.purchase_id AND l.line_no = NEW.line_no;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'line' USING ERRCODE = 'foreign_key_violation',
                                     CONSTRAINT = 'inv_return_lines_purchase_id_line_no_fkey';
    END IF;
    IF NOT ew_inv_qty_ok(unit, NEW.quantity_milli) THEN
        RAISE EXCEPTION 'quantity' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_quantity_unit';
    END IF;
    SELECT coalesce(sum(rl.quantity_milli), 0) INTO returned
      FROM inv_return_lines rl JOIN inv_returns rr ON rr.id = rl.return_id
     WHERE rl.purchase_id = r.purchase_id AND rl.line_no = NEW.line_no AND rr.status = 'POSTED';
    IF NEW.quantity_milli > bought - returned THEN
        RAISE EXCEPTION 'remaining' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_exceeds_remaining';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF (SELECT count(*) FROM inv_return_lines WHERE return_id = r.id) >= 40 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_line_cap';
        END IF;
        NEW.created_at := now();
    END IF;
    NEW.updated_at := now();
    UPDATE inv_returns SET updated_at = now() WHERE id = r.id;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_return_line BEFORE INSERT OR UPDATE ON inv_return_lines
    FOR EACH ROW EXECUTE FUNCTION ew_inv_return_line_guard();

-- الحركة تكتب أثرها في رصيد الصنف وقيمته تحت قفل صفّه. الصادر بالمتوسط الحالي:
-- قيمته نصيبه من القيمة مقرّباً، وكلّها إن خرج الرصيد كلّه، فلا تبقى قيمةٌ بلا كمية.
CREATE FUNCTION ew_inv_movement_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    item inv_items%ROWTYPE;
BEGIN
    SELECT * INTO item FROM inv_items WHERE id = NEW.item_id AND user_id = NEW.user_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'foreign_key_violation', CONSTRAINT = 'inv_movements_item_id_user_id_fkey';
    END IF;
    IF item.kind <> 'STOCK' THEN
        RAISE EXCEPTION 'kind' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_movement_needs_stock_item';
    END IF;
    IF NOT (item.unit IN ('KG', 'LITRE', 'METRE') OR NEW.quantity_milli % 1000 = 0) THEN
        RAISE EXCEPTION 'quantity' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_quantity_unit';
    END IF;
    IF NEW.kind IN ('RETURN_OUT', 'REVERSAL_OUT', 'ISSUE_OUT', 'COUNT_OUT') THEN
        IF NEW.quantity_milli > item.on_hand_milli THEN
            RAISE EXCEPTION 'stock' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_negative_stock';
        END IF;
        NEW.value_halalas := CASE WHEN NEW.quantity_milli = item.on_hand_milli THEN item.stock_value_halalas
                                  ELSE round(item.stock_value_halalas::numeric * NEW.quantity_milli / item.on_hand_milli)::bigint END;
        NEW.on_hand_after_milli := item.on_hand_milli - NEW.quantity_milli;
        NEW.value_after_halalas := item.stock_value_halalas - NEW.value_halalas;
    ELSE
        NEW.on_hand_after_milli := item.on_hand_milli + NEW.quantity_milli;
        NEW.value_after_halalas := item.stock_value_halalas + NEW.value_halalas;
    END IF;
    NEW.created_at := now();
    UPDATE inv_items
       SET on_hand_milli = NEW.on_hand_after_milli, stock_value_halalas = NEW.value_after_halalas,
           last_movement_at = now()
     WHERE id = item.id;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_inv_movement_insert BEFORE INSERT ON inv_movements
    FOR EACH ROW EXECUTE FUNCTION ew_inv_movement_insert();

-- ما سُجّل لا يُعاد كتابته، ولا للمالك (دالّة 0002 نفسها).
CREATE TRIGGER trg_inv_movements_append_only BEFORE UPDATE ON inv_movements
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();
CREATE TRIGGER trg_inv_ledger_append_only BEFORE UPDATE ON inv_ledger
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();
CREATE TRIGGER trg_inv_vouchers_append_only BEFORE UPDATE ON inv_vouchers
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();

-- ولا يُحذف إلا مع حسابه: الحذف المتتالي من users يأتي من محفّز المفتاح الخارجي، فعمقه
-- اثنان فأكثر؛ وحذفٌ مباشر (عمقه واحد) يُرفض، ولو من المالك. والمراجع داخل الحساب
-- تتتالى (ON DELETE CASCADE) ليُحذف الحساب كلّه في عبارةٍ واحدة؛ فالصنف والمورّد لا
-- يُحذفان مباشرةً أبداً (يُؤرشفان)، وإلا حذف تتاليهما أسطراً مسجّلة.
CREATE FUNCTION ew_inv_keep_record() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF pg_trigger_depth() < 2 THEN
        RAISE EXCEPTION 'permanent' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_record_is_permanent';
    END IF;
    RETURN OLD;
END
$$;
CREATE TRIGGER trg_inv_movements_keep BEFORE DELETE ON inv_movements
    FOR EACH ROW EXECUTE FUNCTION ew_inv_keep_record();
CREATE TRIGGER trg_inv_ledger_keep BEFORE DELETE ON inv_ledger
    FOR EACH ROW EXECUTE FUNCTION ew_inv_keep_record();
CREATE TRIGGER trg_inv_vouchers_keep BEFORE DELETE ON inv_vouchers
    FOR EACH ROW EXECUTE FUNCTION ew_inv_keep_record();
CREATE TRIGGER trg_inv_items_keep BEFORE DELETE ON inv_items
    FOR EACH ROW EXECUTE FUNCTION ew_inv_keep_record();
CREATE TRIGGER trg_inv_suppliers_keep BEFORE DELETE ON inv_suppliers
    FOR EACH ROW EXECUTE FUNCTION ew_inv_keep_record();
CREATE TRIGGER trg_inv_purchases_keep BEFORE DELETE ON inv_purchases
    FOR EACH ROW WHEN (OLD.status <> 'DRAFT') EXECUTE FUNCTION ew_inv_keep_record();
CREATE TRIGGER trg_inv_returns_keep BEFORE DELETE ON inv_returns
    FOR EACH ROW WHEN (OLD.status <> 'DRAFT') EXECUTE FUNCTION ew_inv_keep_record();

CREATE FUNCTION ew_inv_keep_posted_lines() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    posted boolean;
BEGIN
    IF pg_trigger_depth() >= 2 THEN
        RETURN OLD;
    END IF;
    IF TG_TABLE_NAME = 'inv_purchase_lines' THEN
        posted := EXISTS (SELECT 1 FROM inv_purchases WHERE id = OLD.purchase_id AND status <> 'DRAFT');
    ELSE
        posted := EXISTS (SELECT 1 FROM inv_returns WHERE id = OLD.return_id AND status <> 'DRAFT');
    END IF;
    IF posted THEN
        RAISE EXCEPTION 'permanent' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_record_is_permanent';
    END IF;
    RETURN OLD;
END
$$;
CREATE TRIGGER trg_inv_purchase_lines_keep BEFORE DELETE ON inv_purchase_lines
    FOR EACH ROW EXECUTE FUNCTION ew_inv_keep_posted_lines();
CREATE TRIGGER trg_inv_return_lines_keep BEFORE DELETE ON inv_return_lines
    FOR EACH ROW EXECUTE FUNCTION ew_inv_keep_posted_lines();

-- ما قاله سيمبول عن مسودةٍ نُبذت يُحذف معها (0009).
CREATE TRIGGER trg_inv_purchases_forget_ai AFTER DELETE ON inv_purchases
    FOR EACH ROW EXECUTE FUNCTION ew_ai_forget_subject('PURCHASE');
CREATE TRIGGER trg_inv_returns_forget_ai AFTER DELETE ON inv_returns
    FOR EACH ROW EXECUTE FUNCTION ew_ai_forget_subject('RETURN');


-- ════════════════════════════════════════════════════════════════════════
-- الحساب والتنبيهات (تُستدعى بصلاحية من يسأل، فيرى صفوفه وحدها)
-- ════════════════════════════════════════════════════════════════════════

-- أرقام كل سطرٍ كما تُسجَّل. مبلغ السطر = تقريب(الكمية × السعر) − الخصم. ضريبة كل
-- فئة = تقريب(مجموع مبالغها × النسبة) نصفاً إلى أعلى (BR-CO-17)، أو ×15/115 حين
-- تكون الأسعار شاملة؛ وتُوزَّع على أسطر الفئة بأكبر الكسور، فمجموع الأسطر يساوي
-- الفئة بالهللة ولا يكون سطرٌ سالباً.
CREATE FUNCTION ew_inv_purchase_calc(p_purchase uuid)
RETURNS TABLE (line_no smallint, item_id uuid, vat_category text, vat_rate_bp integer, quantity_milli bigint,
               amount_halalas bigint, net_halalas bigint, vat_halalas bigint)
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    WITH p AS (
        SELECT prices_include_vat AS incl FROM inv_purchases WHERE id = p_purchase
    ), l AS (
        SELECT l.line_no, l.item_id, l.vat_category, ew_inv_vat_bp(l.vat_category) AS bp, l.quantity_milli,
               round(l.quantity_milli::numeric * l.unit_price_halalas / 1000)::bigint - l.discount_halalas AS amount
          FROM inv_purchase_lines l WHERE l.purchase_id = p_purchase
    ), e AS (
        SELECT l.*, (CASE WHEN p.incl THEN 10000 + l.bp ELSE 10000 END) AS denom,
               l.amount::numeric * l.bp / (CASE WHEN p.incl THEN 10000 + l.bp ELSE 10000 END) AS exact
          FROM l CROSS JOIN p
    ), c AS (
        SELECT e.vat_category,
               round(sum(e.amount)::numeric * max(e.bp) / max(e.denom))::bigint - sum(floor(e.exact))::bigint AS extra
          FROM e GROUP BY e.vat_category
    ), r AS (
        SELECT e.*, floor(e.exact)::bigint AS fl,
               row_number() OVER (PARTITION BY e.vat_category ORDER BY e.exact - floor(e.exact) DESC, e.line_no) AS rk
          FROM e
    )
    SELECT r.line_no, r.item_id, r.vat_category, r.bp, r.quantity_milli, r.amount,
           r.amount - CASE WHEN p.incl THEN r.fl + (r.rk <= c.extra)::int ELSE 0 END,
           r.fl + (r.rk <= c.extra)::int
      FROM r JOIN c ON c.vat_category = r.vat_category CROSS JOIN p
     ORDER BY r.line_no
$$;

-- بصمة ما تراه المراجعة: أساس الأسعار، وكل سطرٍ بصنفه (مفتاح اسمه ووحدته) وأرقامه.
CREATE FUNCTION ew_inv_purchase_digest(p_purchase uuid) RETURNS bytea
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT sha256(convert_to(p.prices_include_vat::text || '#' || coalesce((
               SELECT string_agg(ROW(l.line_no, l.item_id, i.name_key, i.unit, l.quantity_milli,
                                     l.unit_price_halalas, l.discount_halalas, l.vat_category)::text, ';' ORDER BY l.line_no)
                 FROM inv_purchase_lines l JOIN inv_items i ON i.id = l.item_id
                WHERE l.purchase_id = p.id), ''), 'UTF8'))
      FROM inv_purchases p WHERE p.id = p_purchase
$$;

CREATE FUNCTION ew_inv_return_digest(p_return uuid) RETURNS bytea
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT sha256(convert_to(coalesce(r.reason, '') || '#' || coalesce((
               SELECT string_agg(ROW(rl.line_no, i.name_key, i.unit, rl.quantity_milli)::text, ';' ORDER BY rl.line_no)
                 FROM inv_return_lines rl
                 JOIN inv_purchase_lines l ON l.purchase_id = rl.purchase_id AND l.line_no = rl.line_no
                 JOIN inv_items i ON i.id = l.item_id
                WHERE rl.return_id = r.id), ''), 'UTF8'))
      FROM inv_returns r WHERE r.id = p_return
$$;

-- تنبيهات القواعد للفاتورة: ما يمكن أن يقع ويبدو خطأً. لا تمنع؛ يُقرّ بها صاحبها.
-- السعر: سعر الوحدة قبل الضريبة أمام وسيط آخر عشر مشترياتٍ مسجّلة للصنف (أو سعره
-- المحدَّد عند إنشائه إن لم يُشترَ بعد)، بفارقٍ مرّةً ونصفاً فأكثر. الكمية: أمام وسيط
-- آخر عشر، إن كانت ثلاثاً فأكثر، بفارق خمسة أضعافٍ فأكثر. «صفرٌ زائد» أو «ناقص» حين
-- يقع العُشر أو العشرة الأضعاف في المعتاد.
CREATE FUNCTION ew_inv_purchase_flags(p_purchase uuid)
RETURNS TABLE (code text, line_no smallint, detail jsonb)
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    WITH p AS (
        SELECT * FROM inv_purchases WHERE id = p_purchase
    ), calc AS (
        SELECT * FROM ew_inv_purchase_calc(p_purchase)
    ), tot AS (
        SELECT coalesce(sum(calc.net_halalas), 0) AS net, coalesce(sum(calc.vat_halalas), 0) AS vat FROM calc
    ), sup AS (
        SELECT s.* FROM inv_suppliers s JOIN p ON s.id = p.supplier_id
    ), hist AS (
        SELECT h.item_id, count(*) AS n,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY h.unit_net) AS ref_price,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY h.quantity_milli) AS ref_qty
          FROM (SELECT pl.item_id, pl.net_halalas * 1000.0 / pl.quantity_milli AS unit_net, pl.quantity_milli,
                       row_number() OVER (PARTITION BY pl.item_id ORDER BY pp.posted_at DESC, pp.number DESC) AS k
                  FROM inv_purchase_lines pl
                  JOIN inv_purchases pp ON pp.id = pl.purchase_id
                  JOIN p ON pp.user_id = p.user_id
                 WHERE pp.status = 'POSTED' AND pp.id <> p.id
                   AND pl.item_id IN (SELECT calc.item_id FROM calc)) h
         WHERE h.k <= 10
         GROUP BY h.item_id
    ), lines AS (
        SELECT calc.*, i.price_halalas AS item_price, i.vat_category AS item_category, l.unit_price_halalas,
               CASE WHEN calc.net_halalas > 0 THEN calc.net_halalas * 1000.0 / calc.quantity_milli END AS unit_net,
               h.n, h.ref_price, h.ref_qty
          FROM calc
          JOIN inv_purchase_lines l ON l.purchase_id = p_purchase AND l.line_no = calc.line_no
          JOIN inv_items i ON i.id = calc.item_id
          LEFT JOIN hist h ON h.item_id = calc.item_id
    ), priced AS (
        SELECT lines.*, coalesce(lines.ref_price, lines.item_price) AS ref,
               CASE WHEN lines.ref_price IS NULL THEN 'ITEM' ELSE 'HISTORY' END AS basis
          FROM lines
    )
    -- رقم فاتورة المورّد مسجّلٌ من قبل لهذا المورّد.
    SELECT 'DUPLICATE_SUPPLIER_INVOICE', NULL::smallint,
           jsonb_build_object('number', o.number, 'invoice_date', o.invoice_date, 'supplier_invoice_no', o.supplier_invoice_no)
      FROM p JOIN LATERAL (
               SELECT o.number, o.invoice_date, o.supplier_invoice_no FROM inv_purchases o
                WHERE o.user_id = p.user_id AND o.id <> p.id AND o.status = 'POSTED'
                  AND o.supplier_id = p.supplier_id AND o.supplier_invoice_key = p.supplier_invoice_key
                ORDER BY o.number DESC LIMIT 1) o ON true
    UNION ALL
    -- فاتورةٌ أخرى من المورّد نفسه بالتاريخ نفسه والإجمالي نفسه، برقمٍ مختلف.
    SELECT 'POSSIBLE_DUPLICATE', NULL, jsonb_build_object('number', o.number, 'total', o.total_halalas)
      FROM p CROSS JOIN tot JOIN LATERAL (
               SELECT o.number, o.total_halalas FROM inv_purchases o
                WHERE o.user_id = p.user_id AND o.id <> p.id AND o.status = 'POSTED'
                  AND o.supplier_id = p.supplier_id AND o.invoice_date = p.invoice_date
                  AND o.total_halalas = tot.net + tot.vat
                  AND o.supplier_invoice_key IS DISTINCT FROM p.supplier_invoice_key
                ORDER BY o.number DESC LIMIT 1) o ON true
    UNION ALL
    SELECT 'TOTAL_MISMATCH', NULL,
           jsonb_build_object('computed', tot.net + tot.vat, 'printed', p.printed_total_halalas)
      FROM p CROSS JOIN tot
     WHERE p.printed_total_halalas IS NOT NULL AND p.printed_total_halalas <> tot.net + tot.vat
    UNION ALL
    SELECT 'VAT_MISMATCH', NULL, jsonb_build_object('computed', tot.vat, 'printed', p.printed_vat_halalas)
      FROM p CROSS JOIN tot
     WHERE p.printed_vat_halalas IS NOT NULL AND p.printed_vat_halalas <> tot.vat
    UNION ALL
    -- ضريبةٌ بنسبة 15% من موردٍ بلا رقمٍ ضريبي هنا.
    SELECT 'VAT_WITHOUT_SUPPLIER_VAT_NUMBER', NULL, '{}'::jsonb
      FROM sup WHERE sup.vat_number IS NULL AND EXISTS (SELECT 1 FROM calc WHERE calc.vat_category = 'S')
    UNION ALL
    -- موردٌ مسجّلٌ في الضريبة ولا ضريبة على أيّ سطر.
    SELECT 'NO_VAT_CHARGED', NULL, '{}'::jsonb
      FROM sup CROSS JOIN tot
     WHERE sup.vat_number IS NOT NULL AND tot.net > 0 AND NOT EXISTS (SELECT 1 FROM calc WHERE calc.vat_category = 'S')
    UNION ALL
    SELECT 'OLD_INVOICE_DATE', NULL, jsonb_build_object('days', ew_riyadh_today() - p.invoice_date)
      FROM p WHERE p.invoice_date < ew_riyadh_today() - 90
    UNION ALL
    SELECT 'ZERO_PRICE', priced.line_no, '{}'::jsonb FROM priced WHERE priced.unit_price_halalas = 0
    UNION ALL
    SELECT 'PRICE_FAR_FROM_HISTORY', priced.line_no,
           jsonb_build_object('price', round(priced.unit_net), 'reference', round(priced.ref), 'basis', priced.basis,
                              'history', coalesce(priced.n, 0),
                              'extra_zero', priced.unit_net / 10 BETWEEN priced.ref / 1.5 AND priced.ref * 1.5,
                              'missing_zero', priced.unit_net * 10 BETWEEN priced.ref / 1.5 AND priced.ref * 1.5)
      FROM priced
     WHERE priced.unit_net > 0 AND priced.ref > 0
       AND (priced.unit_net >= priced.ref * 1.5 OR priced.unit_net * 1.5 <= priced.ref)
    UNION ALL
    SELECT 'QUANTITY_FAR_FROM_HISTORY', priced.line_no,
           jsonb_build_object('quantity', priced.quantity_milli, 'reference', round(priced.ref_qty), 'history', priced.n,
                              'extra_zero', priced.quantity_milli / 10.0 BETWEEN priced.ref_qty / 2 AND priced.ref_qty * 2,
                              'missing_zero', priced.quantity_milli * 10.0 BETWEEN priced.ref_qty / 2 AND priced.ref_qty * 2)
      FROM priced
     WHERE priced.n >= 3
       AND (priced.quantity_milli >= priced.ref_qty * 5 OR priced.quantity_milli * 5 <= priced.ref_qty)
    UNION ALL
    SELECT 'CATEGORY_CHANGED', priced.line_no,
           jsonb_build_object('category', priced.vat_category, 'usual', priced.item_category)
      FROM priced WHERE priced.vat_category <> priced.item_category
$$;

-- تنبيهات القواعد للمرتجع: إرجاع الفاتورة كلّها (لعلّ القيد العكسي أصحّ)، وفاتورةٌ قديمة.
CREATE FUNCTION ew_inv_return_flags(p_return uuid)
RETURNS TABLE (code text, line_no smallint, detail jsonb)
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    WITH r AS (
        SELECT * FROM inv_returns WHERE id = p_return
    ), p AS (
        SELECT pp.* FROM inv_purchases pp JOIN r ON pp.id = r.purchase_id
    ), remaining AS (
        SELECT l.line_no, l.quantity_milli
                   - coalesce((SELECT sum(rl.quantity_milli) FROM inv_return_lines rl JOIN inv_returns rr ON rr.id = rl.return_id
                                WHERE rl.purchase_id = l.purchase_id AND rl.line_no = l.line_no AND rr.status = 'POSTED'), 0) AS left_milli,
               l.quantity_milli AS bought,
               (SELECT rl.quantity_milli FROM inv_return_lines rl WHERE rl.return_id = p_return AND rl.line_no = l.line_no) AS this_milli
          FROM inv_purchase_lines l JOIN p ON l.purchase_id = p.id
    )
    SELECT 'FULL_RETURN', NULL::smallint, '{}'::jsonb
     WHERE EXISTS (SELECT 1 FROM remaining)
       AND NOT EXISTS (SELECT 1 FROM remaining WHERE left_milli <> bought OR this_milli IS DISTINCT FROM bought)
    UNION ALL
    SELECT 'OLD_PURCHASE', NULL, jsonb_build_object('days', r.return_date - p.invoice_date, 'invoice_date', p.invoice_date)
      FROM r CROSS JOIN p WHERE r.return_date - p.invoice_date > 90
$$;

-- مفاتيح التنبيهات القائمة الآن لمستند، كما يُقرّ بها صاحبه: «رمز» أو «رمز:سطر»، وما
-- قاله المساعد عن المحتوى الحالي يُسبق بـ«AI:».
CREATE FUNCTION ew_inv_flag_keys(p_purchase uuid, p_return uuid) RETURNS text[]
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT coalesce(array_agg(k ORDER BY k), '{}') FROM (
        SELECT f.code || coalesce(':' || f.line_no, '') AS k FROM ew_inv_purchase_flags(p_purchase) f WHERE p_purchase IS NOT NULL
        UNION
        SELECT f.code || coalesce(':' || f.line_no, '') FROM ew_inv_return_flags(p_return) f WHERE p_return IS NOT NULL
    ) keys
$$;

-- ════════════════════════════════════════════════════════════════════════
-- الأفعال (SECURITY DEFINER؛ صاحب الجلسة من ew_current_user() لا من معامِل)
-- ════════════════════════════════════════════════════════════════════════

-- الرقم التالي لنوع المستند، في معاملة التسجيل نفسها: تراجعها يعيده.
CREATE FUNCTION ew_inv_next_no(p_user uuid, p_kind text) RETURNS integer
LANGUAGE sql SET search_path = public, pg_temp AS $$
    INSERT INTO inv_counters (user_id, kind, last_no) VALUES (p_user, p_kind, 1)
    ON CONFLICT (user_id, kind) DO UPDATE SET last_no = inv_counters.last_no + 1
    RETURNING last_no
$$;

-- يقفل أصناف المستند بترتيب معرّفاتها: تسجيلان متزامنان يتشاركان أصنافاً لا يتقافلان.
CREATE FUNCTION ew_inv_lock_items(p_items uuid[]) RETURNS void
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM 1 FROM inv_items WHERE id = ANY (p_items) ORDER BY id FOR UPDATE;
END
$$;

CREATE FUNCTION ew_inv_check_ack(p_purchase uuid, p_return uuid, p_ack text[]) RETURNS void
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM unnest(ew_inv_flag_keys(p_purchase, p_return)) k
                WHERE k <> ALL (coalesce(p_ack, '{}'))) THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_flags_unacknowledged';
    END IF;
END
$$;

-- يُسجّل المسودة: أرقامٌ محسوبة، ورقمٌ تالٍ بلا فجوة، وحركات وارد بالتكلفة، وقيدٌ في
-- الدفتر، وإقرارٌ بكل تنبيهٍ قائم. يُرجع رقم الفاتورة.
CREATE FUNCTION ew_inv_post_purchase(p_purchase uuid, p_expected_row_version integer, p_ack text[]) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid    uuid := ew_current_user();
    p      inv_purchases%ROWTYPE;
    s      inv_settings%ROWTYPE;
    sup    inv_suppliers%ROWTYPE;
    digest bytea;
    n      integer;
    t_net  bigint;
    t_vat  bigint;
BEGIN
    PERFORM ew_inv_require_storekeeper(uid);
    SELECT * INTO p FROM inv_purchases WHERE id = p_purchase AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'purchase' USING ERRCODE = 'no_data_found';
    END IF;
    IF p.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
    END IF;
    IF p.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_stale_row_version';
    END IF;
    SELECT * INTO s FROM inv_settings WHERE user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'settings' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_needs_settings';
    END IF;
    IF p.supplier_id IS NULL OR p.supplier_invoice_no IS NULL OR p.invoice_date IS NULL OR p.printed_total_halalas IS NULL THEN
        RAISE EXCEPTION 'incomplete' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_purchase_incomplete';
    END IF;
    IF p.invoice_date > ew_riyadh_today() THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_purchase_future_date';
    END IF;
    SELECT * INTO sup FROM inv_suppliers WHERE id = p.supplier_id AND user_id = uid;
    IF NOT sup.is_active THEN
        RAISE EXCEPTION 'supplier' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_supplier_archived';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM inv_purchase_lines WHERE purchase_id = p.id) THEN
        RAISE EXCEPTION 'lines' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_purchase_no_lines';
    END IF;
    PERFORM ew_inv_lock_items(ARRAY(SELECT item_id FROM inv_purchase_lines WHERE purchase_id = p.id));
    IF EXISTS (SELECT 1 FROM inv_purchase_lines l JOIN inv_items i ON i.id = l.item_id
                WHERE l.purchase_id = p.id AND NOT i.is_active) THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_item_archived';
    END IF;
    PERFORM ew_inv_check_ack(p.id, NULL, p_ack);
    digest := ew_inv_purchase_digest(p.id);
    -- تنبيهات سيمبول على هذا المحتوى: لا تسجيل وفيها ما لم يُقرَّر، وتُغلق مع التسجيل.
    PERFORM ew_ai_gate('PURCHASE', p.id, digest);

    UPDATE inv_purchase_lines l
       SET vat_rate_bp = c.vat_rate_bp, amount_halalas = c.amount_halalas, net_halalas = c.net_halalas,
           line_vat_halalas = c.vat_halalas,
           cost_halalas = c.net_halalas + CASE WHEN s.cost_includes_vat THEN c.vat_halalas ELSE 0 END,
           item_name = i.name, unit = i.unit
      FROM ew_inv_purchase_calc(p.id) c, inv_items i
     WHERE l.purchase_id = p.id AND l.line_no = c.line_no AND i.id = l.item_id;
    SELECT sum(net_halalas), sum(line_vat_halalas) INTO t_net, t_vat FROM inv_purchase_lines WHERE purchase_id = p.id;

    n := ew_inv_next_no(uid, 'PURCHASE');
    UPDATE inv_purchases
       SET status = 'POSTED', number = n, posted_at = now(), supplier_name = sup.name,
           supplier_vat_number = sup.vat_number, subtotal_halalas = t_net, vat_halalas = t_vat,
           total_halalas = t_net + t_vat
     WHERE id = p.id;

    INSERT INTO inv_movements (user_id, item_id, kind, quantity_milli, value_halalas, purchase_id, purchase_line_no, occurred_on)
    SELECT uid, l.item_id, 'PURCHASE_IN', l.quantity_milli, l.cost_halalas, l.purchase_id, l.line_no, p.invoice_date
      FROM inv_purchase_lines l JOIN inv_items i ON i.id = l.item_id
     WHERE l.purchase_id = p.id AND i.kind = 'STOCK'
     ORDER BY l.line_no;

    INSERT INTO inv_ledger (user_id, kind, entry_date, net_halalas, vat_halalas, gross_halalas, purchase_id, supplier_id)
    VALUES (uid, 'PURCHASE', p.invoice_date, t_net, t_vat, t_net + t_vat, p.id, p.supplier_id);

    -- تنبيهات القواعد على ما سُجّل تُحفظ مُقرّاً بها، وما كان على محتوىً آخر يُحذف.
    DELETE FROM inv_review_flags WHERE purchase_id = p.id AND content_digest <> digest;
    UPDATE inv_review_flags SET acknowledged_at = now() WHERE purchase_id = p.id;
    INSERT INTO inv_review_flags (user_id, purchase_id, content_digest, code, line_no, detail, acknowledged_at)
    SELECT uid, p.id, digest, f.code, f.line_no, f.detail, now() FROM ew_inv_purchase_flags(p.id) f;
    RETURN n;
END
$$;

-- يُسجّل المرتجع: لكل سطرٍ نصيبه من صافي سطره الأصلي وضريبته (والمرتجع الأخير
-- يأخذ الباقي بالهللة)، وخروجٌ من المخزون بالمتوسط، وقيدٌ سالب في الدفتر.
CREATE FUNCTION ew_inv_post_return(p_return uuid, p_expected_row_version integer, p_ack text[]) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    r       inv_returns%ROWTYPE;
    p       inv_purchases%ROWTYPE;
    rl      record;
    digest  bytea;
    n       integer;
    q_left  bigint;
    v_net   bigint;
    v_vat   bigint;
    v_cost  bigint;
    t_net   bigint := 0;
    t_vat   bigint := 0;
BEGIN
    PERFORM ew_inv_require_storekeeper(uid);
    SELECT * INTO r FROM inv_returns WHERE id = p_return AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'return' USING ERRCODE = 'no_data_found';
    END IF;
    IF r.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
    END IF;
    IF r.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_stale_row_version';
    END IF;
    IF r.reason IS NULL THEN
        RAISE EXCEPTION 'reason' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_needs_reason';
    END IF;
    IF r.reason = 'OTHER' AND r.note IS NULL THEN
        RAISE EXCEPTION 'note' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_needs_note';
    END IF;
    -- قفل الفاتورة يصفّ مرتجعاتها وعكسها: مرتجعان متزامنان لا يأخذان الباقي نفسه.
    SELECT * INTO p FROM inv_purchases WHERE id = r.purchase_id AND user_id = uid FOR UPDATE;
    IF p.status <> 'POSTED' THEN
        RAISE EXCEPTION 'purchase' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_needs_posted_purchase';
    END IF;
    IF r.return_date > ew_riyadh_today() OR r.return_date < p.invoice_date THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_date';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM inv_return_lines WHERE return_id = r.id) THEN
        RAISE EXCEPTION 'lines' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_no_lines';
    END IF;
    PERFORM ew_inv_lock_items(ARRAY(SELECT l.item_id FROM inv_return_lines x
                                      JOIN inv_purchase_lines l ON l.purchase_id = x.purchase_id AND l.line_no = x.line_no
                                     WHERE x.return_id = r.id));
    PERFORM ew_inv_check_ack(NULL, r.id, p_ack);
    digest := ew_inv_return_digest(r.id);
    PERFORM ew_ai_gate('RETURN', r.id, digest);
    -- الأسطر تُحسب وتخرج بضاعتها والمرتجع ما زال مسودة (محفّز السطر يشترطها)، ثم يُغلق.
    FOR rl IN
        SELECT x.line_no, x.quantity_milli, l.quantity_milli AS bought, l.net_halalas AS l_net, l.line_vat_halalas AS l_vat,
               l.item_id, i.kind,
               coalesce(prev.q, 0) AS prev_q, coalesce(prev.net, 0) AS prev_net, coalesce(prev.vat, 0) AS prev_vat
          FROM inv_return_lines x
          JOIN inv_purchase_lines l ON l.purchase_id = x.purchase_id AND l.line_no = x.line_no
          JOIN inv_items i ON i.id = l.item_id
          LEFT JOIN LATERAL (
              SELECT sum(y.quantity_milli) AS q, sum(y.net_halalas) AS net, sum(y.vat_halalas) AS vat
                FROM inv_return_lines y JOIN inv_returns yr ON yr.id = y.return_id
               WHERE y.purchase_id = x.purchase_id AND y.line_no = x.line_no AND yr.status = 'POSTED') prev ON true
         WHERE x.return_id = r.id
         ORDER BY x.line_no
    LOOP
        q_left := rl.bought - rl.prev_q;
        IF rl.quantity_milli > q_left THEN
            RAISE EXCEPTION 'remaining' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_exceeds_remaining';
        END IF;
        IF rl.quantity_milli = q_left THEN
            v_net := rl.l_net - rl.prev_net;
            v_vat := rl.l_vat - rl.prev_vat;
        ELSE
            v_net := least(round(rl.l_net::numeric * rl.quantity_milli / rl.bought)::bigint, rl.l_net - rl.prev_net);
            v_vat := least(round(rl.l_vat::numeric * rl.quantity_milli / rl.bought)::bigint, rl.l_vat - rl.prev_vat);
        END IF;
        v_cost := 0;
        IF rl.kind = 'STOCK' THEN
            INSERT INTO inv_movements (user_id, item_id, kind, quantity_milli, value_halalas, return_id, return_line_no, occurred_on)
            VALUES (uid, rl.item_id, 'RETURN_OUT', rl.quantity_milli, 0, r.id, rl.line_no, r.return_date)
            RETURNING value_halalas INTO v_cost;
        END IF;
        UPDATE inv_return_lines SET net_halalas = v_net, vat_halalas = v_vat, cost_halalas = v_cost
         WHERE return_id = r.id AND line_no = rl.line_no;
        t_net := t_net + v_net;
        t_vat := t_vat + v_vat;
    END LOOP;
    n := ew_inv_next_no(uid, 'RETURN');
    UPDATE inv_returns
       SET status = 'POSTED', number = n, posted_at = now(), net_halalas = t_net, vat_halalas = t_vat,
           total_halalas = t_net + t_vat
     WHERE id = r.id;
    INSERT INTO inv_ledger (user_id, kind, entry_date, net_halalas, vat_halalas, gross_halalas, purchase_id, return_id, supplier_id)
    VALUES (uid, 'RETURN', r.return_date, -t_net, -t_vat, -(t_net + t_vat), p.id, r.id, p.supplier_id);

    DELETE FROM inv_review_flags WHERE return_id = r.id AND content_digest <> digest;
    UPDATE inv_review_flags SET acknowledged_at = now() WHERE return_id = r.id;
    INSERT INTO inv_review_flags (user_id, return_id, content_digest, code, line_no, detail, acknowledged_at)
    SELECT uid, r.id, digest, f.code, f.line_no, f.detail, now() FROM ew_inv_return_flags(r.id) f;
    RETURN n;
END
$$;

-- القيد العكسي لفاتورةٍ سُجّلت خطأً: لا مرتجع منها، وكل صنفٍ فيها ما زال رصيده يكفي.
-- يُخرج كمياتها بالمتوسط، ويكتب قيداً سالباً بإجماليها بتاريخ اليوم، ورقماً من تسلسله.
CREATE FUNCTION ew_inv_reverse_purchase(p_purchase uuid, p_expected_row_version integer, p_reason text, p_note text)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_current_user();
    p     inv_purchases%ROWTYPE;
    today date := ew_riyadh_today();
    n     integer;
BEGIN
    PERFORM ew_inv_require_storekeeper(uid);
    SELECT * INTO p FROM inv_purchases WHERE id = p_purchase AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'purchase' USING ERRCODE = 'no_data_found';
    END IF;
    IF p.status <> 'POSTED' THEN
        RAISE EXCEPTION 'posted' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_reversal_needs_posted';
    END IF;
    IF p.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_stale_row_version';
    END IF;
    IF p_reason IS NULL OR p_reason NOT IN ('DUPLICATE', 'WRONG_SUPPLIER', 'WRONG_DETAILS', 'OTHER') THEN
        RAISE EXCEPTION 'reason' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_reversal_needs_reason';
    END IF;
    IF p_reason = 'OTHER' AND p_note IS NULL THEN
        RAISE EXCEPTION 'note' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_reversal_needs_note';
    END IF;
    IF EXISTS (SELECT 1 FROM inv_returns WHERE purchase_id = p.id AND status = 'POSTED') THEN
        RAISE EXCEPTION 'returns' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_reversal_has_returns';
    END IF;
    PERFORM ew_inv_lock_items(ARRAY(SELECT item_id FROM inv_purchase_lines WHERE purchase_id = p.id));
    INSERT INTO inv_movements (user_id, item_id, kind, quantity_milli, value_halalas, purchase_id, purchase_line_no, occurred_on)
    SELECT uid, l.item_id, 'REVERSAL_OUT', l.quantity_milli, 0, l.purchase_id, l.line_no, today
      FROM inv_purchase_lines l JOIN inv_items i ON i.id = l.item_id
     WHERE l.purchase_id = p.id AND i.kind = 'STOCK'
     ORDER BY l.line_no;
    n := ew_inv_next_no(uid, 'REVERSAL');
    UPDATE inv_purchases
       SET status = 'REVERSED', reversal_number = n, reversed_at = now(), reversal_reason = p_reason, reversal_note = p_note
     WHERE id = p.id;
    INSERT INTO inv_ledger (user_id, kind, entry_date, net_halalas, vat_halalas, gross_halalas, purchase_id, supplier_id)
    VALUES (uid, 'REVERSAL', today, -p.subtotal_halalas, -p.vat_halalas, -p.total_halalas, p.id, p.supplier_id);
    RETURN n;
END
$$;

-- سند المخزون بضغطةٍ واحدة. OPENING: رصيدٌ افتتاحي لصنفٍ بلا حركة، بتكلفة وحدته.
-- ISSUE: صرفٌ بسبب. COUNT: المعدود فعلاً أمام الرصيد الذي رآه صاحبه؛ الفرق حركة،
-- والزيادة على رصيدٍ صفرٍ تحتاج تكلفة وحدة. التاريخ في الثلاثين يوماً الأخيرة.
CREATE FUNCTION ew_inv_stock_voucher(
    p_client_token uuid, p_kind text, p_item uuid, p_quantity_milli bigint, p_unit_cost_halalas bigint,
    p_reason text, p_note text, p_occurred_on date, p_expected_on_hand_milli bigint
) RETURNS TABLE (voucher_id uuid, voucher_number integer, replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_current_user();
    item  inv_items%ROWTYPE;
    v     inv_vouchers%ROWTYPE;
    today date := ew_riyadh_today();
    delta bigint;
    n     integer;
BEGIN
    PERFORM ew_inv_require_storekeeper(uid);
    SELECT * INTO v FROM inv_vouchers WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN QUERY SELECT v.id, v.number, true;
        RETURN;
    END IF;
    SELECT * INTO item FROM inv_items WHERE id = p_item AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    IF item.kind <> 'STOCK' THEN
        RAISE EXCEPTION 'kind' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_movement_needs_stock_item';
    END IF;
    IF NOT item.is_active THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_item_archived';
    END IF;
    IF p_occurred_on IS NULL OR p_occurred_on > today OR p_occurred_on < today - 30 THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_voucher_date';
    END IF;
    IF p_kind = 'COUNT' THEN
        IF p_expected_on_hand_milli IS DISTINCT FROM item.on_hand_milli THEN
            RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_count_stale';
        END IF;
        IF p_quantity_milli IS NULL OR (p_quantity_milli <> 0 AND NOT ew_inv_qty_ok(item.unit, p_quantity_milli)) THEN
            RAISE EXCEPTION 'quantity' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_quantity_unit';
        END IF;
        delta := p_quantity_milli - item.on_hand_milli;
        IF delta > 0 AND item.on_hand_milli = 0 AND p_unit_cost_halalas IS NULL THEN
            RAISE EXCEPTION 'cost' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_count_needs_cost';
        END IF;
    ELSIF p_kind IN ('OPENING', 'ISSUE') THEN
        IF p_quantity_milli IS NULL OR NOT ew_inv_qty_ok(item.unit, p_quantity_milli) THEN
            RAISE EXCEPTION 'quantity' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_quantity_unit';
        END IF;
        IF p_kind = 'OPENING' AND (EXISTS (SELECT 1 FROM inv_movements WHERE item_id = item.id) OR p_unit_cost_halalas IS NULL) THEN
            RAISE EXCEPTION 'opening' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_opening_not_first';
        END IF;
    ELSE
        RAISE EXCEPTION 'kind' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_voucher_kind';
    END IF;
    n := ew_inv_next_no(uid, 'VOUCHER');
    INSERT INTO inv_vouchers (user_id, number, kind, item_id, quantity_milli, on_hand_before_milli, unit_cost_halalas,
                              reason, note, occurred_on, client_token)
    VALUES (uid, n, p_kind, item.id, p_quantity_milli,
            CASE WHEN p_kind = 'COUNT' THEN item.on_hand_milli END,
            CASE WHEN p_kind = 'OPENING' OR (p_kind = 'COUNT' AND delta > 0 AND item.on_hand_milli = 0) THEN p_unit_cost_halalas END,
            CASE WHEN p_kind = 'ISSUE' THEN p_reason END, p_note, p_occurred_on, p_client_token)
    RETURNING * INTO v;
    IF p_kind = 'OPENING' THEN
        INSERT INTO inv_movements (user_id, item_id, kind, quantity_milli, value_halalas, voucher_id, occurred_on)
        VALUES (uid, item.id, 'OPENING_IN', p_quantity_milli,
                round(p_quantity_milli::numeric * p_unit_cost_halalas / 1000)::bigint, v.id, p_occurred_on);
    ELSIF p_kind = 'ISSUE' THEN
        INSERT INTO inv_movements (user_id, item_id, kind, quantity_milli, value_halalas, voucher_id, occurred_on)
        VALUES (uid, item.id, 'ISSUE_OUT', p_quantity_milli, 0, v.id, p_occurred_on);
    ELSIF delta > 0 THEN
        -- الزيادة بالمتوسط الحالي، أو بتكلفة الوحدة المعطاة حين لا رصيد يُشتقّ منه متوسط.
        INSERT INTO inv_movements (user_id, item_id, kind, quantity_milli, value_halalas, voucher_id, occurred_on)
        VALUES (uid, item.id, 'COUNT_IN', delta,
                CASE WHEN item.on_hand_milli = 0 THEN round(delta::numeric * p_unit_cost_halalas / 1000)::bigint
                     ELSE round(item.stock_value_halalas::numeric * delta / item.on_hand_milli)::bigint END,
                v.id, p_occurred_on);
    ELSIF delta < 0 THEN
        INSERT INTO inv_movements (user_id, item_id, kind, quantity_milli, value_halalas, voucher_id, occurred_on)
        VALUES (uid, item.id, 'COUNT_OUT', -delta, 0, v.id, p_occurred_on);
    END IF;
    RETURN QUERY SELECT v.id, v.number, false;
END
$$;

-- حذف سطرٍ من مسودة، ونبذ مسودةٍ كاملة: لا DELETE لدور الويب، فتمرّ بهذه الدوالّ.
CREATE FUNCTION ew_inv_remove_purchase_line(p_purchase uuid, p_line_no smallint, p_expected_row_version integer)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    p inv_purchases%ROWTYPE;
BEGIN
    SELECT * INTO p FROM inv_purchases WHERE id = p_purchase AND user_id = ew_current_user() FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'purchase' USING ERRCODE = 'no_data_found';
    END IF;
    IF p.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
    END IF;
    IF p.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_stale_row_version';
    END IF;
    DELETE FROM inv_purchase_lines WHERE purchase_id = p.id AND line_no = p_line_no;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'line' USING ERRCODE = 'no_data_found';
    END IF;
    UPDATE inv_purchases SET updated_at = now() WHERE id = p.id;
END
$$;

CREATE FUNCTION ew_inv_remove_return_line(p_return uuid, p_line_no smallint, p_expected_row_version integer)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    r inv_returns%ROWTYPE;
BEGIN
    SELECT * INTO r FROM inv_returns WHERE id = p_return AND user_id = ew_current_user() FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'return' USING ERRCODE = 'no_data_found';
    END IF;
    IF r.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
    END IF;
    IF r.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_stale_row_version';
    END IF;
    DELETE FROM inv_return_lines WHERE return_id = r.id AND line_no = p_line_no;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'line' USING ERRCODE = 'no_data_found';
    END IF;
    UPDATE inv_returns SET updated_at = now() WHERE id = r.id;
END
$$;

CREATE FUNCTION ew_inv_discard_draft(p_purchase uuid, p_return uuid, p_expected_row_version integer) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    doc_status  text;
    doc_version integer;
BEGIN
    IF num_nonnulls(p_purchase, p_return) <> 1 THEN
        RAISE EXCEPTION 'target' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_one_document';
    END IF;
    IF p_purchase IS NOT NULL THEN
        SELECT d.status, d.row_version INTO doc_status, doc_version FROM inv_purchases d WHERE d.id = p_purchase AND d.user_id = uid FOR UPDATE;
    ELSE
        SELECT d.status, d.row_version INTO doc_status, doc_version FROM inv_returns d WHERE d.id = p_return AND d.user_id = uid FOR UPDATE;
    END IF;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'document' USING ERRCODE = 'no_data_found';
    END IF;
    IF doc_status <> 'DRAFT' THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
    END IF;
    IF doc_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_stale_row_version';
    END IF;
    IF p_purchase IS NOT NULL THEN
        DELETE FROM inv_purchases WHERE id = p_purchase;
    ELSE
        DELETE FROM inv_returns WHERE id = p_return;
    END IF;
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- مراجعة المساعد وسقوفها
-- ════════════════════════════════════════════════════════════════════════
-- ما ربما فُوتر في آخر يوم من المراجعات والحملات وآثار ما حُذف. p_new_only: ما بدأه
-- حسابٌ مفتوحٌ جديد وحده. تستدعيها دوالّ المالك وحدها.
-- ── مراجعة سيمبول: على الدفتر الواحد (0009) ────────────────────────────
-- يفتح استدعاء STOCK_REVIEW لمسودةٍ لصاحب الجلسة بعد سقوف الدفتر، ويُرجع رقمه وبصمة
-- المحتوى الذي سيُرسل. السقوف والحالة والتكرار كلّها في ew_ai_request_open.
CREATE FUNCTION ew_inv_review_begin(p_purchase uuid, p_return uuid)
RETURNS TABLE (request_id uuid, content_digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid    uuid := ew_current_user();
    digest bytea;
BEGIN
    PERFORM ew_inv_require_storekeeper(uid);
    IF num_nonnulls(p_purchase, p_return) <> 1 THEN
        RAISE EXCEPTION 'target' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_one_document';
    END IF;
    IF p_purchase IS NOT NULL THEN
        PERFORM 1 FROM inv_purchases WHERE id = p_purchase AND user_id = uid AND status = 'DRAFT' FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM inv_purchase_lines WHERE purchase_id = p_purchase) THEN
            RAISE EXCEPTION 'lines' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_purchase_no_lines';
        END IF;
        digest := ew_inv_purchase_digest(p_purchase);
        RETURN QUERY SELECT ew_ai_request_open('STOCK_REVIEW', 'PURCHASE', p_purchase, digest), digest;
    ELSE
        PERFORM 1 FROM inv_returns WHERE id = p_return AND user_id = uid AND status = 'DRAFT' FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_document_not_draft';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM inv_return_lines WHERE return_id = p_return) THEN
            RAISE EXCEPTION 'lines' USING ERRCODE = 'check_violation', CONSTRAINT = 'inv_return_no_lines';
        END IF;
        digest := ew_inv_return_digest(p_return);
        RETURN QUERY SELECT ew_ai_request_open('STOCK_REVIEW', 'RETURN', p_return, digest), digest;
    END IF;
END
$$;

-- يحفظ ما قاله سيمبول بعد فحصه في الخادم (ai_flags) ويُغلق الاستدعاء. إن تغيّر المحتوى
-- منذ بدئها، أو سُجّل المستند أو نُبذ، لا يُحفظ شيء ويُغلق DISCARDED (ew_ai_flags_put).
CREATE FUNCTION ew_inv_review_record(p_request uuid, p_flags jsonb, p_usage jsonb) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
    r   ai_requests%ROWTYPE;
    d   bytea;
BEGIN
    SELECT * INTO r FROM ai_requests WHERE id = p_request AND user_id = uid AND feature = 'STOCK_REVIEW';
    IF NOT FOUND OR r.subject_id IS NULL THEN
        RAISE EXCEPTION 'request' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_request_not_open';
    END IF;
    IF r.subject_kind = 'PURCHASE' THEN
        SELECT ew_inv_purchase_digest(s.id) INTO d FROM inv_purchases s
         WHERE s.id = r.subject_id AND s.user_id = uid AND s.status = 'DRAFT' FOR UPDATE;
    ELSE
        SELECT ew_inv_return_digest(s.id) INTO d FROM inv_returns s
         WHERE s.id = r.subject_id AND s.user_id = uid AND s.status = 'DRAFT' FOR UPDATE;
    END IF;
    RETURN ew_ai_flags_put(p_request, d, p_flags, p_usage);
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- العزل بالصفّ: ENABLE + FORCE، وسياسة صاحب الجلسة لدور الويب، وسياسة المالك
-- ════════════════════════════════════════════════════════════════════════
ALTER TABLE inv_settings       ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_settings       FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_counters       ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_counters       FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_suppliers      ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_suppliers      FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_items          FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_purchases      ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_purchases      FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_purchase_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_purchase_lines FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_returns        ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_returns        FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_return_lines   ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_return_lines   FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_vouchers       ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_vouchers       FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_movements      ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_movements      FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_ledger         ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_ledger         FORCE  ROW LEVEL SECURITY;
ALTER TABLE inv_review_flags   ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv_review_flags   FORCE  ROW LEVEL SECURITY;

CREATE POLICY inv_settings_own       ON inv_settings       FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY inv_suppliers_own      ON inv_suppliers      FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY inv_items_own          ON inv_items          FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY inv_purchases_own      ON inv_purchases      FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY inv_purchase_lines_own ON inv_purchase_lines FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY inv_returns_own        ON inv_returns        FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY inv_return_lines_own   ON inv_return_lines   FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY inv_vouchers_own       ON inv_vouchers       FOR SELECT TO eyework_app
    USING (user_id = ew_current_user());
CREATE POLICY inv_movements_own      ON inv_movements      FOR SELECT TO eyework_app
    USING (user_id = ew_current_user());
CREATE POLICY inv_ledger_own         ON inv_ledger         FOR SELECT TO eyework_app
    USING (user_id = ew_current_user());
CREATE POLICY inv_review_flags_own   ON inv_review_flags   FOR SELECT TO eyework_app
    USING (user_id = ew_current_user());

CREATE POLICY inv_settings_owner_access       ON inv_settings       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_counters_owner_access       ON inv_counters       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_suppliers_owner_access      ON inv_suppliers      FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_items_owner_access          ON inv_items          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_purchases_owner_access      ON inv_purchases      FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_purchase_lines_owner_access ON inv_purchase_lines FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_returns_owner_access        ON inv_returns        FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_return_lines_owner_access   ON inv_return_lines   FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_vouchers_owner_access       ON inv_vouchers       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_movements_owner_access      ON inv_movements      FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_ledger_owner_access         ON inv_ledger         FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY inv_review_flags_owner_access   ON inv_review_flags   FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- ════════════════════════════════════════════════════════════════════════
-- المنح: بالأعمدة، بلا DELETE ولا TRUNCATE. ما يُحسب أو يُسجَّل تكتبه الدوالّ وحدها.
-- ════════════════════════════════════════════════════════════════════════
GRANT SELECT ON inv_settings TO eyework_app;
GRANT INSERT (user_id, cost_includes_vat) ON inv_settings TO eyework_app;
GRANT UPDATE (cost_includes_vat) ON inv_settings TO eyework_app;

GRANT SELECT ON inv_suppliers TO eyework_app;
GRANT INSERT (user_id, name, vat_number) ON inv_suppliers TO eyework_app;
GRANT UPDATE (name, vat_number, is_active) ON inv_suppliers TO eyework_app;

GRANT SELECT ON inv_items TO eyework_app;
GRANT INSERT (user_id, name, code, kind, unit, vat_category, price_halalas, reorder_level_milli) ON inv_items TO eyework_app;
GRANT UPDATE (name, code, kind, unit, vat_category, price_halalas, reorder_level_milli, is_active) ON inv_items TO eyework_app;

GRANT SELECT ON inv_purchases TO eyework_app;
GRANT INSERT (user_id, supplier_id, supplier_invoice_no, invoice_date, prices_include_vat, printed_total_halalas,
              printed_vat_halalas, note) ON inv_purchases TO eyework_app;
GRANT UPDATE (supplier_id, supplier_invoice_no, invoice_date, prices_include_vat, printed_total_halalas,
              printed_vat_halalas, note) ON inv_purchases TO eyework_app;

GRANT SELECT ON inv_purchase_lines TO eyework_app;
GRANT INSERT (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, discount_halalas, vat_category)
    ON inv_purchase_lines TO eyework_app;
GRANT UPDATE (item_id, quantity_milli, unit_price_halalas, discount_halalas, vat_category) ON inv_purchase_lines TO eyework_app;

GRANT SELECT ON inv_returns TO eyework_app;
GRANT INSERT (user_id, purchase_id, return_date, reason, note) ON inv_returns TO eyework_app;
GRANT UPDATE (return_date, reason, note, credit_note_no, credit_note_date) ON inv_returns TO eyework_app;

GRANT SELECT ON inv_return_lines TO eyework_app;
GRANT INSERT (return_id, user_id, line_no, quantity_milli) ON inv_return_lines TO eyework_app;
GRANT UPDATE (quantity_milli) ON inv_return_lines TO eyework_app;

GRANT SELECT ON inv_vouchers, inv_movements, inv_ledger, inv_review_flags TO eyework_app;

-- دوالّ القيود والحساب تُستدعى بصلاحية من يكتب أو يسأل.
REVOKE ALL ON FUNCTION ew_inv_text_ok(text, integer), ew_inv_qty_ok(text, bigint), ew_inv_vat_bp(text),
                       ew_inv_doc_no_ok(text), ew_inv_doc_key(text), ew_inv_name_key(text),
                       ew_inv_purchase_calc(uuid), ew_inv_purchase_digest(uuid), ew_inv_return_digest(uuid),
                       ew_inv_purchase_flags(uuid), ew_inv_return_flags(uuid), ew_inv_flag_keys(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_inv_text_ok(text, integer), ew_inv_qty_ok(text, bigint), ew_inv_vat_bp(text),
                          ew_inv_doc_no_ok(text), ew_inv_doc_key(text), ew_inv_name_key(text),
                          ew_inv_purchase_calc(uuid), ew_inv_purchase_digest(uuid), ew_inv_return_digest(uuid),
                          ew_inv_purchase_flags(uuid), ew_inv_return_flags(uuid), ew_inv_flag_keys(uuid, uuid) TO eyework_app;

-- تنبيه «تاريخٌ قديم» يقيس بيوم الرياض بصلاحية من يسأل؛ الدالّة لا تكشف إلا التاريخ.
GRANT EXECUTE ON FUNCTION ew_riyadh_today() TO eyework_app;

-- الأفعال.
REVOKE ALL ON FUNCTION ew_inv_post_purchase(uuid, integer, text[]), ew_inv_post_return(uuid, integer, text[]),
                       ew_inv_reverse_purchase(uuid, integer, text, text),
                       ew_inv_stock_voucher(uuid, text, uuid, bigint, bigint, text, text, date, bigint),
                       ew_inv_remove_purchase_line(uuid, smallint, integer), ew_inv_remove_return_line(uuid, smallint, integer),
                       ew_inv_discard_draft(uuid, uuid, integer),
                       ew_inv_review_begin(uuid, uuid), ew_inv_review_record(uuid, jsonb, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_inv_post_purchase(uuid, integer, text[]), ew_inv_post_return(uuid, integer, text[]),
                          ew_inv_reverse_purchase(uuid, integer, text, text),
                          ew_inv_stock_voucher(uuid, text, uuid, bigint, bigint, text, text, date, bigint),
                          ew_inv_remove_purchase_line(uuid, smallint, integer), ew_inv_remove_return_line(uuid, smallint, integer),
                          ew_inv_discard_draft(uuid, uuid, integer),
                          ew_inv_review_begin(uuid, uuid), ew_inv_review_record(uuid, jsonb, jsonb) TO eyework_app;

-- داخليّة: تستدعيها دوالّ المالك ومحفّزاته وحدها.
REVOKE ALL ON FUNCTION ew_inv_require_storekeeper(uuid), ew_inv_next_no(uuid, text), ew_inv_lock_items(uuid[]),
                       ew_inv_check_ack(uuid, uuid, text[]) FROM PUBLIC;

-- دوالّ المحفّزات لا يستدعيها أحدٌ مباشرة.
REVOKE ALL ON FUNCTION ew_inv_settings_guard(), ew_inv_supplier_guard(), ew_inv_item_guard(),
                       ew_inv_purchase_insert_guard(), ew_inv_purchase_guard(), ew_inv_purchase_line_guard(),
                       ew_inv_return_insert_guard(), ew_inv_return_guard(), ew_inv_return_line_guard(),
                       ew_inv_movement_insert(), ew_inv_keep_record(), ew_inv_keep_posted_lines() FROM PUBLIC;
