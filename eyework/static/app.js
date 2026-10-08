/*
 * صياغة — منطق الواجهة
 * ====================
 * لا إطار ولا خطوة بناء: الملف يُقرأ كما هو.
 *
 * ثلاث قواعد تحكم هذا الملف:
 *   1. الخادم مصدر كل قيمة: الحدود والخيارات والكلمات تأتي من /api/choices
 *      ومن الحملة نفسها. لا يُحسب هنا مبلغٌ ولا كلمة.
 *   2. كل كتابةٍ تحمل `expected_row_version` وقيمةً مطلقة: الضغطة المكرّرة
 *      بالنظر إمّا تضع القيمة نفسها أو تُرفض بـ409 — لا تُطبَّق مرتين.
 *   3. موضعٌ واحد يتصل بالشبكة: `api()`.
 */

'use strict';

const $ = (id) => document.getElementById(id);

const STATUS_LABELS = {
    DRAFT: 'مسودة',
    COPY_PROPOSED: 'نصٌّ بانتظار موافقتك',
    COPY_APPROVED: 'نصٌّ موافَقٌ عليه',
    READY: 'جاهزة للتسليم',
};

const PRESET_LABELS = {
    SHORTER: 'أقصر',
    SIMPLER: 'لغة أبسط',
    MORE_FORMAL: 'أكثر رسمية',
    MORE_LIVELY: 'أكثر حيوية',
    NEW_TITLE: 'عنوانٌ آخر فقط',
    NEW_DESCRIPTION: 'وصفٌ آخر فقط',
};

const WARNING_LABELS = { PRICE: 'سعر', HEALTH_CLAIM: 'ادّعاءٌ صحي', SUPERLATIVE: 'مبالغة' };

const OFFLINE = 'تعذّر الاتصال. تحقّق من الشبكة وحاول مرة أخرى.';
const GENERIC = 'حدث خطأ. حاول مرة أخرى.';

const state = {
    choices: null,
    campaign: null,
    page: 1,
    // طلب التعديل قيد الإعداد، مربوطٌ بالنسخة التي يُبنى عليها.
    edit: { versionId: null, presets: new Set(), note: null, draft: '', armed: false },
    activation: null,
    busy: false,
    waitingFor: null,
    readyBlob: null,
    // الاسم الذي يناديه به المساعد، من /api/me. لا يُرسل إلى النموذج.
    displayName: null,
    // التسجيل الجاري (portal.js): الرمز وما اختير خطوةً خطوة، في الذاكرة وحدها.
    signup: null,
    // بوابة مهنة صاحب الحساب من /api/portal: اسمها، وأداتها، ومهامّها، ومهاراتها.
    portal: null,
    // يزيد مع كل انتقال: ردٌّ وصل بعد انتقالٍ أحدث لا يرسم شاشةً ولا يغيّر حملة.
    nav: 0,
    // النسخة التي عُرضت ملاحظتها وحدها لأن الشاشة لم تتّسع لها مع النصّ.
    noteShownFor: null,
};

/* ── الشبكة: موضعٌ واحد ─────────────────────────────────────────────── */

async function api(method, path, { json, raw, type, as = 'json' } = {}) {
    const headers = { 'X-Eyework': '1' };
    let body;
    if (json !== undefined) {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(json);
    } else if (raw !== undefined) {
        headers['Content-Type'] = type;
        body = raw;
    }
    let response;
    try {
        response = await fetch(path, { method, headers, body, credentials: 'same-origin', cache: 'no-store' });
    } catch (error) {
        return { status: 0, data: { detail: OFFLINE } };
    }
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
        state.campaign = null;
        go('#/login');
        return { status: 401, data: null };
    }
    let data = null;
    if (response.status !== 204) {
        try {
            data = as === 'blob' && response.ok ? await response.blob() : await response.json();
        } catch (error) {
            data = null;
        }
    }
    // المهنة تغيّرت عند الخادم: البوابة المحفوظة لم تعد صحيحة.
    if (response.status === 403 && data && data.code === 'PROFESSION') {
        state.portal = null;
    }
    return { status: response.status, data };
}

function detail(result) {
    return (result.data && result.data.detail) || GENERIC;
}

/* ── التنقّل ────────────────────────────────────────────────────────── */

function go(hash, { replace = false } = {}) {
    if (replace) {
        history.replaceState(null, '', hash);
        route();
    } else if (location.hash === hash) {
        route();
    } else {
        location.hash = hash;
    }
}

function campaignRoute(campaign) {
    return `#/c/${campaign.id}`;
}

// الأب المنطقي لكل شاشة: «رجوع» يذهب إليه دائماً، لا إلى تاريخ المتصفّح.
function parentOf(name) {
    if (name.startsWith('signup-')) {
        return signupParent(name);
    }
    const id = state.campaign && state.campaign.id;
    return {
        account: '#/',
        'portal-item': '#/',
        photo: '#/',
        proposal: '#/',
        ready: '#/',
        edit: id ? `#/c/${id}` : '#/',
        note: id ? `#/c/${id}/edit` : '#/',
        budget: id ? `#/c/${id}` : '#/',
        days: id ? `#/c/${id}/budget` : '#/',
        review: id ? `#/c/${id}/days` : '#/',
    }[name] || '#/';
}

/* الحملة كما هي الآن في الخادم، بلا أثرٍ في الحالة: من طلبها يقرّر إن كان ما زال له. */
async function fetchCampaign(id) {
    const result = await api('GET', `/api/campaigns/${id}`);
    return result.status === 200 ? result.data : null;
}

async function loadCampaign(id) {
    if (state.campaign && state.campaign.id === id) {
        return state.campaign;
    }
    const campaign = await fetchCampaign(id);
    if (campaign) {
        state.campaign = campaign;
    }
    return campaign;
}

