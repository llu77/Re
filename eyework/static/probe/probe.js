/*
 * فحص الإدخال — القياس
 * =====================
 * يجيب عن السؤال الذي يقوم عليه التطبيق كلّه: هل يصل الضغط بتتبّع العين في
 * iOS إلى محتوى الويب، في Safari وفي وضع الشاشة الرئيسية؟
 *
 * ثلاث قواعد تحكم هذا الملف:
 *   1. لا شيء يغادر الجهاز: لا fetch ولا XHR ولا sendBeacon ولا WebSocket.
 *      والصفحة تُخدم بـCSP تمنع الاتصال أصلاً، فالقاعدة يفرضها المتصفّح.
 *   2. لا تخزين: لا localStorage ولا sessionStorage ولا IndexedDB. السجلّ في
 *      الذاكرة، ويُنسخ يدوياً بزرّ.
 *   3. لا مؤقّتات: لا setTimeout ولا setInterval ولا requestAnimationFrame.
 *      الأزمنة تُقرأ من `event.timeStamp` وحده.
 *
 * وخلافاً للتطبيق، تستمع هذه الصفحة لأحداث المرور (pointerover…) لأنها
 * تقيسها؛ لا تتصرّف بناءً عليها.
 */

'use strict';

const $ = (id) => document.getElementById(id);
const LOG_CAP = 2000;
const LOGGED = [
    'pointerover', 'pointerenter', 'pointerout', 'pointerleave', 'pointerdown',
    'pointerup', 'pointercancel', 'click', 'focusin', 'mouseover', 'touchstart',
    'touchend', 'contextmenu',
];
const TARGETS = ['t44', 't56', 't72', 't96'];
// الأحجام التي يستعملها التطبيق فعلاً (72 فأكبر): عليها وحدها يقوم القرار،
// والأصغر منها قياسٌ للدقّة لا شرط.
const APP_TARGETS = ['t72', 't96'];
// «بالرأس» لتتبّع الرأس (iOS 26 فأحدث): يمرّ بالمكوث نفسه، لكن نتائجه تُعدّ وحدها
// ولا تُحسب نظراً.
const MODES = ['gaze', 'head', 'touch'];
const SNAP = { on: 'مُفعَّل', off: 'مُعطَّل' };
// إصدار iOS يكتبه المختبِر: منذ Safari 26 لا يذكر وكيل المستخدم في iOS إصدار النظام
// الحالي (WebKit)، فلا يفرّق بين 26 و27. يُقبل شكل الإصدار وحده.
const IOS_VERSION = /^\d{2}(?:\.\d{1,2}){0,2}$/;
const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp'];
const DIGITS = '٠١٢٣٤٥٦٧٨٩';

const state = {
    mode: 'gaze',
    section: 0,
    // حالة «الانتقال إلى العنصر» كما أعلنها المختبِر: null ما لم يُحدّدها.
    snap: null,
    ios: null,
    log: [],
    // الطريقة ← probe ← آخر مرورٍ قبل أول pointerdown، وأول pointerdown، وحركات
    // pointermove قبله، وأول نقرة، وعدد النقرات الموثوقة، ونوع المؤشر.
    // كل طريقةٍ تُعدّ وحدها: نقرات اللمس والرأس لا تُحسب نظراً أبداً.
    targets: { gaze: {}, head: {}, touch: {} },
    rearm: { clickedA: null, outSinceA: false, sawMove: false, result: null },
    stepper: { count: 0, times: [], result: null },
    scroll: { result: null, scrolled: false },
    file: null,
    check: null,
    dialog: { opened: false, closed: false },
    text: { focusedAt: null, result: null },
    share: null,
    navClicks: [],
};

const toArabic = (n) => String(n).replace(/[0-9]/g, (d) => DIGITS[d]);

function sections() {
    return Array.from(document.querySelectorAll('.sec'));
}

/* ── السجلّ ─────────────────────────────────────────────────────────── */

function probeOf(event) {
    const element = event.target instanceof Element ? event.target.closest('[data-probe]') : null;
    return element ? element.dataset.probe : null;
}

