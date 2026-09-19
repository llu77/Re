/*
 * بوابة المريض — المنطق
 * ======================
 * لا إطار ولا خطوة بناء: الملف يُقرأ كما هو، وهذا مقصود في واجهة تحمل
 * ضمانات سريرية ويجب أن تبقى قابلة للتدقيق بالعين.
 *
 * ثلاث قواعد تحكم هذا الملف:
 *   1. كل محتوى سريري يأتي من `/patient/*` — أي من نقطة العبور في القسم 1.
 *      لا يبني هذا الملف محتوى سريرياً ولا يستنتجه.
 *   2. لا محادثة طبية ولا إجابة عن «هل هذا طبيعي؟». ردّ البلاغ نصّ يأتي من
 *      الخادم ثابتاً.
 *   3. العمل دون اتصال بلا تكرار ولا فقد: لكل تسجيلة `client_uuid` يُولَّد
 *      مرة واحدة ويُخزَّن معها، فإعادة الإرسال تُعيد الصف نفسه لا نسخة منه.
 */

'use strict';

const TOKEN_KEY = 'symbol.patient.token';
const PLAN_KEY = 'symbol.patient.plan';
const IMAGES_KEY = 'symbol.patient.illustrations';
const DB_NAME = 'symbol-portal';
const QUEUE_STORE = 'pending-sessions';

const $ = (id) => document.getElementById(id);

const state = {
    plan: null,
    steps: [],
    index: 0,
    // خريطة: اسم التمرين ← ترميم الرسم المعتمد. لا يدخلها إلا ما جاء من
    // مجموعة صور معتمدة اجتازت التحقق الآلي من الجانب المصاب.
    illustrations: {},
};

/* ── التخزين المحلي ─────────────────────────────────────────────────── */

function openDb() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, 1);
        request.onupgradeneeded = () => {
            request.result.createObjectStore(QUEUE_STORE, { keyPath: 'client_uuid' });
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function queueWrite(item) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(QUEUE_STORE, 'readwrite');
        // keyPath هو client_uuid، فإعادة وضع العنصر نفسه تستبدله ولا تُضيفه
        tx.objectStore(QUEUE_STORE).put(item);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
    });
}

async function queueRead() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const request = db.transaction(QUEUE_STORE).objectStore(QUEUE_STORE).getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function queueDrop(clientUuid) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(QUEUE_STORE, 'readwrite');
        tx.objectStore(QUEUE_STORE).delete(clientUuid);
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
    });
}

/* ── الشبكة ─────────────────────────────────────────────────────────── */

function token() {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

function setToken(value) {
    try { localStorage.setItem(TOKEN_KEY, value); } catch { /* تخزين معطّل */ }
}

/**
 * ينهي الجلسة على هذا الجهاز.
 *
 * الخطة المحفوظة تُمحى معها: هي محتوى سريري، والجهاز قد يكون مشتركاً مع
 * مرافق أو بين مريضين. أما طابور الإرسال فيبقى — فيه تسجيلات لم تصل بعد
 * وإسقاطها فقدُ بيانات، ولا خطر في بقائها: كل تسجيلة مربوطة بخطة، وقاعدة
 * البيانات ترفض خطةً لا تخص صاحب الجلسة، فلا تُكتب تسجيلة مريض في سجل آخر.
 */
function forgetSession() {
    try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(PLAN_KEY);
        localStorage.removeItem(IMAGES_KEY);
    } catch { /* تخزين معطّل */ }
    state.plan = null;
    state.steps = [];
    state.index = 0;
    state.illustrations = {};
    $('acting-as').hidden = true;
}

async function api(path, options = {}) {
    const response = await fetch(`/patient${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token() || ''}`,
            ...(options.headers || {}),
        },
    });
    // رمز منتهٍ أو مُبطَل: تُنسى الجلسة هنا فوراً ويُعاد المريض إلى الدخول
    if (response.status === 401) {
        forgetSession();
        showSignedIn(false);
        throw new Error('unauthenticated');
    }
    if (!response.ok) throw new Error(`http ${response.status}`);
    return response.status === 204 ? null : response.json();
}