async function route() {
    // رابط تسجيلٍ أو تفعيلٍ فُتح في تبويبٍ فيه التطبيق: لا تحميل، بل hashchange وحده.
    captureActivation();
    captureSignup();
    const nav = ++state.nav;
    // لا شاشة بلا خياراتها: إقلاعٌ فشل ثم دخولٌ ناجح يقرأها هنا قبل أيّ رسم.
    if (!state.choices && !(await loadChoices())) {
        return;
    }
    if (nav !== state.nav) {
        return;
    }
    const hash = location.hash || '#/';
    if (hash.startsWith('#/login')) {
        renderLogin();
        return;
    }
    if (hash.startsWith('#/activate')) {
        renderActivate();
        return;
    }
    if (await routePortal(hash, nav)) {
        return;
    }
    if (hash === '#/' || hash === '#') {
        await renderHome();
        return;
    }
    // الحملة أداة بوابة التسويق وحدها: البوابات الأخرى لا تصل مساراتها.
    const portal = await loadPortal();
    if (nav !== state.nav) {
        return;
    }
    if (!portal || !portal.tools.includes('CAMPAIGN')) {
        go('#/', { replace: true });
        return;
    }
    if (hash === '#/new') {
        state.campaign = null;
        renderPhoto();
        return;
    }
    const match = hash.match(/^#\/c\/([0-9a-f-]{36})(?:\/(edit|note|budget|days|review))?$/);
    if (!match) {
        go('#/', { replace: true });
        return;
    }
    const id = match[1];
    const campaign = state.campaign && state.campaign.id === id ? state.campaign : await fetchCampaign(id);
    // انتقالٌ أحدث (رجوعٌ أو «حملة جديدة») وقع أثناء القراءة: الشاشة له، والحملة
    // التي طُلبت لا تصير الحالية — وإلا ذهبت صورةٌ جديدة إلى مسودةٍ أخرى.
    if (nav !== state.nav) {
        return;
    }
    if (!campaign) {
        go('#/', { replace: true });
        return;
    }
    state.campaign = campaign;
    const sub = match[2];
    const status = campaign.status;
    if (status === 'CANCELLED') {
        go('#/', { replace: true });
    } else if (status === 'READY') {
        renderReady();
    } else if (campaign.generating && state.waitingFor !== campaign.id) {
        renderWaiting({ reloaded: true });
    } else if (state.waitingFor === campaign.id) {
        renderWaiting({ reloaded: false });
    } else if (status === 'DRAFT') {
        renderPhoto();
    } else if (sub === 'edit' && status === 'COPY_PROPOSED') {
        renderEdit();
    } else if (sub === 'note' && status === 'COPY_PROPOSED') {
        renderNote();
    } else if (sub === 'budget' && status === 'COPY_APPROVED') {
        renderBudget();
    } else if (sub === 'days' && status === 'COPY_APPROVED' && campaign.budget) {
        renderDays();
    } else if (sub === 'review' && status === 'COPY_APPROVED' && campaign.budget && campaign.days) {
        renderReview();
    } else if (sub) {
        go(campaignRoute(campaign), { replace: true });
    } else {
        renderProposal();
    }
}

/* ── الدخول والتفعيل ────────────────────────────────────────────────── */

function renderLogin() {
    UI.show('login');
}

async function onLogin(event) {
    event.preventDefault();
    const section = UI.screen('login');
    if (state.busy) {
        return;
    }
    state.busy = true;
    const result = await api('POST', '/api/auth/login', {
        json: { username: $('login-username').value, password: $('login-password').value },
    });
    state.busy = false;
    if (result.status === 204) {
        $('login-password').value = '';
        // انتقالٌ كامل: لا يبقى في الذاكرة شيءٌ لحسابٍ سابق (الاسم والصفحة)،
        // ويعرض Safari حفظ كلمة المرور.
        location.replace('/');
    } else {
        UI.showAlert(section, detail(result));
    }
}

// رابط الدعوة يُقرأ إلى الذاكرة ويُمحى من شريط العنوان فوراً: لا يبقى في
// التاريخ ولا يُرسَل في إحالة.
function captureActivation() {
    if (!location.hash.startsWith('#activate=')) {
        return;
    }
    const params = new URLSearchParams(location.hash.slice(1));
    state.activation = { token: params.get('activate') || '', username: params.get('u') || '' };
    history.replaceState(null, '', `${location.pathname}#/activate`);
}

function renderActivate() {
    if (!state.activation) {
        // إعادة تحميلٍ بعد محو الرابط: الرمز لم يعد في الذاكرة.
        UI.show('login');
        UI.showAlert(UI.screen('login'), 'افتح رابط التفعيل من جديد.');
        return;
    }
    $('activate-username').value = state.activation.username;
    UI.show('activate');
}

async function onActivate(event) {
    event.preventDefault();
    const section = UI.screen('activate');
    if (state.busy || !state.activation) {
        return;
    }
    state.busy = true;
    const result = await api('POST', '/api/auth/activate', {
        json: {
            token: state.activation.token,
            username: state.activation.username,
            password: $('activate-password').value,
        },
    });
    state.busy = false;
    if (result.status === 204) {
        state.activation = null;
        // انتقالٌ كامل لا تغيير وسم: هكذا يعرض Safari حفظ كلمة المرور.
        location.replace('/');
    } else {
        UI.showAlert(section, detail(result));
    }
}

/* ── الرئيسية ───────────────────────────────────────────────────────── */

/* «سيمبول» يتكلّم بلسانه، واسم المستخدم من قاعدة التطبيق: النموذج لا يعرفه. */
const PERSONA = 'سيمبول';

function greeting() {
    return state.displayName
        ? `أنا ${PERSONA}، مساعدك الشخصي يا ${state.displayName}.`
        : `أنا ${PERSONA}، مساعدك الشخصي.`;
}

async function renderHome() {
    const nav = ++state.nav;
    state.campaign = null;
    const section = UI.show('home');
    $('home-greeting').textContent = greeting();
    // لا أزرار في موضعٍ مؤقّت تحت النظر: قبل أول بوابةٍ تُخفى، وبعدها يبقى رسمها
    // الأخير حتى تُقرأ من جديد (المهنة قد تتغيّر والتطبيق مفتوح).
    $('home-actions').hidden = !state.portal;
    const portal = await loadPortal({ fresh: true });
    if (nav !== state.nav) {
        return;
    }
    if (!portal) {
        UI.showAlert(section, GENERIC);
        return;
    }
    $('home-actions').hidden = false;
    $('home-portal').textContent = `بوابة ${portal.name}`;
    const campaigns = portal.tools.includes('CAMPAIGN');
    $('home-new').hidden = !campaigns;
    $('home-actions').className = `grid ${campaigns ? 'grid--3' : 'grid--2'}`;
    $('home-about').hidden = campaigns;
    $('home-about').textContent = portal.summary;
    // التعريف مترجمٌ عن المصدر كالمهامّ: يُذكر مصدره تحته.
    $('home-about-source').hidden = campaigns;
    $('home-about-source').textContent = portal.sources.summary;
    if (!campaigns) {
        $('home-list').replaceChildren();
        $('home-empty').hidden = true;
        $('home-install').hidden = true;
        UI.setButton($('home-older'), { reserved: true });
        UI.setButton($('home-newer'), { reserved: true });
        return;
    }
    const result = await api('GET', `/api/campaigns?page=${state.page}`);
    if (nav !== state.nav) {
        return;
    }
    if (result.status !== 200) {
        if (result.status !== 401) {
            UI.showAlert(section, detail(result));
        }
        return;
    }
    const list = $('home-list');
    list.replaceChildren();
    result.data.items.forEach((item) => {
        const row = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn';
        button.dataset.safe = '';
        const title = document.createElement('span');
        title.textContent = item.title || 'مسودة';
        const status = document.createElement('span');
        status.className = 'row-status';
        status.textContent = STATUS_LABELS[item.status] || '';
        button.append(title, status);
        button.addEventListener('click', () => go(`#/c/${item.id}`));
        row.append(button);
        list.append(row);
    });
    $('home-empty').hidden = result.data.items.length > 0 || state.page > 1;
    const standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
    // التلميح يظهر حين يتّسع له المكان: صفّان يملآن الشاشة بلا تمرير.
    $('home-install').hidden = standalone || result.data.items.length > 1;
    UI.setButton($('home-older'), { reserved: !result.data.has_more });
    UI.setButton($('home-newer'), { reserved: state.page <= 1 });
}

async function onLogout() {
    const section = document.querySelector('.screen:not([hidden])');
    if (state.busy || UI.alertOpen(section)) {
        return;
    }
    state.busy = true;
    const result = await api('POST', '/api/auth/logout');
    state.busy = false;
    // ملفّ الجلسة لا يمحوه إلا الخادم: خروجٌ لم يصل لم يقع، ويُقال ذلك.
    if (result.status === 204 || result.status === 401) {
        location.replace('/');
        return;
    }
    UI.showAlert(section, `لم يتمّ تسجيل الخروج. ${detail(result)}`);
}

/* ── الصورة ─────────────────────────────────────────────────────────── */

function imageUrl(campaign) {
    return `/api/campaigns/${campaign.id}/image?v=${campaign.image ? campaign.image.tag : ''}`;
}

function renderPhoto() {
    const campaign = state.campaign;
    UI.show('photo');
    const hasImage = Boolean(campaign && campaign.image);
    $('photo-pick').textContent = hasImage ? 'اختر صورةً أخرى' : 'اختر صورة المنتج';
    const preview = $('photo-preview');
    preview.hidden = !hasImage;
    if (hasImage) {
        preview.src = imageUrl(campaign);
    }
    $('photo-status').textContent = '';
    UI.setButton($('photo-generate'), { label: 'اكتب لي العنوان والوصف', enabled: hasImage, commit: true });
    UI.setButton(UI.screen('photo').querySelector('[data-cancel]'), { reserved: !campaign });
}

async function onPhotoChosen(event) {
    const input = event.currentTarget;
    const file = input.files && input.files[0];
    input.value = '';
    if (!file || state.busy) {
        return;
    }
    const section = UI.screen('photo');
    // الصورة لحملة الشاشة الظاهرة كما يسمّيها العنوان، لا لما بقي في الذاكرة.
    const shown = location.hash.match(/^#\/c\/([0-9a-f-]{36})$/);
    const campaign = shown && state.campaign && state.campaign.id === shown[1] ? state.campaign : null;
    if (!campaign && location.hash !== '#/new') {
        return;
    }
    state.busy = true;
    $('photo-status').textContent = 'تُرفع الصورة…';
    const type = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type) ? file.type : 'image/jpeg';
    const result = campaign
        ? await api('PUT', `/api/campaigns/${campaign.id}/image?expected_row_version=${campaign.row_version}`,
            { raw: file, type })
        : await api('POST', '/api/campaigns', { raw: file, type });
    state.busy = false;
    $('photo-status').textContent = '';
    if (section.hidden) {
        return;
    }
    if (result.status === 200 || result.status === 201) {
        state.campaign = result.data;
        go(campaignRoute(result.data), { replace: true });
    } else if (result.status !== 401) {
        UI.showAlert(section, detail(result));
    }
}

/* ── النصّ ───────────────────────────────────────────────────────────── */

function renderWaiting({ reloaded }) {
    const section = UI.show('proposal');
    $('proposal-waiting').hidden = false;
    $('proposal-copy').hidden = true;
    $('proposal-check').hidden = !reloaded;
    // الشريط السفلي محجوزٌ معطّل: نتيجةٌ تصل بعد دقيقةٍ لا تجد زرّاً تحت النظر.
    UI.setButton($('proposal-start'), { reserved: true });
    UI.setButton($('proposal-end'), { reserved: true });
    UI.setButton(section.querySelector('[data-cancel]'), { reserved: true });
    section.querySelector('#proposal-waiting h2').focus({ preventScroll: true });
}

async function keepAwake() {
    // الكتابة قد تستغرق دقيقة؛ قفل الشاشة يقطع الطلب في Safari. لا مؤقّت هنا.
    try {
        return navigator.wakeLock ? await navigator.wakeLock.request('screen') : null;
    } catch (error) {
        return null;
    }
}

async function runGeneration(path, json) {
    const campaign = state.campaign;
    state.waitingFor = campaign.id;
    renderWaiting({ reloaded: false });
    const lock = await keepAwake();
    const result = await api('POST', path, { json });
    if (lock) {
        lock.release().catch(() => {});
    }
    state.waitingFor = null;
    if (result.status === 401) {
        return;
    }
    const stillHere = state.campaign && state.campaign.id === campaign.id
        && !UI.screen('proposal').hidden;
    if (result.status !== 200 && !(result.data && result.data.code)) {
        // انقطع الطلب في الطريق (شبكة أو وكيل) لا عند الخادم: قد يكون النصّ
        // كُتب. تُقرأ الحملة كما هي، ولا يُفترض شيء — ويُقال ما حدث.
        if (!stillHere) {
            return;
        }
        state.campaign = null;
        const fresh = await loadCampaign(campaign.id);
        if (fresh && fresh.generating) {
            renderWaiting({ reloaded: true });
            return;
        }
        if (fresh) {
            history.replaceState(null, '', campaignRoute(fresh));
            await route();
        } else {
            // الحملة لم تُقرأ أيضاً: تبقى شاشة الانتظار و«تحقّق الآن» فيها.
            state.campaign = campaign;
            renderWaiting({ reloaded: true });
        }
        UI.showAlert(document.querySelector('.screen:not([hidden])'), fresh
            ? 'انقطع الاتصال قبل أن يصل الردّ. هذا ما حُفظ في الحملة الآن.'
            : 'تعذّر الاتصال، ولم يُعرف إن كُتب النص. تحقّق من الاتصال ثم اضغط «تحقّق الآن».');
        return;
    }
    if (result.status === 200) {
        // من غادر الشاشة لا تُغيَّر شاشته ولا تعديله من تحته؛ تُحدَّث الحملة
        // المحفوظة فقط إن كانت هي نفسها.
        if (!stillHere) {
            if (state.campaign && state.campaign.id === campaign.id) {
                state.campaign = result.data.campaign;
            }
            return;
        }
        state.campaign = result.data.campaign;
        state.edit = { versionId: null, presets: new Set(), note: null, draft: '', armed: false };
        // العنوان يتبع الحالة: إعادة التحميل بعدها تعرض ما يُعرض الآن.
        history.replaceState(null, '', campaignRoute(state.campaign));
        await route();
        if (result.data.result === 'UNUSABLE_PHOTO') {
            const advice = result.data.assistant_note ? ` ${PERSONA}: ${result.data.assistant_note}` : '';
            UI.showAlert(UI.screen('photo'), result.data.message + advice);
        }
        return;
    }
    if (stillHere) {
        // الفشل يُقرّ قبل أيّ شيء: «حسناً» تعيد الشاشة التي بدأ منها.
        state.campaign = null;
        await loadCampaign(campaign.id);
        UI.showAlert(UI.screen('proposal'), detail(result));
    }
}

const BUSY_ELSEWHERE = 'يكتب سيمبول نصّ حملةٍ أخرى الآن. حين ينتهي يمكن البدء هنا.';

/* «تحقّق الآن» بعد ردٍّ لم يصل: تُقرأ الحملة، ويبقى الانتظار ما دام الاتصال مقطوعاً. */
async function onProposalCheck() {
    const section = UI.screen('proposal');
    const campaign = state.campaign;
    if (!campaign || state.busy || UI.alertOpen(section)) {
        return;
    }
    const nav = state.nav;
    state.busy = true;
    const result = await api('GET', `/api/campaigns/${campaign.id}`);
    state.busy = false;
    if (nav !== state.nav || section.hidden || result.status === 401) {
        return;
    }
    if (result.status === 404) {
        go('#/', { replace: true });
        return;
    }
    if (result.status !== 200) {
        UI.showAlert(section, `${detail(result)} «تحقّق الآن» تعيد المحاولة.`);
        return;
    }
    state.campaign = result.data;
    route();
}

function onGenerate() {
    const campaign = state.campaign;
    if (!campaign || state.busy) {
        return;
    }
    if (state.waitingFor) {
        UI.showAlert(UI.screen('photo'), BUSY_ELSEWHERE);
        return;
    }
    runGeneration(`/api/campaigns/${campaign.id}/copy`, { expected_row_version: campaign.row_version });
}

function fillCopy(prefix, campaign, copy) {
    const thumb = $(`${prefix}-thumb`);
    thumb.src = imageUrl(campaign);
    $(`${prefix}-title`).textContent = copy.title;
    $(`${prefix}-description`).textContent = copy.description;
}

function renderProposal() {
    const campaign = state.campaign;
    const copy = campaign.copy;
    const section = UI.show('proposal');
    $('proposal-waiting').hidden = true;
    $('proposal-copy').hidden = false;
    fillCopy('proposal', campaign, copy);
    const note = $('proposal-note');
    note.textContent = copy.assistant_note ? `${PERSONA}: ${copy.assistant_note}` : '';
    note.hidden = !copy.assistant_note;
    $('proposal-warnings').textContent = copy.warnings.length
        ? `تحقّق من هذه العبارة قبل الموافقة: ${copy.warnings.map((w) => WARNING_LABELS[w]).join('، ')}`
        : '';
    UI.setButton(section.querySelector('[data-cancel]'), { reserved: false });
    // قياسٌ بعد الرسم لا مؤقّت: إن فاض المحتوى يُضغط تخطيطه، ولا يُقصّ النصّ.
    const copyBox = $('proposal-copy');
    copyBox.classList.remove('copy--compact');
    const content = section.querySelector('.content');
    const approved = campaign.status === 'COPY_APPROVED';
    if (approved) {
        $('proposal-status').textContent = 'تمّت الموافقة على هذا النص.';
        UI.setButton($('proposal-start'), { label: 'تراجع عن الموافقة', commit: true });
        UI.setButton($('proposal-end'), { label: 'تابع إلى الميزانية' });
    } else {
        $('proposal-status').textContent =
            `نصٌّ مقترحٌ آلياً — لم توافق عليه بعد · النسخة ${copy.version} من ${state.choices.limits.versions_max}`;
        // بلا نسخٍ متبقية يبقى الرجوع إلى نسخةٍ سابقة ممكناً من شاشة التعديل.
        const canEdit = campaign.versions_left > 0;
        UI.setButton($('proposal-start'), {
            label: canEdit ? 'اطلب تعديلاً' : 'نسخةٌ سابقة',
            enabled: canEdit || copy.can_restore_previous || copy.can_restore_newest,
        });
        UI.setButton($('proposal-end'), { label: 'أوافق على النص', commit: true });
    }
    const overflowing = () => content.scrollHeight > content.clientHeight;
    copyBox.classList.toggle('copy--compact', overflowing());
    // والملاحظة إن بقي الفيض: تُعرض وحدها أولاً، مرةً لكل نسخة، ثم يُعرض النصّ
    // كاملاً بلا قصّ. ما يُوافَق عليه لا يُقصّ منه حرف.
    if (copy.assistant_note && overflowing()) {
        note.hidden = true;
        if (state.noteShownFor !== copy.version_id) {
            state.noteShownFor = copy.version_id;
            UI.showAlert(section, `${PERSONA}: ${copy.assistant_note}`);
        }
    }
}

/*
 * كتابةٌ على الحملة الحالية. تعيد الحملة الجديدة إن بقي المستخدم على الشاشة
 * التي أرسلت؛ فإن غادرها لا تُرسم شاشته من تحته — ولا يقع زرٌّ يعتمد تحت نظرٍ
 * استقرّ على شاشةٍ أخرى — وتُحدَّث الحملة المحفوظة إن كانت هي نفسها فقط.
 */
async function mutate(section, method, path, json) {
    if (state.busy || UI.alertOpen(section)) {
        return null;
    }
    const nav = state.nav;
    const id = state.campaign && state.campaign.id;
    state.busy = true;
    const result = await api(method, path, { json });
    state.busy = false;
    const stillHere = nav === state.nav && !section.hidden;
    if (!stillHere) {
        if (result.status === 200 && state.campaign && state.campaign.id === id) {
            state.campaign = result.data;
        }
        return null;
    }
    if (result.status === 200) {
        state.campaign = result.data;
        return result.data;
    }
    if (result.status !== 401) {
        if (result.status === 409) {
            // تغيّرت الحملة: تُقرأ من جديد قبل أيّ قرارٍ آخر.
            const id = state.campaign && state.campaign.id;
            state.campaign = null;
            if (id) {
                await loadCampaign(id);
            }
        }
        UI.showAlert(section, detail(result));
    }
    return null;
}

async function onProposalStart() {
    const campaign = state.campaign;
    if (campaign.status === 'COPY_APPROVED') {
        const view = await mutate(UI.screen('proposal'), 'POST', `/api/campaigns/${campaign.id}/copy/unapprove`,
            { expected_row_version: campaign.row_version });
        if (view) {
            renderProposal();
        }
    } else {
        // الوصول إلى شاشة التعديل لا يُرسل شيئاً: «اطلب نسخة جديدة» تبقى معطّلةً
        // حتى يختار المستخدم فيها، فلا يرسل الطلبَ نظرٌ مرّ بها في الطريق.
        editState().armed = false;
        go(`#/c/${campaign.id}/edit`);
    }
}

async function onProposalEnd() {
    const campaign = state.campaign;
    if (campaign.status === 'COPY_APPROVED') {
        go(`#/c/${campaign.id}/budget`);
        return;
    }
    const view = await mutate(UI.screen('proposal'), 'POST', `/api/campaigns/${campaign.id}/copy/approve`,
        { expected_row_version: campaign.row_version, version_id: campaign.copy.version_id });
    if (view) {
        renderProposal();
    }
}

/* ── طلب التعديل ────────────────────────────────────────────────────── */

function editState() {
    const versionId = state.campaign.copy.version_id;
    if (state.edit.versionId !== versionId) {
        state.edit = { versionId, presets: new Set(), note: null, draft: '', armed: false };
    }
    return state.edit;
}

function conflictOf(preset) {
    const pair = state.choices.preset_conflicts.find((p) => p.includes(preset));
    return pair ? pair.find((p) => p !== preset) : null;
}

function renderEdit() {
    const campaign = state.campaign;
    const edit = editState();
    UI.show('edit');
    const exhausted = campaign.versions_left <= 0;
    const full = edit.presets.size >= state.choices.limits.presets_max;
    const options = state.choices.edit_presets.map((preset) => ({
        value: preset,
        label: PRESET_LABELS[preset],
        disabled: exhausted || (!edit.presets.has(preset) && (full || edit.presets.has(conflictOf(preset)))),
    }));
    // مجموعة متعدّدة الاختيار: كل خيارٍ يُبدَّل وحده.
    const chips = $('edit-chips');
    chips.replaceChildren();
    options.forEach((option) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn chip';
        button.textContent = option.label;
        button.dataset.key = option.value;
        button.setAttribute('aria-pressed', String(edit.presets.has(option.value)));
        button.disabled = option.disabled;
        button.addEventListener('click', () => {
            if (edit.presets.has(option.value)) {
                edit.presets.delete(option.value);
            } else {
                edit.presets.add(option.value);
            }
            edit.armed = true;
            renderEdit();
        });
        chips.append(button);
    });
    UI.setButton($('edit-note'), {
        label: edit.note ? 'ملاحظة نصية (مكتوبة)' : 'ملاحظة نصية',
        enabled: !exhausted,
    });
    // «النسخة الأحدث» تُلغي «النسخة السابقة»: ضغطةٌ خاطئة لا تُفقد نسخة.
    const newest = campaign.copy.can_restore_newest;
    UI.setButton($('edit-restore'), {
        label: newest ? 'النسخة الأحدث' : 'النسخة السابقة',
        enabled: newest || campaign.copy.can_restore_previous,
        commit: true,
    });
    $('edit-restore').dataset.target = newest ? 'newest' : 'previous';
    UI.setButton($('edit-submit'), {
        label: 'اطلب نسخة جديدة',
        enabled: !exhausted && edit.armed && (edit.presets.size > 0 || Boolean(edit.note)),
        commit: true,
    });
    if (exhausted) {
        $('edit-left').textContent = 'بلغت الحملة حدّ النسخ؛ يمكن الرجوع إلى نسخةٍ سابقة.';
    } else {
        $('edit-left').textContent = full
            ? 'ثلاثة تعديلاتٍ على الأكثر'
            : `النسخ المتبقية: ${campaign.versions_left}`;
    }
}