function record(event) {
    const probe = probeOf(event);
    if (!probe) {
        return;
    }
    if (state.log.length >= LOG_CAP) {
        state.log.shift();
    }
    // البُعد عن مركز الهدف: دقّة النظر على هذا الجهاز، لا الحجم وحده.
    const box = event.target.closest('[data-probe]').getBoundingClientRect();
    const x = Math.round(event.clientX || 0);
    const y = Math.round(event.clientY || 0);
    state.log.push({
        mode: state.mode,
        snap: state.snap,
        section: sections()[state.section].dataset.section,
        type: event.type,
        pointerType: event.pointerType || '',
        isPrimary: event.isPrimary === undefined ? '' : String(event.isPrimary),
        trusted: event.isTrusted,
        probe,
        x,
        y,
        dx: Math.round(x - (box.left + box.width / 2)),
        dy: Math.round(y - (box.top + box.height / 2)),
        t: Math.round(event.timeStamp),
    });

    const target = state.targets[state.mode][probe];
    if (target && event.type === 'pointerover' && target.firstDown === null) {
        target.lastOver = event.timeStamp;
    }
    if (target && event.type === 'pointerdown') {
        if (target.firstDown === null) {
            target.firstDown = event.timeStamp;
        }
        // النوع من pointerdown لا من click: في iOS قد يحمل click الناتج عن لمسٍ
        // النوع mouse (علّة WebKit 282988).
        target.pointerType = event.pointerType || target.pointerType;
    }
    if ((probe === 'rearm-a' || probe === 'rearm-b') && event.type === 'pointerout'
        && state.rearm.clickedA !== null) {
        // إخفاء الأول وإظهار الثاني في الخانة نفسها يُطلق pointerout من الأول
        // نحو الثاني دون أيّ حركة: لا يُحسب تحرّكاً إلا الخروج من الخانة.
        const cell = event.target.closest('.swap');
        const to = event.relatedTarget;
        if (!cell || !(to instanceof Node) || !cell.contains(to)) {
            state.rearm.outSinceA = true;
        }
    }
}

function countMove(event) {
    // pointerover وحده لا يُثبت مروراً: جهازٌ لا يمرّ يُطلقه قبل pointerdown مباشرة
    // (Pointer Events 3). الدليل على مؤشرٍ يمرّ حركاتُ pointermove قبل الضغط.
    const probe = probeOf(event);
    const target = probe ? state.targets[state.mode][probe] : null;
    if (target && target.firstDown === null) {
        target.movesBeforeDown += 1;
    }
    if (probe === 'rearm-a' || probe === 'rearm-b') {
        state.rearm.sawMove = true;
    }
}

function renderActivationLog() {
    const list = $('log-activation');
    list.replaceChildren();
    state.log.filter((row) => row.section === 'activation').slice(-6).forEach((row) => {
        const item = document.createElement('li');
        item.textContent = `${row.probe} ${row.type} ${row.pointerType} ${row.trusted ? 'trusted' : 'synthetic'} @${row.t}`;
        list.append(item);
    });
}

/* ── البيئة ─────────────────────────────────────────────────────────── */

function environment() {
    const media = (query) => (window.matchMedia(query).matches ? 'نعم' : 'لا');
    return [
        ['وضع الشاشة الرئيسية', media('(display-mode: standalone)') === 'نعم' || navigator.standalone === true ? 'نعم' : 'لا'],
        ['حجم النافذة', `${window.innerWidth}×${window.innerHeight}`],
        ['كثافة البكسل', String(window.devicePixelRatio)],
        ['مؤشر دقيق (pointer: fine)', media('(pointer: fine)')],
        ['مؤشر خشن (pointer: coarse)', media('(pointer: coarse)')],
        ['مرور (hover: hover)', media('(hover: hover)')],
        ['أي مرور (any-hover)', media('(any-hover: hover)')],
    ];
}

function renderEnvironment() {
    const list = $('env');
    list.replaceChildren();
    environment().forEach(([name, value]) => {
        const term = document.createElement('dt');
        term.textContent = name;
        const detail = document.createElement('dd');
        detail.textContent = value;
        list.append(term, detail);
    });
}