function say(message) {
    const status = $('status');
    status.textContent = message || '';
    status.hidden = !message;
}

/* ── خطة اليوم ──────────────────────────────────────────────────────── */

function cachePlan(plan) {
    try { localStorage.setItem(PLAN_KEY, JSON.stringify(plan)); } catch { /* حصة ممتلئة */ }
}

function cachedPlan() {
    try { return JSON.parse(localStorage.getItem(PLAN_KEY) || 'null'); } catch { return null; }
}

function cacheImages(images) {
    try { localStorage.setItem(IMAGES_KEY, JSON.stringify(images)); } catch { /* حصة ممتلئة */ }
}

function cachedImages() {
    try { return JSON.parse(localStorage.getItem(IMAGES_KEY) || '{}'); } catch { return {}; }
}

/**
 * يجلب مجموعة الصور المعتمدة ويحوّلها إلى خريطة باسم التمرين.
 *
 * الجانب يُطابَق مع جانب الخطة: مجموعة لجانب آخر لا تُعرض ولو كانت معتمدة.
 * ذلك يحدث عند تحديث الخطة وحدها، والصورة القديمة حينها تخصّ حالة أخرى.
 */
async function loadIllustrations(plan) {
    try {
        const set = await api('/content/ILLUSTRATION_SET');
        const images = {};
        if (set && plan && set.affected_side === plan.affected_side) {
            for (const item of (set.content.illustrations || [])) {
                if (item && item.exercise_type && item.svg) images[item.exercise_type] = item.svg;
            }
        }
        cacheImages(images);
        return images;
    } catch {
        return cachedImages();   // دون اتصال: آخر مجموعة معتمدة محفوظة
    }
}

/** يحوّل الخطة المعتمدة إلى خطوات. لا يخترع خطوة غير موجودة فيها. */
function stepsOf(plan) {
    if (!plan || !plan.content) return [];
    const content = plan.content;
    if (Array.isArray(content.steps) && content.steps.length) return content.steps;
    if (content.home_program) return [{ title: 'برنامجك المنزلي', text: content.home_program }];
    return [];
}

function renderStep() {
    const card = $('step-card');
    const step = state.steps[state.index];
    if (!step) { card.hidden = true; return; }

    card.hidden = false;
    $('step-counter').textContent = `الخطوة ${state.index + 1} من ${state.steps.length}`;
    $('step-title').textContent = step.title || `الخطوة ${state.index + 1}`;
    $('step-text').textContent = step.text || '';

    // الصورة المعتمدة فقط، وجانبها المصاب معلَّم نصاً لا لوناً.
    //
    // `step.illustration` اسم تمرين لا ترميم: قاعدة البيانات تمنع وجود أي
    // SVG في حمولة خطة، فالصورة الوحيدة الممكنة هنا هي ما جاء من مجموعة
    // معتمدة اجتازت التحقق. خطةٌ تحمل رسماً بنفسها لا توجد أصلاً.
    const figure = $('step-figure');
    const side = state.plan && state.plan.affected_side;
    const markup = state.illustrations[step.illustration];
    if (markup && side && drawIllustration($('step-image'), markup)) {
        $('step-side').textContent = `الجانب المصاب: ${sideLabel(side)}`;
        figure.hidden = false;
    } else {
        figure.hidden = true;
    }

    $('prev').disabled = state.index === 0;
    $('next').disabled = state.index >= state.steps.length - 1;
}