function onEditSubmit() {
    const campaign = state.campaign;
    const edit = editState();
    if (state.busy || !edit.armed || (!edit.presets.size && !edit.note)) {
        return;
    }
    if (state.waitingFor) {
        UI.showAlert(UI.screen('edit'), BUSY_ELSEWHERE);
        return;
    }
    runGeneration(`/api/campaigns/${campaign.id}/copy/edit`, {
        expected_row_version: campaign.row_version,
        expected_version_id: campaign.copy.version_id,
        presets: Array.from(edit.presets),
        note: edit.note,
    });
}

async function onRestore() {
    const campaign = state.campaign;
    const view = await mutate(UI.screen('edit'), 'POST', `/api/campaigns/${campaign.id}/copy/restore`, {
        expected_row_version: campaign.row_version,
        expected_version_id: campaign.copy.version_id,
        target: $('edit-restore').dataset.target,
    });
    if (view) {
        go(campaignRoute(view));
    }
}

function renderNote() {
    const edit = editState();
    UI.show('note');
    const area = $('note-text');
    area.value = edit.draft || edit.note || '';
    updateNoteCount();
}

function updateNoteCount() {
    const left = state.choices.limits.note_max - $('note-text').value.length;
    $('note-count').textContent = `الأحرف المتبقية: ${left}`;
}