/* ── التنقّل ────────────────────────────────────────────────────────── */

function showSection(index) {
    const all = sections();
    state.section = Math.max(0, Math.min(all.length - 1, index));
    all.forEach((section, i) => { section.hidden = i !== state.section; });
    $('step-label').textContent = `${toArabic(state.section + 1)} من ${toArabic(all.length)}`;
    $('prev').disabled = state.section === 0;
    $('next').disabled = state.section === all.length - 1;
    if (['verdict', 'details'].includes(all[state.section].dataset.section)) {
        renderVerdict();
    }
    // التركيز على العنوان لا على زر: التركيز ليس تفعيلاً، لكنه يعلن القسم.
    $('heading').focus();
}

function navigate(event, delta) {
    // نقرتا تنقّل متتاليتان دون خروج المؤشر بينهما تعني إعادة ضغطٍ تلقائية:
    // تُسجَّل ملاحظةً، فهي بيانٌ عن سلوك النظام لا خطأ من المستخدم.
    state.navClicks.push({ t: event.timeStamp, delta, trusted: event.isTrusted });
    showSection(state.section + delta);
}

/* ── الأقسام ────────────────────────────────────────────────────────── */

function onTargetClick(event) {
    const probe = event.currentTarget.dataset.probe;
    const target = state.targets[state.mode][probe];
    if (event.isTrusted) {
        target.trustedClicks += 1;
    } else {
        target.syntheticClicks += 1;
    }
    if (target.firstClick === null) {
        target.firstClick = event.timeStamp;
    }
    event.currentTarget.dataset.clicked = '';
    renderActivationLog();
}

function onRearmA(event) {
    state.rearm.clickedA = event.timeStamp;
    state.rearm.outSinceA = false;
    state.rearm.result = null;
    $('rearm-a').hidden = true;
    $('rearm-b').hidden = false;
    $('rearm-result').textContent = 'ظهر الزر الثاني. أبقِ نظرك حيث هو.';
}

function onRearmB(event) {
    const delay = Math.round(event.timeStamp - state.rearm.clickedA);
    // الحركة تُعرف من خروج المؤشر من الخانة، وهذا لا يصحّ إلا لمؤشرٍ يمرّ. فإن لم
    // تصل الخانةَ حركةُ pointermove — لا أحداث حدودٍ أصلاً، أو أحداثٌ ترافق الضغطة
    // نفسها كما في اللمس — فالحركة غير معروفة، لا «لم يتحرّك». وأحداث الحدود
    // تغيّرت في Safari 26.2 و27.0، فيُجرى على الإصدارين.
    const moved = state.rearm.sawMove ? state.rearm.outSinceA : null;
    state.rearm.result = { delay, moved };
    const after = `ضُغط الثاني بعد ${toArabic(delay)} مللي ثانية`;
    if (moved === null) {
        $('rearm-result').textContent = `${after}. الحركة غير معروفة: لم تصل أحداث حركة المؤشر.`;
    } else {
        $('rearm-result').textContent = moved
            ? `${after}، بعد أن تحرّك النظر.`
            : `${after} دون أن يتحرّك النظر: النظام يعيد الضغط.`;
    }
}

function resetRearm() {
    state.rearm = { clickedA: null, outSinceA: false, sawMove: false, result: null };
    $('rearm-a').hidden = false;
    $('rearm-b').hidden = true;
    $('rearm-result').textContent = 'لم يُختبر بعد.';
}

function onStepper(event) {
    state.stepper.count += 1;
    state.stepper.times.push(event.timeStamp);
    $('stepper-value').textContent = toArabic(state.stepper.count);
}

function onStepperDone() {
    const times = state.stepper.times;
    const gaps = times.slice(1).map((t, i) => Math.round(t - times[i]));
    state.stepper.result = { count: state.stepper.count, gaps };
    $('stepper-result').textContent = state.stepper.count === 3
        ? 'ثلاث ضغطات بالضبط.'
        : `${toArabic(state.stepper.count)} ضغطات بدل ثلاث.`;
}

