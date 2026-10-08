"""
الشاشة مضاءة أثناء الكتابة
==========================
الكتابة قد تستغرق حتى 200 ثانية، ومن يعمل بالنظر لا يلمس الشاشة لتبقى مضاءة.
فالقفل يُطلب داخل الضغطة، ويُطلب من جديد حين تعود الصفحة بعد أن أُخفيت (iOS
يُسقطه عندها)، ويُترك حين يصل الردّ؛ وإن لم يُمنح قيل إن الشاشة قد تُقفل.

`navigator.wakeLock` هنا بديلٌ للاختبار وحده: Chromium بلا شاشةٍ لا يمنحه.
"""

from __future__ import annotations

from eyework.tests.ui.flow import Flow, sample_photo

STUB = """
(() => {
    // hold: الطلب يبقى معلّقاً حتى grant()، كما يتأخّر WebKit بسؤال الإذن.
    const log = { requests: 0, released: 0, live: null, refuse: false, hold: false, pending: [], locks: [] };
    log.grant = () => log.pending.shift()();
    Object.defineProperty(window, '__wake', { value: log });
    Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
        request: async () => {
            if (log.refuse) throw new DOMException('refused', 'NotAllowedError');
            log.requests += 1;
            const lock = new EventTarget();
            lock.released = false;
            lock.release = async () => {
                if (lock.released) return;
                lock.released = true;
                log.released += 1;
                lock.dispatchEvent(new Event('release'));
            };
            log.locks.push(lock);
            if (log.hold) {
                return new Promise((resolve) => log.pending.push(() => { log.live = lock; resolve(lock); }));
            }
            log.live = lock;
            return lock;
        },
    } });
    let visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
    window.__setVisibility = (value) => { visibility = value; document.dispatchEvent(new Event('visibilitychange')); };
})();
"""


def _waiting(page_factory, server, *, refuse: bool = False):
    page = page_factory()
    page.add_init_script(STUB)
    held = []
    page.route("**/api/campaigns/*/copy", lambda route: held.append(route))
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/new")
    flow.screen("photo")
    if refuse:
        page.evaluate("() => { window.__wake.refuse = true; }")
    page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                 "buffer": sample_photo()}])
    flow.until("!document.querySelector('#photo-generate').disabled")
    page.click("#photo-generate")
    flow.until("!document.querySelector('#proposal-waiting').hidden")
    page.wait_for_function("() => state.waitingFor !== null")
    return page, flow, held


def test_the_lock_is_taken_in_the_press_retaken_after_hiding_and_released_at_the_end(page_factory, server):
    page, flow, held = _waiting(page_factory, server)
    page.wait_for_function("() => window.__wake.requests === 1")
    assert page.is_hidden("#proposal-awake")

    # النظام يُسقط القفل حين تُخفى الصفحة، ثم تعود والكتابة جارية.
    page.evaluate("() => { window.__setVisibility('hidden'); window.__wake.live.release(); }")
    page.evaluate("() => window.__setVisibility('visible')")
    page.wait_for_function("() => window.__wake.requests === 2")
    assert page.is_hidden("#proposal-awake")

    held[0].continue_()
    flow.until("!document.querySelector('#proposal-copy').hidden")
    page.wait_for_function("() => window.__wake.live.released && state.wakeLock === null")
    # بعد الردّ لا يُطلب القفل حين تعود الصفحة.
    page.evaluate("() => { window.__setVisibility('hidden'); window.__setVisibility('visible'); }")
    assert page.evaluate("() => window.__wake.requests") == 2
    assert not page.errors, page.errors


def test_a_refused_lock_is_said_on_the_waiting_screen(page_factory, server):
    page, flow, held = _waiting(page_factory, server, refuse=True)
    page.wait_for_selector("#proposal-awake:not([hidden])")
    audit = flow.audit("waiting-unlocked")
    assert not audit["vertical"] and not audit["clipped"], audit
    held[0].continue_()
    flow.until("!document.querySelector('#proposal-copy').hidden")
    assert not page.errors, page.errors


def test_a_lock_granted_after_the_wait_ended_is_let_go(page_factory, server):
    """طلبٌ من عودة الصفحة لم يُمنح بعد حين وصل الردّ: يُترك فور منحه، فلا تبقى الشاشة مضاءة بلا انتظار."""
    page, flow, held = _waiting(page_factory, server)
    page.wait_for_function("() => window.__wake.requests === 1")
    page.evaluate("""() => {
        window.__wake.hold = true;
        window.__setVisibility('hidden');
        window.__wake.live.release();
        window.__setVisibility('visible');
    }""")
    page.wait_for_function("() => window.__wake.pending.length === 1")
    held[0].continue_()
    flow.until("!document.querySelector('#proposal-copy').hidden")
    page.wait_for_function("() => state.waitingFor === null")
    page.evaluate("() => window.__wake.grant()")
    page.wait_for_function("() => window.__wake.locks.every((lock) => lock.released)", timeout=3000)
    assert page.evaluate("() => state.wakeLock") is None
    assert not page.errors, page.errors


def test_two_returns_while_waiting_keep_one_lock(page_factory, server):
    """الصفحة تُخفى وتعود مرتين والطلبان معلّقان: يبقى قفلٌ واحد، ويُترك عند الردّ."""
    page, flow, held = _waiting(page_factory, server)
    page.wait_for_function("() => window.__wake.requests === 1")
    page.evaluate("""() => {
        window.__wake.hold = true;
        window.__setVisibility('hidden');
        window.__wake.live.release();
        window.__setVisibility('visible');
        window.__setVisibility('hidden');
        window.__setVisibility('visible');
    }""")
    page.wait_for_function("() => window.__wake.pending.length === 2")
    page.evaluate("() => { window.__wake.grant(); window.__wake.grant(); }")
    page.wait_for_function("() => window.__wake.locks.filter((lock) => !lock.released).length === 1", timeout=3000)
    assert page.evaluate("() => window.__wake.locks.find((lock) => !lock.released) === state.wakeLock")
    held[0].continue_()
    flow.until("!document.querySelector('#proposal-copy').hidden")
    page.wait_for_function("() => window.__wake.locks.every((lock) => lock.released)", timeout=3000)
    assert not page.errors, page.errors