function onNoteSave() {
    const edit = editState();
    // ما يُرسل هو ما يُحسب: المسافات المتكرّرة وفواصل الأسطر مسافةٌ واحدة.
    const text = $('note-text').value.replace(/\s+/g, ' ').trim();
    edit.note = text ? text : null;
    edit.draft = '';
    edit.armed = true;
    go(`#/c/${state.campaign.id}/edit`);
}

// «رجوع» من الملاحظة لا يمحو ما كُتب بالنظر حرفاً حرفاً: يبقى مسودةً تعود
// إليها، ولا يُرسل حتى تُحفظ.
function onNoteBack() {
    editState().draft = $('note-text').value;
    go(`#/c/${state.campaign.id}/edit`);
}

/* ── الميزانية والمدّة ───────────────────────────────────────────────── */

function neighbour(values, current, delta) {
    if (current === null) {
        return delta > 0 ? values[0] : null;
    }
    const index = values.indexOf(current) + delta;
    return index >= 0 && index < values.length ? values[index] : null;
}

function renderValue(container, digits, words, extra) {
    container.replaceChildren();
    if (digits === null) {
        const empty = document.createElement('p');
        empty.className = 'value__words';
        empty.textContent = words;
        container.append(empty);
        return;
    }
    const top = document.createElement('p');
    top.className = 'value__digits';
    top.append(UI.bdi(digits));
    const bottom = document.createElement('p');
    bottom.className = 'value__words';
    bottom.textContent = words;
    container.append(top, bottom);
    if (extra) {
        const line = document.createElement('p');
        line.className = 'value__daily';
        line.textContent = extra;
        container.append(line);
    }
}