function resetStepper() {
    state.stepper = { count: 0, times: [], result: null };
    $('stepper-value').textContent = toArabic(0);
    $('stepper-result').textContent = 'لم يُختبر بعد.';
}

function buildScroller() {
    const scroller = $('scroller');
    for (let i = 1; i <= 10; i += 1) {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'btn';
        item.dataset.probe = `item-${i}`;
        item.textContent = `العنصر ${toArabic(i)}`;
        item.addEventListener('click', () => {
            state.scroll.result = i === 8 ? 'pass' : `pressed-${i}`;
            $('scroll-result').textContent = i === 8
                ? 'ضُغط العنصر ٨.'
                : `ضُغط العنصر ${toArabic(i)} بدل ٨.`;
        });
        scroller.append(item);
    }
    scroller.addEventListener('scroll', () => { state.scroll.scrolled = true; }, { passive: true });
}

function onFile(event) {
    const file = event.currentTarget.files[0];
    if (!file) {
        return;
    }
    // النوع والحجم فقط: الصورة لا تُقرأ ولا تُعرض.
    state.file = { type: file.type || '(بلا نوع)', kb: Math.round(file.size / 1024) };
    $('file-result').textContent = `النوع: ${state.file.type} · الحجم: ${toArabic(state.file.kb)} ك.ب`;
}

function onIosVersion(event) {
    // الأرقام العربية والفاصلة العشرية العربية كما تكتبها لوحة المفاتيح العربية.
    const text = event.currentTarget.value.trim()
        .replace(/[٠-٩]/g, (d) => String(DIGITS.indexOf(d)))
        .replace(/[٫,،]/g, '.');
    state.ios = IOS_VERSION.test(text) ? text : null;
    if (state.ios) {
        $('ios-result').textContent = `سُجّل الإصدار ${state.ios}.`;
    } else {
        $('ios-result').textContent = text
            ? 'لم يُفهم الإصدار. اكتبه كما يظهر في الإعدادات (مثل 27.0.1).'
            : 'لم يُكتب بعد (مثل 27.0.1).';
    }
}

function onTextDone(event) {
    const value = $('probe-text').value.trim();
    const seconds = state.text.focusedAt === null
        ? null
        : Math.round((event.timeStamp - state.text.focusedAt) / 1000);
    // لا يُحفظ النصّ نفسه: يكفي هل طابق، وكم استغرق.
    state.text.result = { matched: value === 'نعم', seconds };
    $('text-result').textContent = value === 'نعم'
        ? `كُتبت الكلمة في ${seconds === null ? '؟' : toArabic(seconds)} ثانية.`
        : 'لم تطابق الكلمة «نعم».';
}

async function onShare() {
    if (!navigator.share) {
        state.share = 'unsupported';
    } else {
        try {
            await navigator.share({ title: 'فحص الإدخال', text: 'اختبار المشاركة' });
            state.share = 'shared';
        } catch (error) {
            state.share = error && error.name ? error.name : 'error';
        }
    }
    renderVerdict();
}

/* ── النتيجة ────────────────────────────────────────────────────────── */

function median(values) {
    if (!values.length) {
        return null;
    }
    const sorted = [...values].sort((a, b) => a - b);
    return Math.round(sorted[Math.floor(sorted.length / 2)]);
}

function sizesOf(probes) {
    return probes.map((p) => toArabic(p.slice(1))).join('، ');
}

