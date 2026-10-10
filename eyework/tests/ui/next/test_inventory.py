"""
بوابة أمين المخزون على الواجهة الجديدة، بالحجمين
================================================
المسار الكامل نقرةً نقرة: الإعداد الأوّل، ثم فاتورة شراءٍ بمورّدٍ ومنتجٍ يُنشآن من سطرها، وتنبيه
التطبيق (فرق الإجمالي) وملاحظة سيمبول (عبر /api/ai/review بالبوّابة المصطنعة) وقرارهما، ثم
التسجيل، فبطاقة المنتج، فمرتجعٌ من الفاتورة بسببه وإشعاره الدائن، فجلسة جردٍ تُعدّ وتُرحَّل،
فالمصاريف والمجاميع. وفي كل شاشةٍ عقد النظر لكل حجم (flow.py)، وقاعدتا الهبوط والأقرب إلى النظر
في الحجم الكبير. المسار الكامل يمشي على إطارات الآيفون والآيباد والحاسوب (conftest.FRAMES).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from eyework.tests.fakes import FakeGateway, flag, review_reply
from eyework.tests.ui.next.conftest import DESKTOP, FRAMES, LOGIN, PHONES, STRESS, TABLETS, frame_ids, member
from eyework.tests.ui.next.flow import Flow

SIZES = ["compact", "gaze"]
BASE = "#/inventory"
SHOTS = os.environ.get("EYEWORK_SHOTS")


def _page(next_page, owner, server, size: str = "compact", width: int = 390, height: int = 664):
    """أمين مخزونٍ بالحجم المطلوب، وصفحةٌ داخلةٌ به، والبوّابة المصطنعة بلا أجوبة مجدولة."""
    member(owner, profession="STOREKEEPER", size="GAZE" if size == "gaze" else "COMPACT")
    gateway = FakeGateway()
    # المساعد يقرأ البوّابة من حالة التطبيق عند كل سؤال؛ والمراجع يحملها في حوضه منذ الإقلاع.
    server["app"].state.gateway = gateway
    server["app"].state.review_runner.gateway = gateway
    page = next_page(width, height, login=LOGIN, size=size)
    page.gateway = gateway
    return page


def _today(owner) -> str:
    with owner.cursor() as cursor:
        cursor.execute("SELECT ew_riyadh_today()")
        return cursor.fetchone()[0].isoformat()


def _shot(page, label: str) -> None:
    if SHOTS:
        size = page.evaluate("() => document.documentElement.dataset.size")
        width = page.viewport_size["width"]
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=f"{SHOTS}/inventory-{label}-{size}-{width}.png", full_page=size != "gaze")


def _audit(flow: Flow, label: str) -> None:
    # الحجم العادي يمرّ: يُقاس من أعلى الصفحة كما تُفتح، فالصفّ العلوي اللاصق لا يعلو إلا ما مرّ تحته.
    if not _gaze(flow.page):
        flow.page.evaluate("() => window.scrollTo(0, 0)")
    flow.audit(label)
    _shot(flow.page, label)


def _gaze(page) -> bool:
    return page.evaluate("() => document.documentElement.dataset.size") == "gaze"


def _pick(flow: Flow, picker: str, key: str, label: str) -> None:
    """خيارٌ من منتقٍ: قائمة Select في الحجم العادي، وخياراتٌ مكان الخطوة في الكبير (بمفتاحه)."""
    page = flow.page
    flow.press(f"#{picker}", lambda: flow.screen("[role=listbox], [data-options]"), label)
    if _gaze(page):
        while page.locator(f"[data-options] [data-key='{key}']").count() == 0:
            flow.press("[data-gaze-host] [role=group] button:has-text('التالية')", lambda: None, "التالية")
        flow.press(f"[data-options] [data-key='{key}']", lambda: page.wait_for_selector("[data-options]", state="detached"), label)
    else:
        flow.press(f"[role=listbox] [role=option][data-key='{key}'], [role=listbox] [role=option]:has-text('{key}')", lambda: page.wait_for_selector("[role=listbox]", state="detached"), label)


def _choose_option(flow: Flow, combobox: str, text: str, create: bool, label: str) -> None:
    """يكتب في قائمة البحث ثم يختار المطابق، أو «جديد باسم» حين لا مطابق."""
    page = flow.page
    page.fill(f"#{combobox}", text)
    # في الحجم الكبير الخيارات أزرارٌ في `[data-options]`، وفي العادي `option` في `listbox`.
    options, choice = ("[data-options]", "button") if _gaze(page) else ("[role=listbox]", "[role=option]")
    flow.screen(options)
    target = f"{options} {choice}[data-safe]" if create else f"{options} {choice}[data-value]:has-text('{text}')"
    flow.screen(target)
    flow.press(target, lambda: page.wait_for_selector(options, state="detached"), label)


def _setup(flow: Flow) -> None:
    page = flow.page
    page.goto(page.next + "#/")
    flow.screen("#settings-save")
    _audit(flow, "setup")
    assert page.evaluate("() => location.hash") == BASE
    assert page.input_value("#settings-store-name") == "المخزن الرئيسي"
    # لا جواب مسبق عن أساس التكلفة: «احفظ وابدأ» معطّلٌ حتى يُختار.
    assert page.locator("#settings-basis-net[aria-checked='true'], #settings-basis-gross[aria-checked='true'],"
                        " #settings-basis-net[aria-pressed='true'], #settings-basis-gross[aria-pressed='true']").count() == 0
    assert page.locator("#settings-save").is_disabled()
    flow.press("#settings-basis-net", lambda: flow.until("!document.querySelector('#settings-save').disabled"), "نعم، مسجّلة وتخصمها")
    flow.press("#settings-save", lambda: flow.screen("#home-purchase"), "احفظ وابدأ")
    _audit(flow, "home")
    assert page.text_content("#home-summary").startswith("لا شيء ينتظرك")


def _header_step(flow: Flow, today: str) -> None:
    """رأس الفاتورة: مورّدٌ يُنشأ من القائمة، ورقم الفاتورة والإجمالي المكتوب (116 لفرق ريالٍ مع الأسطر)."""
    page = flow.page
    gaze = _gaze(page)
    flow.screen("#purchase-supplier")
    _audit(flow, "purchase-empty")
    _choose_option(flow, "purchase-supplier", "مؤسسة النور", True, "مورّد جديد باسم")
    flow.screen("#quick-supplier-create")
    _audit(flow, "purchase-new-supplier")
    page.fill("#quick-supplier-vat", "300000000000003")
    flow.press("#quick-supplier-create", lambda: flow.screen("#purchase-rep"), "أنشئ المورّد")
    assert page.input_value("#purchase-supplier") == "مؤسسة النور"
    _audit(flow, "purchase-supplier")
    if gaze:
        flow.press("#purchase-next", lambda: flow.screen("#purchase-no"), "الفاتورة")
    page.fill("#purchase-no", "INV-1001")
    assert page.input_value("#purchase-date") == today
    page.locator("#purchase-no").blur()
    _audit(flow, "purchase-invoice")
    if gaze:
        # في الحجم الكبير خطوتا الفاتورة والمبالغ صفحتان.
        flow.press("#purchase-next", lambda: flow.screen("#purchase-received"), "الاستلام")
        _audit(flow, "purchase-receiving")
        flow.press("#purchase-next", lambda: flow.screen("#purchase-printed"), "المبالغ")
    page.fill("#purchase-printed", "116")
    page.locator("#purchase-printed").blur()
    _audit(flow, "purchase-amounts")
    if gaze:
        flow.press("#purchase-next", lambda: flow.screen("#purchase-basis-net"), "الأسعار")
        _audit(flow, "purchase-basis")
        flow.press("#purchase-next", lambda: flow.screen("#line-item"), "المنتجات")


def _line_step(flow: Flow) -> None:
    """سطرٌ بمنتجٍ يُنشأ من القائمة بوحدته وسعره: 10 كرتون × 10.00 = 115.00 مع الضريبة."""
    page = flow.page
    gaze = _gaze(page)
    flow.screen("#line-item")
    _audit(flow, "line-empty")
    _choose_option(flow, "line-item", "كرتونة ماء ٣٣٠ مل", True, "منتج جديد باسم")
    flow.screen("#quick-item-create")
    _audit(flow, "line-new-item")
    _pick(flow, "quick-item-unit", "CARTON" if gaze else "كرتون", "الوحدة")
    if gaze:
        # المنتج الجديد صفحتان في الحجم الكبير: الاسم والوحدة، ثم السعر والضريبة.
        flow.press("#quick-item-more", lambda: flow.screen("#quick-item-price"), "السعر والضريبة")
    page.fill("#quick-item-price", "10")
    flow.press("#quick-item-create", lambda: flow.until("(document.querySelector('#line-price') || {}).value === '10.00'")
               if not gaze else flow.screen("#line-quantity"), "أنشئ المنتج")
    assert page.input_value("#line-item") == "كرتونة ماء ٣٣٠ مل"
    page.fill("#line-quantity", "10")
    _audit(flow, "line-filled")
    if gaze:
        # السطر ثلاث صفحاتٍ في الحجم الكبير: السعر وخصمه في الثانية.
        flow.press("#line-more", lambda: flow.screen("#line-price"), "السعر والخصم")
        _audit(flow, "line-price")
    assert page.input_value("#line-price") == "10.00"
    flow.press("#line-save", lambda: flow.until("(document.querySelector('#line-item') || {}).value === ''"), "أضف السطر")
    _audit(flow, "line-saved")
    if not gaze:
        assert page.locator("#purchase-line-list li").count() == 1
        assert "115.00" in page.text_content("#purchase-line-list")


def _review_and_post(flow: Flow, name: str) -> None:
    """تنبيه فرق الإجمالي من التطبيق، وملاحظة سيمبول من البوّابة المصطنعة، وقرارهما، ثم التسجيل."""
    page = flow.page
    gaze = _gaze(page)
    page.gateway.queue(review_reply(flag(check="PRICE_IMPLAUSIBLE", field="unit_price", line=1,
                                         reason="سعر «كرتونة ماء ٣٣٠ مل» 10.00 ر.س يبدو منخفضاً لكرتونة ماء.",
                                         suggestion="تأكّد من السعر في فاتورة المورّد.")))
    flow.press("#purchase-review", lambda: flow.screen("[data-flag-status]"), "راجِع وسجّل")
    flow.until("document.querySelectorAll('[data-flag-status]').length >= 1")
    flow.until("!document.querySelector('#review-status') || !document.querySelector('#review-status').textContent.includes('يراجع')")
    _audit(flow, "review")
    if gaze:
        # تنبيهٌ في كل شاشة: قرارٌ ثم «التالي»؛ وآخرها شاشة التسجيل.
        for index in range(2):
            flow.screen("[data-flag-status='open']")
            flow.press("[data-flag-status] >> text=تابع رغم ذلك", lambda: flow.screen("[data-flag-status='acknowledged']"), "تابع رغم ذلك")
            _audit(flow, f"review-decided-{index}")
            if index == 0:
                flow.press("#review-next", lambda: flow.screen("[data-flag-status='open']"), "التالي")
            else:
                flow.press("#review-next", lambda: flow.screen("#review-post"), "التالي")
    else:
        cards = page.locator("[data-flag-status]")
        assert cards.count() == 2, cards.count()
        texts = page.eval_on_selector_all("[data-flag-status]", "(es) => es.map((e) => e.textContent)")
        assert any("116.00" in t and "115.00" in t for t in texts), texts
        assert any(f"⁨{name}⁩" in t for t in texts), texts
        assert page.locator("#review-post").is_disabled()
        for _ in range(2):
            flow.press("[data-flag-status='open'] >> text=تابع رغم ذلك", lambda: None, "تابع رغم ذلك")
        flow.until("document.querySelectorAll('[data-flag-status=\"acknowledged\"]').length === 2")
    flow.until("!document.querySelector('#review-post').disabled")
    _audit(flow, "review-ready")
    assert [url for method, url in page.requests if method == "POST" and url.endswith("/api/ai/review")]
    assert [url for method, url in page.requests if method == "POST" and "/api/ai/flags/" in url]
    flow.press("#review-post", lambda: flow.screen("#purchase-return"), "سجّل الفاتورة")
    _audit(flow, "posted")
    assert "ش-0001" in page.text_content("h1")
    assert "مسجّلة" in page.text_content("[data-screen-root]")


def _item_and_stock(flow: Flow) -> None:
    page = flow.page
    flow.press("#nav-home", lambda: flow.screen("#home-stock"), "الرئيسية")
    # الملخّص يُقرأ من جديد كلما عادت الرئيسية: المنتج المسجَّل بالفاتورة لم يُجرد بعد، وهو أوّل ما ينتظر
    # في الحجمين (الكبير يعرض أوّل بندٍ وحده).
    flow.until("document.querySelector('#home-summary').textContent.includes('لم تُجرد منذ تسعين يوماً: 1')")
    flow.press("#home-stock", lambda: flow.screen("#stock-search"), "المخزون")
    flow.until("document.querySelectorAll('[aria-label=\"المنتجات\"] li').length === 1")
    _audit(flow, "stock")
    assert "ص-00001" in page.text_content("[aria-label='المنتجات']")
    # الصفّ الظاهر: بطاقةٌ في الهاتف والحجم الكبير، وخليّة الجدول الأولى في الآيباد والحاسوب باللمس.
    flow.press("button[aria-label='افتح كرتونة ماء ٣٣٠ مل']:visible", lambda: flow.screen("#item-edit"), "افتح المنتج")
    _audit(flow, "item")
    assert "ص-00001" in page.text_content("[data-screen-root]")
    assert "10 كرتون" in page.text_content("[data-screen-root]")


def _return(flow: Flow, today: str) -> None:
    """مرتجع 3 كراتين من الفاتورة بسبب «تالفة»، ثم إشعاره الدائن."""
    page = flow.page
    gaze = _gaze(page)
    flow.press("#nav-home", lambda: flow.screen("#home-return"), "الرئيسية")
    flow.press("#home-return", lambda: flow.screen("#return-purchase"), "مرتجع من فاتورة")
    _audit(flow, "return-new")
    invoice = "[data-options] button" if gaze else "[role=listbox] [role=option]"
    flow.press("#return-purchase", lambda: flow.screen(invoice), "الفواتير")
    flow.press(invoice, lambda: flow.until("!document.querySelector('#return-start').disabled"), "الفاتورة")
    _audit(flow, "return-pick")
    flow.press("#return-start", lambda: flow.screen("[aria-label='أسطر الفاتورة']"), "ابدأ المرتجع")
    _audit(flow, "return-empty")
    # المعدِّل معطّلٌ حتى يُحفظ ما قبله: كل ضغطةٍ تنتظر حفظها.
    plus = "[aria-label='زِد الكمية المرتجعة من كرتونة ماء ٣٣٠ مل']"
    for n in range(1, 4):
        flow.press(plus, lambda n=n: flow.until(
            f"!document.querySelector(\"{plus}\").disabled"
            f" && document.querySelector('[aria-label=\"أسطر الفاتورة\"] output').textContent.includes('{n}')"), "زِد")
    _audit(flow, "return-quantities")
    if gaze:
        flow.press("#return-next", lambda: flow.screen("#return-reason"), "السبب")
    _pick(flow, "return-reason", "DAMAGED" if gaze else "تالفة", "سبب الإرجاع")
    _audit(flow, "return-reason")
    if gaze:
        # الجزء الثاني من خطوة السبب: المندوب والتاريخ.
        flow.press("#return-next", lambda: flow.screen("#return-rep"), "المندوب والتاريخ")
        _audit(flow, "return-rep")
    flow.press("#return-review", lambda: flow.screen("#review-post"), "راجِع وسجّل")
    flow.until("!document.querySelector('#review-post').disabled")
    _audit(flow, "return-review")
    flow.press("#review-post", lambda: flow.screen("#credit-number"), "سجّل المرتجع")
    _audit(flow, "return-posted")
    assert "ر-0001" in page.text_content("h1")
    page.fill("#credit-number", "CN-9")
    assert page.input_value("#credit-date") == today
    flow.press("#credit-save", lambda: page.wait_for_selector("#credit-number", state="detached"), "احفظ الإشعار")
    _audit(flow, "return-credited")
    assert "CN-9" in page.text_content("[data-screen-root]")


def _count(flow: Flow) -> None:
    """جلسة جردٍ مغلقة على كل المنتجات: الرصيد 7، يُعدّ 8 بسبب «عُثر عليه»، ثم تُرحَّل."""
    page = flow.page
    gaze = _gaze(page)
    flow.press("#nav-home", lambda: flow.screen("#home-count"), "الرئيسية")
    flow.press("#home-count", lambda: flow.screen("#counts-new"), "الجرد")
    _audit(flow, "counts-empty")
    flow.press("#counts-new", lambda: flow.screen("#count-scope-all"), "جلسة جديدة")
    _audit(flow, "count-new")
    if gaze:
        flow.press("#count-next", lambda: flow.screen("#count-blind-yes"), "التالي")
    flow.press("#count-open", lambda: flow.screen("#count-post"), "افتح الجلسة")
    _audit(flow, "count-open")
    assert page.locator("#count-post").is_disabled()
    assert "•••" in page.text_content("[aria-label='أسطر الجرد']") or "لم يُعدّ بعد" in page.text_content("[aria-label='أسطر الجرد']")
    flow.press("button[aria-label='عُدّ كرتونة ماء ٣٣٠ مل']:visible", lambda: flow.screen("#count-line-counted"), "عُدّ المنتج")
    _audit(flow, "count-line")
    page.fill("#count-line-counted", "8")
    # العدّ المغلق: الرصيد الدفتري يظهر بعد الحفظ، ومعه الفرق، ويُطلب سببه قبل الترحيل.
    flow.press("#count-line-save", lambda: flow.until("document.body.textContent.includes('الرصيد الدفتري')"), "احفظ")
    _audit(flow, "count-line-saved")
    assert "الفرق" in page.text_content("[data-screen-root]")
    _pick(flow, "count-line-reason", "FOUND" if gaze else "عُثر عليه", "سبب الفرق")
    flow.press("#count-line-save", lambda: flow.until("document.querySelector('#count-line-save') && !document.querySelector('#count-line-save').disabled"), "احفظ")
    flow.press("#count-line-back", lambda: flow.screen("#count-post"), "الجلسة")
    flow.until("!document.querySelector('#count-post').disabled")
    _audit(flow, "count-counted")
    flow.press("#count-post", lambda: flow.screen("#count-post-yes"), "رحّل الجرد")
    _audit(flow, "count-confirm")
    flow.press("#count-post-yes", lambda: flow.until("document.body.textContent.includes('مرحّلة')"), "نعم، رحّل")
    _audit(flow, "count-posted")


def _ledger(flow: Flow) -> None:
    page = flow.page
    flow.press("#nav-home", lambda: flow.screen("#home-expenses"), "الرئيسية")
    flow.press("#home-expenses", lambda: flow.screen("#expenses-previous"), "المصاريف")
    flow.until("document.querySelectorAll('[aria-label^=\"قيود\"] li').length === 2")
    _audit(flow, "expenses")
    assert page.locator("#expenses-next").is_disabled()
    flow.press("#expenses-previous", lambda: flow.until("document.querySelectorAll('[aria-label^=\"قيود\"] li').length === 0"), "الشهر السابق")
    _audit(flow, "expenses-empty")
    flow.press("#nav-home", lambda: flow.screen("#home-totals"), "الرئيسية")
    flow.press("#home-totals", lambda: flow.screen("text=المشتريات قبل الضريبة"), "المجاميع")
    _audit(flow, "totals")
    assert "المشتريات قبل الضريبة100" in page.text_content("[data-screen-root]").replace("\n", "")


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), FRAMES, ids=frame_ids(FRAMES))
def test_the_storekeeper_walks_from_setup_to_a_posted_count(next_page, server, owner, size, width, height):
    page = _page(next_page, owner, server, size, width, height)
    flow = Flow(page)
    today = _today(owner)
    _setup(flow)
    flow.press("#home-purchase", lambda: flow.screen("#purchase-supplier"), "فاتورة شراء جديدة")
    _header_step(flow, today)
    _line_step(flow)
    _review_and_post(flow, "علي")
    _item_and_stock(flow)
    _return(flow, today)
    _count(flow)
    _ledger(flow)
    assert not flow.failures(), "\n".join(flow.failures())
    if size == "gaze":
        assert not flow.landings, "\n".join(flow.landings)
        flow.gaze_safe()
    assert not page.errors, page.errors
    with owner.cursor() as cursor:
        cursor.execute("SELECT status, number FROM inv_purchases")
        assert cursor.fetchall() == [("POSTED", 1)]
        cursor.execute("SELECT on_hand_milli FROM inv_items")
        assert cursor.fetchone() == (8000,)
        cursor.execute("SELECT status, items_counted, items_matched FROM inv_count_sessions")
        assert cursor.fetchone() == ("POSTED", 1, 0)


@pytest.mark.parametrize("size", SIZES)
def test_a_draft_is_kept_on_the_server_and_an_undecided_symbol_note_blocks_posting(next_page, server, owner, size):
    """المسودة تعود بما حُفظ بعد إعادة التحميل، وملاحظة سيمبول التي لم يُبتّ فيها تحجز التسجيل (409)."""
    page = _page(next_page, owner, server, size, *PHONES[0])
    flow = Flow(page)
    today = _today(owner)
    _setup(flow)
    flow.press("#home-purchase", lambda: flow.screen("#purchase-supplier"), "فاتورة شراء جديدة")
    _header_step(flow, today)
    _line_step(flow)
    draft = page.evaluate("() => location.hash")
    page.reload()
    flow.screen("#purchase-supplier")
    assert page.input_value("#purchase-supplier") == "مؤسسة النور"
    if size == "gaze":
        flow.press("#purchase-next", lambda: flow.screen("#purchase-no"), "الفاتورة")
    assert page.input_value("#purchase-no") == "INV-1001"
    page.gateway.queue(review_reply(flag(check="PRICE_IMPLAUSIBLE", field="unit_price", line=1,
                                         reason="سعر «كرتونة ماء ٣٣٠ مل» 10.00 ر.س يبدو منخفضاً لكرتونة ماء.",
                                         suggestion="تأكّد من السعر في فاتورة المورّد.")))
    page.goto(page.next + draft + "/review")
    # تنبيه القاعدة (فرق الإجمالي 116 مقابل 115) يُقرّ به أوّلاً، فلا يبقى ما يحجز إلا ملاحظة سيمبول.
    if size == "gaze":
        flow.until("document.querySelector('h1') && document.querySelector('h1').textContent.includes('تنبيه 1 من 2')")
        assert page.locator("#review-next").is_disabled()
        flow.press("[data-flag-status='open'] >> text=تابع رغم ذلك", lambda: flow.screen("[data-flag-status='acknowledged']"), "تابع رغم ذلك")
        flow.press("#review-next", lambda: flow.until("document.querySelector('h1').textContent.includes('تنبيه 2 من 2')"), "التالي")
        assert "يبدو منخفضاً" in page.text_content("[data-flag-status='open']")
        assert page.locator("#review-next").is_disabled()
    else:
        flow.until("document.querySelectorAll('[data-flag-status]').length === 2")
        flow.press("[data-flag-status='open'] >> text=تابع رغم ذلك",
                   lambda: flow.until("document.querySelectorAll('[data-flag-status=\"acknowledged\"]').length === 1"), "تابع رغم ذلك")
        assert "يبدو منخفضاً" in page.text_content("[data-flag-status='open']")
        assert page.locator("#review-post").is_disabled()
    _audit(flow, "review-undecided")
    # والخادم يحجز التسجيل نفسه: الإقرار بتنبيهات القاعدة كلّها لا يكفي ما دامت الملاحظة بلا قرار.
    api = f"{server['base']}/api/inventory/purchases/{draft.rsplit('/', 1)[-1]}"
    keys = [f["key"] for f in page.request.get(api + "/flags").json()["flags"]]
    version = page.request.get(api).json()["row_version"]
    refused = page.request.post(api + "/post", data={"expected_row_version": version, "acknowledged": keys},
                                headers={"X-Eyework": "1", "Origin": server["base"]})
    assert (refused.status, refused.json()["code"]) == (409, "FLAGS_UNDECIDED")
    # قائمة فواتير الشراء تعرض المسودة نفسها، لا ثانيةً أنشأتها إعادة التحميل.
    page.goto(page.next + "#/inventory/purchases")
    flow.until("document.querySelectorAll('[aria-label=\"فواتير الشراء\"] li').length === 1")
    _audit(flow, "purchases")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), [PHONES[0], STRESS], ids=frame_ids([PHONES[0], STRESS]))
def test_a_discount_printed_on_a_line_is_entered_on_the_line_and_lowers_its_amount(next_page, server, owner, size, width, height):
    """خصم السطر المطبوع يُكتب في السطر نفسه: يُرفض ما يتجاوز مبلغ السطر، ويُطرح قبل الضريبة (10 × 10.00 − 10.00 = 90.00 + 13.50)."""
    page = _page(next_page, owner, server, size, width, height)
    flow = Flow(page)
    gaze = size == "gaze"
    _setup(flow)
    flow.press("#home-purchase", lambda: flow.screen("#purchase-supplier"), "فاتورة شراء جديدة")
    _header_step(flow, _today(owner))
    flow.screen("#line-item")
    _choose_option(flow, "line-item", "كرتونة ماء ٣٣٠ مل", True, "منتج جديد باسم")
    flow.screen("#quick-item-create")
    _pick(flow, "quick-item-unit", "CARTON" if gaze else "كرتون", "الوحدة")
    if gaze:
        # المنتج الجديد صفحتان في الحجم الكبير: الاسم والوحدة، ثم السعر والضريبة.
        flow.press("#quick-item-more", lambda: flow.screen("#quick-item-price"), "السعر والضريبة")
    page.fill("#quick-item-price", "10")
    flow.press("#quick-item-create", lambda: flow.until("(document.querySelector('#line-price') || {}).value === '10.00'")
               if not gaze else flow.screen("#line-quantity"), "أنشئ المنتج")
    page.fill("#line-quantity", "10")
    if gaze:
        # السعر والخصم في صفحة السطر الثانية، بزرٍّ في مكانه لا يتحرّك.
        _audit(flow, "line-main")
        flow.press("#line-more", lambda: flow.screen("#line-discount"), "السعر والخصم")
        assert page.locator("#line-quantity").count() == 0
    # أكبر من مبلغ السطر (100.00): يُرفض عند الحقل قبل أن يصل الخادم.
    page.fill("#line-discount", "150")
    flow.press("#line-save", lambda: flow.until("document.body.textContent.includes('الخصم من صفرٍ إلى مبلغ السطر')"), "أضف السطر")
    _audit(flow, "line-discount-refused")
    page.fill("#line-discount", "10")
    _audit(flow, "line-discount")
    flow.press("#line-save", lambda: flow.until("(document.querySelector('#line-item') || {}).value === ''"), "أضف السطر")
    draft = page.evaluate("() => location.hash").rsplit("/", 1)[-1]
    saved = page.request.get(f"{server['base']}/api/inventory/purchases/{draft}").json()
    assert [(line["discount_halalas"], line["net_halalas"], line["vat_halalas"]) for line in saved["lines"]] == [(1000, 9000, 1350)]
    assert saved["totals"]["gross"] == 10350
    if gaze:
        assert "103.50" in page.text_content("main")
    else:
        assert "خصم 10.00" in page.text_content("#purchase-line-list")
        assert "103.50" in page.text_content("#purchase-line-list")
        # «عدّل» يعيد الخصم إلى حقله كما حُفظ.
        flow.press("#purchase-line-list li >> text=عدّل", lambda: flow.until("(document.querySelector('#line-discount') || {}).value === '10.00'"), "عدّل")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), [STRESS, TABLETS[0], DESKTOP], ids=frame_ids([STRESS, TABLETS[0], DESKTOP]))
def test_the_product_form_and_the_supplier_card_fit_the_tightest_tablet_and_desktop_frames(next_page, server, owner, width, height):
    """نموذج المنتج بخطواته الستّ، وبطاقة المورّد بمندوبيه، بالحجم الكبير على الأضيق والآيباد والحاسوب."""
    page = _page(next_page, owner, server, "gaze", width, height)
    flow = Flow(page)
    _setup(flow)
    flow.press("#home-item", lambda: flow.screen("#item-name"), "منتج جديد")
    _audit(flow, "item-form-1")
    page.fill("#item-name", "أرز بسمتي")
    _pick(flow, "item-unit", "KG", "الوحدة")
    flow.press("#item-next", lambda: flow.screen("#item-price"), "التالي")
    _audit(flow, "item-form-2")
    page.fill("#item-price", "9")
    flow.press("#item-next", lambda: flow.screen("#item-barcode"), "التالي")
    _audit(flow, "item-form-3")
    page.fill("#item-barcode", "6281001234567")
    flow.press("#item-next", lambda: flow.screen("#item-category"), "التالي")
    _audit(flow, "item-form-4")
    flow.press("#item-next", lambda: flow.screen("#item-selling"), "التالي")
    _audit(flow, "item-form-5")
    page.fill("#item-selling", "12.5")
    flow.press("#item-next", lambda: flow.screen("#item-reorder"), "التالي")
    _audit(flow, "item-form-6")
    page.fill("#item-reorder", "20")
    flow.press("#item-save", lambda: flow.screen("#item-edit"), "أنشئ المنتج")
    _audit(flow, "item-created")
    assert "ص-00001" in page.text_content("[data-screen-root]")
    page.goto(page.next + "#/inventory/suppliers/new")
    flow.screen("#supplier-name")
    page.fill("#supplier-name", "مؤسسة النور")
    page.fill("#supplier-phone", "0112345678")
    flow.press("#supplier-save", lambda: flow.screen("#supplier-add-rep"), "أنشئ المورّد")
    _audit(flow, "supplier")
    flow.press("#supplier-add-rep", lambda: flow.screen("#rep-name"), "أضف مندوباً")
    page.fill("#rep-name", "أحمد")
    page.fill("#rep-mobile", "0501234567")
    _audit(flow, "rep-form")
    flow.press("#rep-save", lambda: flow.until("document.body.textContent.includes('الافتراضي')"), "احفظ")
    _audit(flow, "supplier-with-rep")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    flow.gaze_safe()


def test_the_tools_offer_the_vat_calculator_and_the_assistant_knows_the_screen(next_page, server, owner):
    page = _page(next_page, owner, server, "gaze", *PHONES[0])
    flow = Flow(page)
    _setup(flow)
    flow.open_tools()
    _audit(flow, "tools")
    names = page.eval_on_selector_all("dialog[open] ul button", "(bs) => bs.map((b) => b.textContent.trim())")
    # وفي الحجم الكبير على الهاتف «إعدادات المخزن» أداةٌ: رابط الرئيسية لا يتّسع مع أزرارها السبعة.
    expected = ("حاسبة الضريبة", "ابحث عن منتج", "إعدادات المخزن", "مساعدة")
    assert len(names) == len(expected) and all(n.startswith(e) for n, e in zip(names, expected)), names
    flow.press("dialog[open] >> text=حاسبة الضريبة", lambda: flow.screen("dialog[open] input"), "حاسبة الضريبة")
    page.fill("dialog[open] input", "100")
    flow.until("document.querySelector('dialog[open]').textContent.includes('115.00')")
    _audit(flow, "vat-tool")
    assert [url for method, url in page.requests if "/api/inventory/tools/vat" in url]
    flow.press("dialog[open] >> text=إغلاق", lambda: page.wait_for_selector("dialog[open]", state="detached"), "إغلاق")
    # الجواب نفسه (نصّ البوّابة المصطنعة)، لا كلمةٌ ظاهرة في الورقة قبل الإرسال.
    flow.ask_symbol("بماذا أبدأ اليوم؟", "حملاتي")
    _audit(flow, "chat")
    call = page.gateway.calls[-1]
    assert "الأصناف النشطة: 0" in call.user and "<label>الجرد</label>" in call.user
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors
    flow.gaze_safe()