function dailyText(campaign) {
    if (!campaign.daily) {
        return '';
    }
    const amount = `${campaign.daily.amount} ر.س`;
    return campaign.daily.exact ? `في اليوم: ${amount}` : `في اليوم نحو: ${amount}`;
}

function renderBudget() {
    const campaign = state.campaign;
    UI.show('budget');
    const table = state.choices.budget;
    const values = table.values.map((v) => v.sar);
    const current = campaign.budget ? campaign.budget.sar : null;
    renderValue($('budget-value'),
        campaign.budget ? campaign.budget.short : null,
        campaign.budget ? `الميزانية الإجمالية: ${campaign.budget.words}` : 'لم تُحدَّد الميزانية بعد.');
    UI.choiceGroup($('budget-presets'),
        table.presets.map((sar) => ({ value: sar, label: sar.toLocaleString('en-US') })),
        current, (sar) => setBudget(sar));
    const down = neighbour(values, current, -1);
    const up = neighbour(values, current, +1);
    const label = (sar) => table.values.find((v) => v.sar === sar).short;
    UI.setButton($('budget-down'), { label: down === null ? 'أقل' : `أقل: ${label(down)}`, enabled: down !== null });
    UI.setButton($('budget-up'), { label: up === null ? 'أكثر' : `أكثر: ${label(up)}`, enabled: up !== null });
    $('budget-down').dataset.value = down === null ? '' : String(down);
    $('budget-up').dataset.value = up === null ? '' : String(up);
    UI.setButton($('budget-next'), { label: 'التالي: عدد الأيام', enabled: current !== null });
}