function checks() {
    const gaze = state.targets.gaze;
    const hit = TARGETS.filter((probe) => gaze[probe].trustedClicks > 0);
    const appHit = APP_TARGETS.filter((probe) => gaze[probe].trustedClicks > 0);
    const synthetic = TARGETS.some((probe) => gaze[probe].syntheticClicks > 0);
    const touched = TARGETS.filter((probe) => state.targets.touch[probe].trustedClicks > 0);
    const headHit = TARGETS.filter((probe) => state.targets.head[probe].trustedClicks > 0);
    const types = [...new Set(TARGETS.map((probe) => gaze[probe].pointerType).filter(Boolean))];

    // المرور والمكوث من الأهداف التي بلغها pointerdown بالنظر. الفاصل من آخر
    // pointerover قبله: قرابة الصفر لضغطةٍ كاللمس، وزمن المكوث لمؤشرٍ يمرّ.
    const pressed = TARGETS.map((probe) => gaze[probe]).filter((t) => t.firstDown !== null);
    const moves = pressed.reduce((sum, t) => sum + t.movesBeforeDown, 0);
    const hovered = pressed.some((t) => t.movesBeforeDown > 0);
    const gap = median(pressed.filter((t) => t.lastOver !== null).map((t) => t.firstDown - t.lastOver));

    // القرار من نقرات «بالنظر» على أحجام التطبيق وحدها.
    let activation = 'NOT_RUN';
    if (appHit.length === APP_TARGETS.length) {
        activation = 'PASS';
    } else if (hit.length > 0 || synthetic) {
        activation = 'FAIL';
    }

    // توصية حجم الهدف من الدقّة المقيسة بالنظر: ضعف المئين 95 من البُعد عن
    // المركز، مقرّباً إلى 8، ولا أقلّ من 72. القياس يرفع الحجم ولا يخفضه.
    // ومن نقراتٍ أعلن معها المختبِر «الانتقال إلى العنصر» مُعطَّلاً وحدها: أين
    // يضغط المكوث حين يُفعَّل غير موثّق، فإن ضغط مركز العنصر صار البُعد صفراً
    // ولم يدلّ على شيء.
    const offsets = state.log
        .filter((row) => row.section === 'activation' && row.type === 'click' && row.mode === 'gaze'
            && row.snap === 'off' && row.trusted && (row.x || row.y))
        .map((row) => Math.hypot(row.dx, row.dy))
        .sort((a, b) => a - b);
    const p95 = offsets.length ? offsets[Math.min(offsets.length - 1, Math.floor(offsets.length * 0.95))] : null;
    const recommended = p95 === null ? null : Math.max(72, Math.ceil((2 * p95) / 8) * 8);

    const quickNav = state.navClicks.slice(1).some(
        (click, i) => click.t - state.navClicks[i].t < 1500 && click.delta === state.navClicks[i].delta,
    );

    return [
        ['activation', 'الضغط بالنظر يصل الصفحة', activation,
            `${toArabic(appHit.length)} من ${toArabic(APP_TARGETS.length)} بحجم التطبيق`],
        ['sizes', 'الأحجام التي أُصيبت بالنظر', hit.length ? 'INFO' : 'NOT_RUN', sizesOf(hit) || '—'],
        ['head', 'الأحجام التي أُصيبت بالرأس', headHit.length ? 'INFO' : 'NOT_RUN', sizesOf(headHit) || '—'],
        ['touch', 'أهدافٌ أُصيبت باللمس (للمقارنة)', touched.length ? 'INFO' : 'NOT_RUN',
            touched.length ? toArabic(touched.length) : '—'],
        ['accuracy', 'حجم الهدف الموصى به', recommended === null ? 'NOT_RUN' : 'INFO',
            recommended === null
                ? 'لا يُحسب إلا مع «الانتقال إلى العنصر» مُعطَّلاً'
                : `${toArabic(recommended)} بكسل (البُعد عن المركز ${toArabic(Math.round(p95))})`],
        ['pointer', 'نوع المؤشر عند pointerdown', types.length ? 'INFO' : 'NOT_RUN', types.join('، ') || '—'],
        ['hover', 'مرورٌ قبل الضغط (pointermove)', pressed.length ? 'INFO' : 'NOT_RUN',
            pressed.length ? `${hovered ? 'نعم' : 'لا'} (pointermove: ${toArabic(moves)})` : '—'],
        ['gap', 'من دخول الهدف إلى الضغط', gap === null ? 'NOT_RUN' : 'INFO',
            gap === null ? '—' : `${toArabic(gap)} مللي ثانية`],
        ['rearm', 'يعيد النظام الضغط دون تحريك النظر', state.rearm.result ? 'INFO' : 'NOT_RUN',
            state.rearm.result ? rearmAnswer(state.rearm.result.moved) : '—'],
        ['nav', 'قفزةٌ مزدوجة في التنقّل', 'INFO', quickNav ? 'رُصدت' : 'لم تُرصد'],
        ['stepper', 'ثلاث ضغطات بالضبط', state.stepper.result
            ? (state.stepper.result.count === 3 ? 'PASS' : 'FAIL') : 'NOT_RUN',
            state.stepper.result ? toArabic(state.stepper.result.count) : '—'],
        ['scroll', 'التمرير ثم الضغط', state.scroll.result
            ? (state.scroll.result === 'pass' ? 'PASS' : 'FAIL') : 'NOT_RUN',
            state.scroll.scrolled ? 'مُرِّرت القائمة' : 'لم تُمرَّر'],
        ['file', 'اختيار صورة بنوعٍ مقبول', state.file
            ? (ACCEPTED.includes(state.file.type) ? 'PASS' : 'FAIL') : 'NOT_RUN',
            state.file ? state.file.type : '—'],
        ['check', 'مربّع الاختيار', state.check === null ? 'NOT_RUN' : 'PASS', state.check ? 'عُلِّم' : '—'],
        ['dialog', 'فتح النافذة وإغلاقها', state.dialog.opened
            ? (state.dialog.closed ? 'PASS' : 'FAIL') : 'NOT_RUN', ''],
        ['typing', 'الكتابة', state.text.result
            ? (state.text.result.matched ? 'PASS' : 'FAIL') : 'NOT_RUN',
            state.text.result && state.text.result.seconds !== null
                ? `${toArabic(state.text.result.seconds)} ثانية` : '—'],
        ['share', 'المشاركة', state.share === null ? 'NOT_RUN'
            : (state.share === 'shared' ? 'PASS' : 'INFO'), state.share || '—'],
        ['standalone', 'وضع الشاشة الرئيسية', 'INFO', environment()[0][1]],
    ];
}