/**
 * يرسم رسماً معتمداً، أو لا يرسم شيئاً.
 *
 * الخادم لا يسلّم إلا رسماً اجتاز فحص القائمة البيضاء في
 * `core/illustrations.py`، والمحفّز في قاعدة البيانات يمنع غير ذلك. وهذا
 * الفحص الثاني هنا دفاعٌ في العمق لا تكرار: لو سُلّم يوماً ما لم يُفحص —
 * بخلل أو باختراق — فلن ينفّذ شيئاً على جهاز المريض.
 *
 * `textContent` كان يعرض ترميم الـSVG نصاً خاماً: آمن، وبلا صورة.
 */
function drawIllustration(container, markup) {
    container.replaceChildren();
    let document_;
    try {
        document_ = new DOMParser().parseFromString(markup, 'image/svg+xml');
    } catch {
        return false;
    }

    const root = document_.documentElement;
    if (!root || root.nodeName.toLowerCase() !== 'svg') return false;
    if (document_.querySelector('parsererror')) return false;

    for (const element of [root, ...root.querySelectorAll('*')]) {
        const name = element.nodeName.toLowerCase();
        if (name === 'script' || name === 'foreignobject' || name === 'image') return false;
        for (const attribute of element.getAttributeNames()) {
            const lowered = attribute.toLowerCase();
            if (lowered.startsWith('on') || lowered.endsWith('href')) return false;
        }
    }

    container.appendChild(document_.importNode(root, true));
    return true;
}

function sideLabel(side) {
    return { LEFT: 'الأيسر', RIGHT: 'الأيمن', BILATERAL: 'كلا الجانبين' }[side] || side;
}

async function loadPlan() {
    let plan = null;
    try {
        plan = await api('/plan');
        if (plan) cachePlan(plan);
    } catch (error) {
        if (error.message === 'unauthenticated') { say('سجّل الدخول لعرض خطتك.'); return; }
        // دون اتصال: آخر خطة معتمدة تبقى قابلة للقراءة
        plan = cachedPlan();
        if (plan) say('تُعرض آخر خطة محفوظة على جهازك.');
    }

    state.plan = plan;
    state.steps = stepsOf(plan);
    state.index = 0;
    state.illustrations = plan ? await loadIllustrations(plan) : {};

    const hasPlan = state.steps.length > 0;
    $('plan-empty').hidden = hasPlan;
    $('record').hidden = !hasPlan;
    renderStep();
}

/* ── تسجيل الجلسة ───────────────────────────────────────────────────── */

async function recordOutcome(outcome) {
    if (!state.plan) return;

    const item = {
        client_uuid: crypto.randomUUID(),
        plan_id: state.plan.id,
        outcome,
        occurred_at: new Date().toISOString(),
        difficulty: Number($('difficulty').value),
        pain: Number($('pain').value),
        reason: $('reason').value.trim() || null,
    };

    // نُخزّن أولاً ثم نُرسل: انقطاع بين الاثنين يفقد التسجيلة لو عكسنا الترتيب
    await queueWrite(item);
    const sent = await flushQueue();

    const done = $('record-done');
    done.textContent = sent
        ? 'سُجِّلت اليوم. شكراً لك.'
        : 'سُجِّلت على جهازك وستُرسَل عند عودة الاتصال.';
    done.hidden = false;
}

/** يرسل ما في الطابور. آمن للتكرار: الخادم يُرجع نفس الصف لنفس المعرّف. */
async function flushQueue() {
    const pending = await queueRead();
    if (!pending.length) return true;

    let allSent = true;
    for (const item of pending) {
        try {
            await api('/sessions', { method: 'POST', body: JSON.stringify(item) });
            await queueDrop(item.client_uuid);
        } catch (error) {
            if (error.message === 'unauthenticated') { allSent = false; break; }
            // 409 يعني خطة لم تعد قابلة للتسجيل — نُسقطها بدل إعادة محاولة أبدية
            if (/http 4\d\d/.test(error.message)) { await queueDrop(item.client_uuid); continue; }
            allSent = false;
        }
    }
    return allSent;
}

/* ── تقدّمي ─────────────────────────────────────────────────────────── */