async function setBudget(sar) {
    const campaign = state.campaign;
    const view = await mutate(UI.screen('budget'), 'PUT', `/api/campaigns/${campaign.id}/budget`,
        { expected_row_version: campaign.row_version, budget_sar: sar });
    if (view) {
        renderBudget();
    }
}

function renderDays() {
    const campaign = state.campaign;
    UI.show('days');
    const table = state.choices.days;
    const values = table.values.map((v) => v.n);
    const current = campaign.days ? campaign.days.n : null;
    renderValue($('days-value'),
        campaign.days ? campaign.days.short : null,
        campaign.days ? `المدة: ${campaign.days.words}` : 'لم تُحدَّد المدة بعد.',
        dailyText(campaign));
    UI.choiceGroup($('days-presets'),
        table.presets.map((n) => ({ value: n, label: table.values.find((v) => v.n === n).short })),
        current, (n) => setDays(n));
    const down = neighbour(values, current, -1);
    const up = neighbour(values, current, +1);
    const label = (n) => table.values.find((v) => v.n === n).short;
    UI.setButton($('days-down'), { label: down === null ? 'أقل' : `أقل: ${label(down)}`, enabled: down !== null });
    UI.setButton($('days-up'), { label: up === null ? 'أكثر' : `أكثر: ${label(up)}`, enabled: up !== null });
    $('days-down').dataset.value = down === null ? '' : String(down);
    $('days-up').dataset.value = up === null ? '' : String(up);
    UI.setButton($('days-next'), { label: 'التالي: المراجعة', enabled: current !== null });
}