function rearmAnswer(moved) {
    if (moved === null) {
        return 'الحركة غير معروفة';
    }
    return moved ? 'لا' : 'نعم';
}

const LABELS = { PASS: 'نجح', FAIL: 'لم ينجح', INFO: 'ملاحظة', NOT_RUN: 'لم يُختبر' };

// الفحوص التي تحكم القرار تُعرض مع النتيجة؛ والملاحظات في القسم التالي، فلا
// يحتاج أيّ قسمٍ إلى تمرير.
const CORE = ['activation', 'rearm', 'stepper', 'scroll', 'file', 'typing', 'share'];

function fillTable(body, rows) {
    body.replaceChildren();
    rows.forEach(([, name, status, detail]) => {
        const row = document.createElement('tr');
        const label = document.createElement('td');
        label.textContent = name;
        const value = document.createElement('td');
        value.textContent = detail && detail !== '—' ? `${LABELS[status]} — ${detail}` : LABELS[status];
        row.append(label, value);
        body.append(row);
    });
}

function renderVerdict() {
    const rows = checks();
    fillTable($('checks-core'), rows.filter(([key]) => CORE.includes(key)));
    fillTable($('checks-detail'), rows.filter(([key]) => !CORE.includes(key)));

    const activation = rows[0][2];
    const verdict = $('verdict');
    if (activation === 'PASS') {
        verdict.dataset.state = 'pass';
        verdict.textContent = 'يصل الضغط بالنظر إلى أهداف التطبيق في هذا الوضع.';
    } else if (activation === 'FAIL') {
        verdict.dataset.state = 'fail';
        verdict.textContent = 'لم يصل الضغط بالنظر إلى أهداف التطبيق (٧٢ فأكبر). لا يُبنى على الويب قبل حلّ هذا.';
    } else {
        const at = sections().findIndex((section) => section.dataset.section === 'activation') + 1;
        verdict.dataset.state = '';
        verdict.textContent = `لم يُختبر الضغط بالنظر بعد (القسم ${toArabic(at)}، بطريقة «بالنظر»).`;
    }
}