async function loadProgress() {
    let data;
    try {
        data = await api('/progress?days=14');
    } catch {
        say('تعذّر تحميل تقدّمك الآن.');
        return;
    }

    $('progress-lead').textContent = data.done_today
        ? `سجّلت اليوم. ${data.adherent_days} يوماً من آخر ${data.total_days}.`
        : `لم تسجّل اليوم بعد. ${data.adherent_days} يوماً من آخر ${data.total_days}.`;

    const calendar = $('calendar');
    const rows = $('progress-rows');
    calendar.innerHTML = '';
    rows.innerHTML = '';

    for (const day of data.days) {
        const cell = document.createElement('li');
        cell.dataset.recorded = String(day.sessions > 0);
        calendar.appendChild(cell);

        // نصّ مكافئ لكل مربع: المعلومة متاحة لقارئ الشاشة لا للعين وحدها
        const row = document.createElement('tr');
        const dayCell = document.createElement('th');
        dayCell.scope = 'row';
        dayCell.textContent = day.day;
        const valueCell = document.createElement('td');
        valueCell.textContent = day.sessions > 0 ? `${day.sessions} جلسة` : 'لم تُسجَّل جلسة';
        row.append(dayCell, valueCell);
        rows.appendChild(row);
    }
}

/* ── البلاغ ─────────────────────────────────────────────────────────── */

async function sendAlarm() {
    const body = $('alarm-body').value.trim();
    if (!body) return;

    const ack = $('alarm-ack');
    try {
        const result = await api('/red-flag', {
            method: 'POST', body: JSON.stringify({ body }),
        });
        // النص يأتي من الخادم ثابتاً. لا تقييم هنا ولا طمأنة ولا نصيحة.
        ack.textContent = result.acknowledgement;
    } catch {
        ack.textContent = 'تعذّر الإرسال الآن. إن كانت حالتك طارئة فاتصل بالإسعاف فوراً.';
    }
    ack.hidden = false;
    $('alarm-body').value = '';
}

/* ── النطق ──────────────────────────────────────────────────────────── */

function speakStep() {
    if (!('speechSynthesis' in window)) return;
    const step = state.steps[state.index];
    if (!step) return;

    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(
        `${step.title || ''}. ${step.text || ''}`
    );
    utterance.lang = 'ar-SA';
    utterance.rate = 0.9;
    speechSynthesis.speak(utterance);
}

function wireDictation() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) return;              // تحسين تدريجي: غيابه لا يعطّل شيئاً

    const button = $('dictate');
    button.hidden = false;
    button.addEventListener('click', () => {
        const recognition = new Recognition();
        recognition.lang = 'ar-SA';
        recognition.onresult = (event) => {
            $('reason').value = event.results[0][0].transcript;
        };
        recognition.start();
    });
}

/* ── الدخول والخروج ─────────────────────────────────────────────────── */

/** يُظهر شاشة واحدة: إما الدخول وإما البوابة. لا حالة بينهما. */
function showSignedIn(signedIn) {
    $('view-login').hidden = signedIn;
    $('logout').hidden = !signedIn;
    document.querySelector('.tabs').hidden = !signedIn;
    // زر البلاغ يحتاج جلسة: إظهاره قبل الدخول يَعِد بما لا يستطيع
    document.querySelector('.alarm').hidden = !signedIn;

    if (signedIn) {
        showView('plan');
    } else {
        $('view-plan').hidden = true;
        $('view-progress').hidden = true;
        say('');
    }
}

async function openSession() {
    await showActingAs();
    await loadPlan();
    if (navigator.onLine) flushQueue();
}

/** يُظهر الصفة للمرافق. صامت للمريض نفسه: لا داعي لإخباره أنه هو. */
async function showActingAs() {
    const banner = $('acting-as');
    try {
        const who = await api('/session');
        const isCaregiver = who.acting_as === 'CAREGIVER';
        banner.textContent = isCaregiver
            ? 'أنت تستخدم البوابة بصفة مرافق. ما تسجّله يُنسب إليك ويظهر للممارس.'
            : '';
        banner.hidden = !isCaregiver;
    } catch {
        // دون اتصال أو بجلسة منتهية: لا نعرض صفة قد تكون خاطئة
        banner.hidden = true;
    }
}