async function setDays(n) {
    const campaign = state.campaign;
    const view = await mutate(UI.screen('days'), 'PUT', `/api/campaigns/${campaign.id}/days`,
        { expected_row_version: campaign.row_version, days: n });
    if (view) {
        renderDays();
    }
}

/* ── المراجعة والتأكيد ───────────────────────────────────────────────── */

function lineWith(element, label, words, digits) {
    // الكلمات بعد العنوان والنقطتين مباشرةً — موضع الرفع — والأرقام بعدها.
    element.replaceChildren(`${label}: ${words} (`, UI.bdi(digits), ')');
}

function renderReview() {
    const campaign = state.campaign;
    UI.show('review');
    fillCopy('review', campaign, campaign.copy);
    lineWith($('review-budget'), 'الميزانية الإجمالية', campaign.budget.words, campaign.budget.short);
    lineWith($('review-days'), 'المدة', campaign.days.words, campaign.days.short);
    $('review-daily').textContent = dailyText(campaign);
}

function renderConfirm() {
    const campaign = state.campaign;
    UI.show('confirm');
    $('confirm-restate').textContent =
        `الميزانية الإجمالية: ${campaign.budget.words}. المدة: ${campaign.days.words}. `
        + 'لن يُنشر شيءٌ ولن يُدفع أيّ مبلغٍ تلقائياً، ولا يمكن تعديل الحملة بعد اعتمادها.';
}

async function onConfirm() {
    const campaign = state.campaign;
    const view = await mutate(UI.screen('confirm'), 'POST', `/api/campaigns/${campaign.id}/confirm`, {
        expected_row_version: campaign.row_version,
        version_id: campaign.approved_version_id,
        budget_sar: campaign.budget.sar,
        days: campaign.days.n,
    });
    if (view) {
        go(campaignRoute(view));
    }
}

/* ── الإلغاء والسحب ──────────────────────────────────────────────────── */

function renderCancel() {
    const withdraw = state.campaign && state.campaign.status === 'READY';
    UI.show('cancel');
    $('cancel-heading').textContent = withdraw ? 'سحب الحملة' : 'إلغاء الحملة';
    UI.setButton($('cancel-yes'), { label: withdraw ? 'نعم، اسحب الحملة' : 'نعم، ألغِ الحملة', commit: true });
}

async function onCancelYes() {
    const campaign = state.campaign;
    const view = await mutate(UI.screen('cancel'), 'POST', `/api/campaigns/${campaign.id}/cancel`,
        { expected_row_version: campaign.row_version });
    if (view) {
        state.campaign = null;
        go('#/');
    }
}

/* ── جاهزة للتسليم ───────────────────────────────────────────────────── */

function brief(campaign) {
    return [
        campaign.copy.title,
        '',
        campaign.copy.description,
        '',
        `الميزانية الإجمالية: ${campaign.budget.words} (${campaign.budget.short})`,
        `المدة: ${campaign.days.words} (${campaign.days.short})`,
        dailyText(campaign),
    ].join('\n');
}

async function renderReady() {
    const campaign = state.campaign;
    UI.show('ready');
    fillCopy('ready', campaign, campaign.copy);
    $('ready-summary').replaceChildren(UI.bdi(`${campaign.budget.short} · ${campaign.days.short}`));
    $('ready-status').textContent = '';
    $('ready-download').href = imageUrl(campaign);
    // الصورة تُجلب الآن لا عند الضغط: المشاركة يجب أن تبدأ داخل الضغطة نفسها.
    state.readyBlob = null;
    const result = await api('GET', imageUrl(campaign), { as: 'blob' });
    if (result.status === 200 && state.campaign && state.campaign.id === campaign.id) {
        state.readyBlob = result.data;
    }
}

async function copyText(text, done) {
    try {
        await navigator.clipboard.writeText(text);
        $('ready-status').textContent = done;
    } catch (error) {
        UI.showAlert(UI.screen('ready'), 'تعذّر النسخ. استخدم «شارك الحملة».');
    }
}