function summary() {
    const rows = checks();
    const lines = ['فحص الإدخال — النتيجة', 'الحكم من نقرات «بالنظر» وحدها؛ نقرات «بالرأس» و«باللمس» تُعدّ وحدها.'];
    lines.push(
        `إصدار iOS (كتبه المختبِر): ${state.ios || 'لم يُكتب'}`,
        `الانتقال إلى العنصر (Snap to Item): ${state.snap ? SNAP[state.snap] : 'لم يُحدَّد'}`,
    );
    environment().forEach(([name, value]) => lines.push(`${name}: ${value}`));
    lines.push(`نقاط اللمس: ${navigator.maxTouchPoints}`, `المتصفّح: ${navigator.userAgent}`);
    lines.push('');
    rows.forEach(([key, name, status, detail]) => lines.push(`${key} · ${name}: ${status}${detail ? ` (${detail})` : ''}`));
    lines.push('', 'آخر الأحداث:');
    state.log.slice(-50).forEach((row) => lines.push(
        `${row.mode}/snap-${row.snap || '?'} ${row.section} ${row.probe} ${row.type} ${row.pointerType} ${row.trusted ? 'T' : 'S'} ${row.x},${row.y} Δ${row.dx},${row.dy} @${row.t}`,
    ));
    return lines.join('\n');
}

async function onCopy() {
    const button = $('copy');
    try {
        await navigator.clipboard.writeText(summary());
        button.textContent = 'نُسخت النتيجة';
    } catch (error) {
        button.textContent = 'تعذّر النسخ';
    }
}

/* ── الإقلاع ────────────────────────────────────────────────────────── */

function init() {
    MODES.forEach((mode) => TARGETS.forEach((probe) => {
        state.targets[mode][probe] = {
            lastOver: null, firstDown: null, movesBeforeDown: 0,
            firstClick: null, trustedClicks: 0, syntheticClicks: 0, pointerType: '',
        };
    }));

    LOGGED.forEach((type) => document.addEventListener(type, record, { capture: true, passive: true }));
    document.addEventListener('pointermove', countMove, { capture: true, passive: true });

    document.querySelectorAll('[data-mode]').forEach((button) => {
        button.addEventListener('click', () => {
            state.mode = button.dataset.mode;
            document.querySelectorAll('[data-mode]').forEach((other) => {
                other.setAttribute('aria-pressed', String(other === button));
            });
        });
    });
    document.querySelectorAll('[data-snap]').forEach((button) => {
        button.addEventListener('click', () => {
            state.snap = button.dataset.snap;
            document.querySelectorAll('[data-snap]').forEach((other) => {
                other.setAttribute('aria-pressed', String(other === button));
            });
        });
    });
    $('probe-ios').addEventListener('change', onIosVersion);

    document.querySelectorAll('.target').forEach((button) => button.addEventListener('click', onTargetClick));
    $('rearm-a').addEventListener('click', onRearmA);
    $('rearm-b').addEventListener('click', onRearmB);
    $('rearm-reset').addEventListener('click', resetRearm);
    $('stepper-plus').addEventListener('click', onStepper);
    $('stepper-done').addEventListener('click', onStepperDone);
    $('stepper-reset').addEventListener('click', resetStepper);
    buildScroller();
    $('probe-file').addEventListener('change', onFile);
    $('probe-check').addEventListener('change', (event) => { state.check = event.currentTarget.checked; });
    $('dialog-open').addEventListener('click', () => { $('probe-dialog').showModal(); state.dialog.opened = true; });
    $('dialog-close').addEventListener('click', () => { $('probe-dialog').close(); state.dialog.closed = true; });
    $('probe-text').addEventListener('focus', (event) => {
        if (state.text.focusedAt === null) {
            state.text.focusedAt = event.timeStamp;
        }
    });
    $('text-done').addEventListener('click', onTextDone);
    $('share').addEventListener('click', onShare);
    $('copy').addEventListener('click', onCopy);
    $('next').addEventListener('click', (event) => navigate(event, 1));
    $('prev').addEventListener('click', (event) => navigate(event, -1));

    renderEnvironment();
    showSection(0);
}

init();