async function doLogin(event) {
    event.preventDefault();

    const error = $('login-error');
    const submit = $('login-submit');
    error.hidden = true;
    submit.disabled = true;

    try {
        const response = await fetch('/patient/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: $('login-email').value.trim(),
                password: $('login-password').value,
            }),
        });

        // لا تفصيل بين «بريد غير موجود» و«كلمة مرور خاطئة»: الفرق يكشف الحسابات
        if (response.status === 429) {
            throw new Error('محاولات كثيرة. انتظر دقيقة ثم أعد المحاولة.');
        }
        if (!response.ok) throw new Error('البريد أو كلمة المرور غير صحيحة.');

        setToken((await response.json()).token);
        $('login-password').value = '';
        showSignedIn(true);
        await openSession();
    } catch (failure) {
        error.textContent = failure instanceof TypeError
            ? 'لا يوجد اتصال. تعذّر تسجيل الدخول.'
            : failure.message;
        error.hidden = false;
    } finally {
        submit.disabled = false;
    }
}

async function doLogout() {
    // إبطال الرمز على الخادم أولاً، ثم نسيانه هنا مهما كانت نتيجة الطلب
    try { await api('/logout', { method: 'POST' }); } catch { /* رمز منتهٍ */ }
    forgetSession();
    showSignedIn(false);
}

/* ── التبويبات ──────────────────────────────────────────────────────── */

function showView(name) {
    for (const tab of document.querySelectorAll('.tab')) {
        const active = tab.dataset.view === name;
        if (active) tab.setAttribute('aria-current', 'page');
        else tab.removeAttribute('aria-current');
    }
    $('view-plan').hidden = name !== 'plan';
    $('view-progress').hidden = name !== 'progress';
    if (name === 'progress') loadProgress();
}

/* ── الإقلاع ────────────────────────────────────────────────────────── */

function showConnectivity() {
    $('offline').hidden = navigator.onLine;
}

function wire() {
    $('today-label').textContent = new Intl.DateTimeFormat('ar', {
        weekday: 'long', day: 'numeric', month: 'long',
        timeZone: 'Asia/Riyadh',
    }).format(new Date());

    for (const tab of document.querySelectorAll('.tab')) {
        tab.addEventListener('click', () => showView(tab.dataset.view));
    }

    $('prev').addEventListener('click', () => { state.index--; renderStep(); });
    $('next').addEventListener('click', () => { state.index++; renderStep(); });
    $('speak').addEventListener('click', speakStep);

    for (const button of document.querySelectorAll('[data-outcome]')) {
        button.addEventListener('click', () => recordOutcome(button.dataset.outcome));
    }

    for (const [input, output] of [['difficulty', 'difficulty-out'], ['pain', 'pain-out']]) {
        $(input).addEventListener('input', () => { $(output).textContent = $(input).value; });
    }

    $('alarm').addEventListener('click', () => {
        $('alarm-ack').hidden = true;
        $('alarm-sheet').showModal();
    });
    $('login-form').addEventListener('submit', doLogin);
    $('logout').addEventListener('click', doLogout);

    $('alarm-send').addEventListener('click', sendAlarm);
    $('alarm-cancel').addEventListener('click', () => $('alarm-sheet').close());

    window.addEventListener('online', () => { showConnectivity(); flushQueue(); });
    window.addEventListener('offline', showConnectivity);

    wireDictation();
    showConnectivity();
}

async function start() {
    wire();

    if (token()) {
        showSignedIn(true);
        await openSession();
    } else {
        showSignedIn(false);
    }

    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('sw.js').catch(() => { /* لا يعطّل شيئاً */ });
    }
}

document.addEventListener('DOMContentLoaded', start);