async function onShare() {
    const campaign = state.campaign;
    const data = { title: campaign.copy.title, text: brief(campaign) };
    if (state.readyBlob) {
        const file = new File([state.readyBlob], 'campaign.jpg', { type: 'image/jpeg' });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            data.files = [file];
        }
    }
    if (!navigator.share) {
        await copyText(data.text, 'نُسخ ملخّص الحملة.');
        return;
    }
    try {
        await navigator.share(data);
    } catch (error) {
        if (!error || error.name !== 'AbortError') {
            UI.showAlert(UI.screen('ready'), 'تعذّرت المشاركة. استخدم «نزّل الصورة» و«انسخ الوصف».');
        }
    }
}

/* ── الإقلاع ────────────────────────────────────────────────────────── */

function wire() {
    $('login-form').addEventListener('submit', onLogin);
    $('activate-form').addEventListener('submit', onActivate);
    $('home-new').addEventListener('click', () => go('#/new'));
    $('home-older').addEventListener('click', () => { state.page += 1; renderHome(); });
    $('home-newer').addEventListener('click', () => { state.page = Math.max(1, state.page - 1); renderHome(); });
    $('photo-input').addEventListener('change', onPhotoChosen);
    $('photo-generate').addEventListener('click', onGenerate);
    $('proposal-start').addEventListener('click', onProposalStart);
    $('proposal-end').addEventListener('click', onProposalEnd);
    $('proposal-check').addEventListener('click', onProposalCheck);
    $('edit-note').addEventListener('click', () => go(`#/c/${state.campaign.id}/note`));
    $('edit-restore').addEventListener('click', onRestore);
    $('edit-submit').addEventListener('click', onEditSubmit);
    $('note-text').addEventListener('input', updateNoteCount);
    $('note-save').addEventListener('click', onNoteSave);
    $('budget-down').addEventListener('click', (e) => setBudget(Number(e.currentTarget.dataset.value)));
    $('budget-up').addEventListener('click', (e) => setBudget(Number(e.currentTarget.dataset.value)));
    $('budget-next').addEventListener('click', () => go(`#/c/${state.campaign.id}/days`));
    $('days-down').addEventListener('click', (e) => setDays(Number(e.currentTarget.dataset.value)));
    $('days-up').addEventListener('click', (e) => setDays(Number(e.currentTarget.dataset.value)));
    $('days-next').addEventListener('click', () => go(`#/c/${state.campaign.id}/review`));
    $('review-continue').addEventListener('click', renderConfirm);
    $('confirm-yes').addEventListener('click', onConfirm);
    $('confirm-back').addEventListener('click', renderReview);
    $('cancel-yes').addEventListener('click', onCancelYes);
    $('cancel-back').addEventListener('click', route);
    $('ready-copy-title').addEventListener('click', () => copyText(state.campaign.copy.title, 'نُسخ العنوان.'));
    $('ready-copy-description').addEventListener('click',
        () => copyText(state.campaign.copy.description, 'نُسخ الوصف.'));
    $('ready-share').addEventListener('click', onShare);

    document.querySelectorAll('[data-back]').forEach((button) => {
        const name = button.closest('.screen').dataset.screen;
        button.addEventListener('click', name === 'note' ? onNoteBack : () => go(parentOf(name)));
    });
    document.querySelectorAll('[data-home]').forEach((button) => button.addEventListener('click', () => go('#/')));
    document.querySelectorAll('[data-cancel]').forEach((button) => button.addEventListener('click', renderCancel));
    document.querySelectorAll('[data-ack]').forEach((button) => {
        button.addEventListener('click', () => {
            const section = button.closest('.screen');
            UI.clearAlert(section);
            if (retryBoot && section.dataset.screen === 'login') {
                retryBoot = false;
                boot();
                return;
            }
            // فحص رمز التسجيل لم يكتمل (انقطاعٌ أو حدّ): الرمز في الذاكرة، فيُعاد.
            if (section.dataset.screen === 'login' && state.signup && !state.signup.checked) {
                route();
                return;
            }
            // انتظارٌ لا يُعرف مآله: يبقى، و«تحقّق الآن» فيه هو المخرج.
            if (section.dataset.screen === 'proposal' && !$('proposal-check').hidden
                && !$('proposal-waiting').hidden) {
                return;
            }
            // بعد الإقرار تُعرض الحملة كما هي الآن، لا كما كانت.
            if (['proposal', 'confirm', 'budget', 'days', 'edit'].includes(section.dataset.screen)) {
                route();
            }
        });
    });
    wirePortal();
    window.addEventListener('hashchange', route);
    // صفحةٌ تعود من ذاكرة الرجوع في Safari قد تعرض تأكيداً قديماً: تُقرأ من جديد.
    window.addEventListener('pageshow', (event) => {
        if (event.persisted) {
            state.campaign = null;
            state.portal = null;
            route();
        }
    });
}

// فشل الإقلاع لا يترك شاشةً بلا مخرج: «حسناً» تعيد المحاولة.
let retryBoot = false;

async function loadChoices() {
    const choices = await api('GET', '/api/choices');
    if (choices.status !== 200) {
        startupFailed(detail(choices));
        return false;
    }
    state.choices = choices.data;
    retryBoot = false;
    return true;
}

async function boot() {
    if (!(await loadChoices())) {
        return;
    }
    if (location.hash.startsWith('#/activate')) {
        renderActivate();
        return;
    }
    // التسجيل قبل الجلسة: لا يُسأل عن صاحبٍ لم يُنشأ حسابه بعد.
    if (location.hash.startsWith('#/signup')) {
        route();
        return;
    }
    const me = await api('GET', '/api/me');
    if (me.status === 200) {
        state.displayName = me.data.display_name || null;
        route();
    } else if (me.status !== 401) {
        // 401 يعرض شاشة الدخول من `api`؛ ما سواه عطلٌ لا «لست مسجّلاً».
        startupFailed(detail(me));
    }
}

function startupFailed(message) {
    retryBoot = true;
    const section = UI.show('login');
    UI.showAlert(section, `${message} «حسناً» تعيد المحاولة.`);
}

captureActivation();
captureSignup();
wire();
boot();
