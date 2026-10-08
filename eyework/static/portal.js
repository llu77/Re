/*
 * التسجيل والحساب والبوابة
 * ========================
 * يُحمَّل قبل app.js، ويستعمل عند التشغيل ما فيه: `state` و`api` و`go` و`detail`
 * و`renderValue` و`renderLogin`. و`wire()` في app.js يستدعي `wirePortal()` من هنا.
 *
 *   • التسجيل برابطٍ من المشغّل (#signup=…): الرمز يُقرأ إلى الذاكرة ويُمحى من
 *     شريط العنوان، ويُسأل الخادم عنه قبل الخطوة الأولى. البيانات في الذاكرة
 *     خطوةً خطوة، ولا تُرسل إلا في الأخيرة مع كلمة المرور — في نموذجٍ ظاهرٍ
 *     يُرسَل، فيعرض Safari حفظها.
 *   • تاريخ الميلاد بأزرارٍ لا بكتابة: سنواتٌ وأشهرٌ وأيامٌ جاهزة، وخطوة «أقدم/أحدث».
 *   • البوابة لمهنة صاحب الحساب وحدها، والمهامّ والمهارات بندٌ واحد في كل شاشة:
 *     لا تمرير، ولا نصٌّ مقصوص.
 *   • مفتاح المرور: «ادخل بمفتاح المرور» في شاشة الدخول و«أضف مفتاح مرور» في
 *     الحساب، وكلمة المرور باقيةٌ بجانبه.
 */

'use strict';

const MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

const MODE_LABELS = {
    IN_APP: 'جزءٌ منها في هذه البوابة، تسمّيه الملاحظة',
    EMPLOYER_SYSTEM: 'عملٌ مكتبي يحتاج أنظمة صاحب العمل',
    ON_SITE: 'عملٌ ميداني لا يُؤدّى بالنظر',
    VOICE: 'بالهاتف أو الصوت',
};

/* رمزٌ مشوّه (حرفٌ زائد من تطبيق محادثة مثلاً) يرفضه فحص الشكل بـ422: نصّ الرابط لا نصّ الطلب. */
const SIGNUP_LINK_INVALID = 'رابط التسجيل غير صالح أو انتهى. اطلب رابطاً جديداً ممّن أعطاك إياه.';

const SIGNUP_STEPS = ['name', 'year', 'month', 'day', 'profession', 'email', 'review', 'password'];

const YEAR_PRESETS = [1960, 1970, 1980, 1990, 2000, 2010];
const MONTH_PRESETS = [1, 3, 5, 7, 9, 11];
const DAY_PRESETS = [1, 5, 10, 15, 20, 25];

/* ── التسجيل ────────────────────────────────────────────────────────── */

function captureSignup() {
    if (!location.hash.startsWith('#signup=')) {
        return;
    }
    const params = new URLSearchParams(location.hash.slice(1));
    state.signup = {
        code: params.get('signup') || '', checked: false, agreed: false,
        name: '', year: null, month: null, day: null, profession: null, email: '',
        // رسالة خطأٍ من الخادم تُعرض على الخطوة التي يُصلَح فيها بعد رسمها.
        alert: null,
    };
    history.replaceState(null, '', `${location.pathname}#/signup`);
}

function daysIn(year, month) {
    return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/* الاسم كما يفحصه الخادم (auth.check_name): مسافاتٌ مفردة، و«ی/ک» عربية. */
function normalizeName(raw) {
    return raw.replace(/ی/g, 'ي').replace(/ک/g, 'ك').replace(/\s+/g, ' ').trim();
}

function nameIsValid(name) {
    return name.length > 0 && name.length <= state.choices.registration.name_max
        && /^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$/.test(name);
}

/* البريد كما يوحّده الخادم (auth.normalize_login) ويفحصه (auth.check_email).
   casefold في بايثون يزيد على toLowerCase بحرفٍ واحدٍ يصير لاتينياً: «ß» ← «ss». */
function normalizeEmail(raw) {
    return raw.normalize('NFKC').toLowerCase().replace(/ß/g, 'ss').trim();
}

function emailIsValid(email) {
    return email.length <= 254 && /^[a-z0-9._+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(email);
}

function birthDate() {
    const s = state.signup;
    const pad = (n) => String(n).padStart(2, '0');
    return `${s.year}-${pad(s.month)}-${pad(s.day)}`;
}

function birthWords() {
    const s = state.signup;
    return `${s.day} ${MONTHS[s.month - 1]} ${s.year}`;
}

function birthInFuture() {
    const s = state.signup;
    const today = new Date();
    const chosen = new Date(s.year, s.month - 1, s.day);
    return chosen > today;
}

/* أول خطوةٍ ناقصة: لا تُفتح خطوةٌ قبل ما يسبقها (رابطٌ محفوظ، أو «رجوع» المتصفّح). */
function firstMissingStep() {
    const s = state.signup;
    if (!s.agreed) return 'notice';
    if (!nameIsValid(s.name)) return 'name';
    if (s.year === null) return 'year';
    if (s.month === null) return 'month';
    if (s.day === null || birthInFuture()) return 'day';
    if (s.profession === null) return 'profession';
    if (!emailIsValid(s.email)) return 'email';
    return null;
}

function stepRoute(step) {
    return step === 'notice' ? '#/signup' : `#/signup/${step}`;
}

function signupParent(name) {
    const step = name.replace('signup-', '');
    if (step === 'notice') {
        return '#/login';
    }
    const index = SIGNUP_STEPS.indexOf(step);
    return index <= 0 ? '#/signup' : stepRoute(SIGNUP_STEPS[index - 1]);
}

async function renderSignup(step, nav) {
    if (!state.signup) {
        // إعادة تحميلٍ بعد محو الرابط: الرمز لم يعد في الذاكرة.
        UI.showAlert(renderLogin(), 'افتح رابط التسجيل من جديد.');
        return;
    }
    if (!state.signup.checked) {
        const result = await api('POST', '/api/auth/signup-code', { json: { code: state.signup.code } });
        if (nav !== state.nav || !state.signup) {
            return;
        }
        if (result.status !== 204) {
            const login = renderLogin();
            if ([403, 410, 422].includes(result.status)) {
                // رمزٌ لا يصلح أو تسجيلٌ مغلق: لا فائدة من المحاولة به ثانيةً.
                state.signup = null;
                UI.showAlert(login, result.status === 422 ? SIGNUP_LINK_INVALID : detail(result));
            } else {
                // انقطاعٌ أو حدٌّ أو عطلٌ عابر: الرمز باقٍ في الذاكرة، و«حسناً» تعيد الفحص.
                UI.showAlert(login, `${detail(result)} «حسناً» تعيد المحاولة.`);
            }
            return;
        }
        state.signup.checked = true;
    }
    const missing = firstMissingStep();
    const order = ['notice', ...SIGNUP_STEPS];
    if (missing !== null && order.indexOf(step) > order.indexOf(missing)) {
        go(stepRoute(missing), { replace: true });
        return;
    }
    ({
        notice: renderSignupNotice,
        name: renderSignupName,
        year: renderSignupYear,
        month: renderSignupMonth,
        day: renderSignupDay,
        profession: renderSignupProfession,
        email: renderSignupEmail,
        review: renderSignupReview,
        password: renderSignupPassword,
    }[step] || renderSignupNotice)();
    if (state.signup && state.signup.alert) {
        UI.showAlert(document.querySelector('.screen:not([hidden])'), state.signup.alert);
        state.signup.alert = null;
    }
}

function renderSignupNotice() {
    UI.show('signup-notice');
}

function renderSignupName() {
    UI.show('signup-name');
    $('signup-name-input').value = state.signup.name;
}

function onSignupName(event) {
    event.preventDefault();
    const name = normalizeName($('signup-name-input').value);
    if (!nameIsValid(name)) {
        UI.showAlert(UI.screen('signup-name'), 'الاسم: حروفٌ عربية أو لاتينية فقط، حتى 30 حرفاً.');
        return;
    }
    state.signup.name = name;
    go(stepRoute('year'));
}

/* شاشة قيمةٍ بأزرارٍ جاهزة وخطوة «أقلّ/أكثر» — نمط الميزانية نفسه. */
function renderStepper(name, { value, presets, min, max, label, digits, words, empty, onPick, nextEnabled }) {
    UI.show(name);
    renderValue($(`${name}-value`), value === null ? null : digits(value), value === null ? empty : words(value));
    UI.choiceGroup($(`${name}-presets`),
        presets.filter((v) => v >= min && v <= max).map((v) => ({ value: v, label: label(v) })),
        value, onPick);
    const down = value === null || value - 1 < min ? null : value - 1;
    const up = value === null || value + 1 > max ? null : value + 1;
    UI.setButton($(`${name}-down`), { label: down === null ? 'أقدم' : `أقدم: ${label(down)}`, enabled: down !== null });
    UI.setButton($(`${name}-up`), { label: up === null ? 'أحدث' : `أحدث: ${label(up)}`, enabled: up !== null });
    $(`${name}-down`).dataset.value = down === null ? '' : String(down);
    $(`${name}-up`).dataset.value = up === null ? '' : String(up);
    UI.setButton($(`${name}-next`), { label: 'التالي', enabled: nextEnabled });
}

/* اليوم المختار قد لا يوجد بعد تغيير السنة أو الشهر (29 فبراير)، أو يصير في
   المستقبل: يُختار من جديد، فلا تصل المراجعةَ تاريخٌ يرفضه الخادم. */
function dropImpossibleDay() {
    const s = state.signup;
    if (s.day !== null && s.month !== null && s.year !== null
        && (s.day > daysIn(s.year, s.month) || birthInFuture())) {
        s.day = null;
    }
}

function setYear(year) {
    state.signup.year = year;
    dropImpossibleDay();
    renderSignupYear();
}

function renderSignupYear() {
    const s = state.signup;
    renderStepper('signup-year', {
        value: s.year,
        presets: YEAR_PRESETS,
        min: state.choices.registration.earliest_year,
        max: new Date().getFullYear(),
        label: String,
        digits: String,
        words: (y) => `سنة الميلاد: ${y}`,
        empty: 'لم تُحدَّد السنة بعد.',
        onPick: setYear,
        nextEnabled: s.year !== null,
    });
}

function setMonth(month) {
    state.signup.month = month;
    dropImpossibleDay();
    renderSignupMonth();
}

function renderSignupMonth() {
    const s = state.signup;
    renderStepper('signup-month', {
        value: s.month,
        presets: MONTH_PRESETS,
        min: 1,
        max: 12,
        label: (m) => MONTHS[m - 1],
        digits: (m) => MONTHS[m - 1],
        words: (m) => `شهر الميلاد: ${MONTHS[m - 1]} (${m})`,
        empty: 'لم يُحدَّد الشهر بعد.',
        onPick: setMonth,
        nextEnabled: s.month !== null,
    });
}

function setDay(day) {
    state.signup.day = day;
    renderSignupDay();
}

function renderSignupDay() {
    const s = state.signup;
    const future = s.day !== null && birthInFuture();
    renderStepper('signup-day', {
        value: s.day,
        presets: DAY_PRESETS,
        min: 1,
        max: daysIn(s.year, s.month),
        label: String,
        digits: () => birthWords(),
        words: () => (future ? 'هذا التاريخ لم يأتِ بعد.' : 'تاريخ الميلاد'),
        empty: 'لم يُحدَّد اليوم بعد.',
        onPick: setDay,
        nextEnabled: s.day !== null && !future,
    });
}

function renderSignupProfession() {
    UI.show('signup-profession');
    const list = $('signup-professions');
    list.replaceChildren();
    state.choices.professions.forEach((profession) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn chip';
        button.dataset.key = profession.code;
        button.setAttribute('aria-pressed', String(state.signup.profession === profession.code));
        const name = document.createElement('span');
        name.textContent = profession.name;
        const tagline = document.createElement('span');
        tagline.className = 'row-status';
        tagline.textContent = profession.tagline;
        button.append(name, tagline);
        button.addEventListener('click', () => {
            state.signup.profession = profession.code;
            renderSignupProfession();
        });
        list.append(button);
    });
    UI.setButton($('signup-profession-next'), { label: 'التالي', enabled: state.signup.profession !== null });
}

function renderSignupEmail() {
    UI.show('signup-email');
    $('signup-email-input').value = state.signup.email;
}

function onSignupEmail(event) {
    event.preventDefault();
    const email = normalizeEmail($('signup-email-input').value);
    if (!emailIsValid(email)) {
        UI.showAlert(UI.screen('signup-email'), 'البريد غير صحيح. مثال: name@example.com');
        return;
    }
    state.signup.email = email;
    go(stepRoute('review'));
}

function professionName(code) {
    const found = state.choices.professions.find((p) => p.code === code);
    return found ? found.name : '';
}

function renderSignupReview() {
    const s = state.signup;
    UI.show('signup-review');
    $('signup-review-name').textContent = `الاسم: ${s.name}`;
    $('signup-review-birth').textContent = `تاريخ الميلاد: ${birthWords()}`;
    $('signup-review-profession').textContent = `المهنة: ${professionName(s.profession)}`;
    $('signup-review-email').textContent = s.email;
}

function renderSignupPassword() {
    UI.show('signup-password');
    $('signup-password-login').value = state.signup.email;
    UI.setButton($('signup-create'), { label: `أنشئ حسابي: ${professionName(state.signup.profession)}`, commit: true });
}

function onSignupReveal() {
    const field = $('signup-password-input');
    const shown = field.type === 'text';
    field.type = shown ? 'password' : 'text';
    $('signup-reveal').setAttribute('aria-pressed', String(!shown));
    $('signup-reveal').textContent = shown ? 'أظهر كلمة المرور' : 'أخفِ كلمة المرور';
}

/* رمز الخطأ من الخادم ← الخطوة التي يُصلَح فيها. */
const FIELD_STEPS = { NAME: 'name', BIRTH: 'year', EMAIL: 'email', TAKEN: 'email', PASSWORD: 'password', CONSENT: 'notice' };

async function onSignupCreate(event) {
    event.preventDefault();
    const section = UI.screen('signup-password');
    const s = state.signup;
    if (state.busy || !s || UI.alertOpen(section)) {
        return;
    }
    const password = $('signup-password-input').value;
    if (password.length < state.choices.registration.password_min) {
        UI.showAlert(section, `كلمة المرور من ${state.choices.registration.password_min} حرفاً على الأقل.`);
        return;
    }
    state.busy = true;
    const result = await api('POST', '/api/auth/register', {
        json: {
            code: s.code, name: s.name, birth_date: birthDate(), email: s.email,
            password, profession: s.profession, accept_terms: true,
        },
    });
    state.busy = false;
    if (result.status === 204) {
        state.signup = null;
        // انتقالٌ كامل لا تغيير وسم: هكذا يعرض Safari حفظ كلمة المرور.
        location.replace('/');
        return;
    }
    const field = result.data && result.data.field;
    if (result.data && result.data.code === 'REGISTER_CODE') {
        state.signup = null;
        UI.showAlert(renderLogin(), detail(result));
        return;
    }
    const step = FIELD_STEPS[field];
    if (step && step !== 'password') {
        s.alert = detail(result);
        go(stepRoute(step));
        return;
    }
    UI.showAlert(section, detail(result));
}

/* ── الحساب ─────────────────────────────────────────────────────────── */

/* سطر المهنة يحجز مكانه قبل قراءة البوابة: لا يتحرّك تحته زرٌّ حين تصل. */
async function renderAccount(nav) {
    UI.show('account');
    $('account-name').textContent = state.displayName ? `الاسم: ${state.displayName}` : 'بلا اسم';
    const profession = (portal) => (portal ? `المهنة: ${portal.name}` : '\u00a0');
    $('account-profession').textContent = profession(state.portal);
    $('account-passkey-status').textContent = '';
    $('account-passkey-help').hidden = !passkeysAvailable();
    offerPasskey('add', $('account-passkey'));
    const portal = await loadPortal({ fresh: true });
    if (nav !== state.nav) {
        return;
    }
    $('account-profession').textContent = profession(portal);
}

/* نسبة O*NET كاملةً كما يطلبها ترخيصه، ومصادر هذه البوابة بأسطرها. */
async function renderAccountSources(nav) {
    const section = UI.show('account-sources');
    const portal = await loadPortal();
    if (nav !== state.nav) {
        return;
    }
    if (!portal) {
        UI.showAlert(section, GENERIC);
        return;
    }
    $('account-attribution').textContent = portal.attribution;
    const lines = [...new Set([portal.sources.tasks, portal.sources.skills])].map((text) => {
        const line = document.createElement('p');
        line.className = 'help';
        line.textContent = text;
        return line;
    });
    $('account-source-lines').replaceChildren(...lines);
}

function renderAccountDelete() {
    UI.show('account-delete');
}

async function onAccountDelete() {
    const section = UI.screen('account-delete');
    if (state.busy || UI.alertOpen(section)) {
        return;
    }
    state.busy = true;
    const result = await api('POST', '/api/me/delete');
    state.busy = false;
    if (result.status === 204) {
        // كل ما في الذاكرة لصاحب حسابٍ لم يعد موجوداً: تحميلٌ جديد.
        location.replace('/');
        return;
    }
    if (result.status !== 401) {
        UI.showAlert(section, detail(result));
    }
}

/* ── مفاتيح المرور ──────────────────────────────────────────────────── */

/*
 * الخيارات — وفيها التحدّي — تُجلب حين تُعرض الشاشة، لا داخل الضغطة: WebKit قد
 * يشترط لهذا الطلب تفعيلاً من المستخدم، ومهلة التفعيل فيه خمس ثوانٍ، فجلبٌ داخل
 * الضغطة قد يستنفدها. فالضغطة تستدعي الجهاز قبل أيّ انتظار، ولا حقل يُركَّز:
 * نافذة النظام تعرض المفاتيح، ثم يؤكّد صاحب الجهاز بـFace ID أو Touch ID أو رمزه.
 *
 * والتحدّي لمرةٍ واحدة ومهلته في الخادم: بعد كل محاولةٍ — نجحت أو فشلت — تُجلب
 * خياراتٌ جديدة. والبايتات بين الخادم والمتصفّح base64url بلا حشو.
 */

const PASSKEY_OPTIONS = { login: '/api/auth/passkey/options', add: '/api/me/passkeys/options' };
const PASSKEY_NOT_READY = 'لم يجهز مفتاح المرور بعد. حاول مرة أخرى.';
// الجهاز لا يقول لماذا: إلغاءٌ، أو لا مفتاح لهذا الموقع، أو انتهاء المهلة — جوابٌ واحد عمداً.
const PASSKEY_NOT_SIGNED_IN = 'لم يكتمل الدخول بمفتاح المرور. إن لم يُضَف لحسابك مفتاحٌ بعد، '
    + 'فادخل بكلمة المرور، ثم أضفه من «حسابي».';
const PASSKEY_NOT_SAVED = 'لم يُحفظ مفتاح المرور. يحتاج سلسلة مفاتيح iCloud والمصادقة بخطوتين مفعّلتين، '
    + 'ثم تأكيداً بـFace ID أو Touch ID أو رمز الجهاز.';
const PASSKEY_ALREADY_HERE = 'في هذا الجهاز مفتاح مرورٍ لهذا الحساب من قبل.';
const PASSKEY_SAVED = 'حُفظ مفتاح المرور. ادخل به في المرة القادمة من شاشة الدخول.';

function passkeysAvailable() {
    return Boolean(window.PublicKeyCredential && navigator.credentials);
}

function fromBase64url(text) {
    const base64 = text.replace(/-/g, '+').replace(/_/g, '/');
    const binary = atob(base64 + '='.repeat((4 - (base64.length % 4)) % 4));
    return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

function toBase64url(buffer) {
    let binary = '';
    new Uint8Array(buffer).forEach((byte) => { binary += String.fromCharCode(byte); });
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/* خيارات الخادم بالشكل الذي يقبله المتصفّح: التحدّي والمعرّفات بايتات. */
function publicKeyOptions(json) {
    const options = { ...json, challenge: fromBase64url(json.challenge) };
    if (json.user) {
        options.user = { ...json.user, id: fromBase64url(json.user.id) };
    }
    ['allowCredentials', 'excludeCredentials'].forEach((key) => {
        if (json[key]) {
            options[key] = json[key].map((credential) => ({ ...credential, id: fromBase64url(credential.id) }));
        }
    });
    return options;
}

/* ردّ الجهاز بالأسماء التي يقرؤها الخادم (schemas.py)، ولا حقل غيرها. */
function credentialJson(credential, response) {
    const json = { id: credential.id, rawId: toBase64url(credential.rawId), type: credential.type, response };
    if (credential.authenticatorAttachment) {
        json.authenticatorAttachment = credential.authenticatorAttachment;
    }
    return json;
}

function assertionJson(credential) {
    const r = credential.response;
    const response = {
        clientDataJSON: toBase64url(r.clientDataJSON),
        authenticatorData: toBase64url(r.authenticatorData),
        signature: toBase64url(r.signature),
    };
    if (r.userHandle) {
        response.userHandle = toBase64url(r.userHandle);
    }
    return credentialJson(credential, response);
}

function attestationJson(credential) {
    const r = credential.response;
    return credentialJson(credential, {
        clientDataJSON: toBase64url(r.clientDataJSON),
        attestationObject: toBase64url(r.attestationObject),
        transports: typeof r.getTransports === 'function' ? r.getTransports() : [],
    });
}

/*
 * يجلب خياراتٍ جديدة لـ`kind` ويحفظها في `state.passkey`. ما يصل لطلبٍ أقدم
 * يُترك: الخيارات لآخر عرضٍ للشاشة.
 */
function preparePasskey(kind) {
    const ticket = { options: null, error: null };
    state.passkey[kind] = ticket;
    api('POST', PASSKEY_OPTIONS[kind]).then((result) => {
        if (result.status === 200) {
            ticket.options = publicKeyOptions(result.data);
        } else {
            ticket.error = detail(result);
        }
    });
}

/* الزرّ حيث يعمل مفتاح المرور، وخياراته تُجلب الآن؛ وإلا يبقى مكانه محجوزاً. */
function offerPasskey(kind, button) {
    const offered = passkeysAvailable();
    UI.setButton(button, { reserved: !offered });
    if (offered) {
        preparePasskey(kind);
    } else {
        state.passkey[kind] = null;
    }
}

/*
 * خيارات الضغطة، لمرةٍ واحدة. وإن لم تصل بعد أو فشل جلبها يُقال ذلك — وتُطلب من
 * جديد إن فشلت — فلا ضغطةٌ بلا أثر، ولا جلبٌ داخلها.
 */
function takePasskeyOptions(kind, section) {
    const ticket = state.passkey[kind];
    if (!ticket || state.busy || UI.alertOpen(section)) {
        return null;
    }
    if (!ticket.options) {
        UI.showAlert(section, ticket.error || PASSKEY_NOT_READY);
        if (ticket.error) {
            preparePasskey(kind);
        }
        return null;
    }
    state.passkey[kind] = null;
    return ticket.options;
}

async function onPasskeyLogin() {
    const section = UI.screen('login');
    const options = takePasskeyOptions('login', section);
    if (!options) {
        return;
    }
    state.busy = true;
    const credential = await navigator.credentials.get({ publicKey: options }).catch(() => null);
    const result = credential ? await api('POST', '/api/auth/passkey', { json: assertionJson(credential) }) : null;
    state.busy = false;
    if (result && result.status === 204) {
        // انتقالٌ كامل كالدخول بكلمة المرور: لا يبقى في الذاكرة شيءٌ من قبله.
        location.replace('/');
        return;
    }
    preparePasskey('login');
    if (!section.hidden) {
        UI.showAlert(section, result ? detail(result) : PASSKEY_NOT_SIGNED_IN);
    }
}

async function onPasskeyAdd() {
    const section = UI.screen('account');
    const options = takePasskeyOptions('add', section);
    if (!options) {
        return;
    }
    state.busy = true;
    $('account-passkey-status').textContent = '';
    let failure = PASSKEY_NOT_SAVED;
    const credential = await navigator.credentials.create({ publicKey: options }).catch((error) => {
        // أحد مفاتيح الحساب المسمّاة في الخيارات (excludeCredentials) على هذا الجهاز.
        if (error && error.name === 'InvalidStateError') {
            failure = PASSKEY_ALREADY_HERE;
        }
        return null;
    });
    const result = credential ? await api('POST', '/api/me/passkeys', { json: attestationJson(credential) }) : null;
    state.busy = false;
    // انتهت الجلسة (`api()` نقل إلى الدخول) أو غادر الشاشة: خياراتها تُجلب حين تُعرض.
    if ((result && result.status === 401) || section.hidden) {
        return;
    }
    preparePasskey('add');
    if (result && result.status === 204) {
        $('account-passkey-status').textContent = PASSKEY_SAVED;
    } else {
        UI.showAlert(section, result ? detail(result) : failure);
    }
}

/* ── البوابة ────────────────────────────────────────────────────────── */

/*
 * بوابة صاحب الحساب. `fresh` يقرؤها من جديد (الرئيسية والحساب): المشغّل قد
 * ينقل الحساب إلى مهنةٍ أخرى والتطبيق مفتوح. وإن تعذّرت القراءة بقي ما عُرف.
 */
async function loadPortal({ fresh = false } = {}) {
    if (state.portal && !fresh) {
        return state.portal;
    }
    const result = await api('GET', '/api/portal');
    if (result.status !== 200) {
        return state.portal;
    }
    state.portal = result.data;
    return state.portal;
}

async function renderPortalItem(kind, position, nav) {
    const portal = await loadPortal();
    if (nav !== state.nav) {
        return;
    }
    if (!portal) {
        go('#/', { replace: true });
        return;
    }
    const items = portal[kind];
    const n = Math.min(Math.max(1, position), items.length);
    if (n !== position) {
        go(`#/${kind}/${n}`, { replace: true });
        return;
    }
    UI.show('portal-item');
    const item = items[n - 1];
    const tasks = kind === 'tasks';
    $('portal-item-heading').textContent = tasks ? `مهامّ ${portal.name}` : `مهارات ${portal.name}`;
    $('portal-item-position').textContent = `${tasks ? 'المهمة' : 'المهارة'} ${n} من ${items.length}`;
    $('portal-item-text').textContent = item.text;
    $('portal-item-note').textContent = item.note || '';
    $('portal-item-note').hidden = !item.note;
    const mode = tasks ? MODE_LABELS[item.mode] : null;
    $('portal-item-mode').textContent = mode || '';
    $('portal-item-mode').hidden = !mode;
    $('portal-item-mode').dataset.mode = tasks ? item.mode : '';
    $('portal-item-source').textContent = portal.sources[kind];
    UI.setButton($('portal-item-previous'), { label: 'السابق', reserved: n <= 1 });
    UI.setButton($('portal-item-next'), { label: 'التالي', reserved: n >= items.length });
    $('portal-item-previous').dataset.target = `#/${kind}/${n - 1}`;
    $('portal-item-next').dataset.target = `#/${kind}/${n + 1}`;
}

/*
 * المسارات التي يعرفها هذا الملف. `true` إن عالج الوسم. `nav` رقم الانتقال
 * (app.js): ما وصل بعد انتقالٍ أحدث لا يرسم شيئاً.
 */
async function routePortal(hash, nav) {
    const signup = hash.match(/^#\/signup(?:\/([a-z]+))?$/);
    if (signup) {
        await renderSignup(signup[1] || 'notice', nav);
        return true;
    }
    if (hash === '#/account') {
        await renderAccount(nav);
        return true;
    }
    if (hash === '#/account/sources') {
        await renderAccountSources(nav);
        return true;
    }
    if (hash === '#/account/delete') {
        renderAccountDelete();
        return true;
    }
    if (hash === '#/account/logout') {
        UI.show('account-logout');
        return true;
    }
    const item = hash.match(/^#\/(tasks|skills)\/([0-9]{1,3})$/);
    if (item) {
        await renderPortalItem(item[1], Number(item[2]), nav);
        return true;
    }
    return false;
}

function wirePortal() {
    $('signup-agree').addEventListener('click', () => {
        state.signup.agreed = true;
        go(stepRoute('name'));
    });
    $('signup-name-form').addEventListener('submit', onSignupName);
    ['signup-year', 'signup-month', 'signup-day'].forEach((name) => {
        const set = { 'signup-year': setYear, 'signup-month': setMonth, 'signup-day': setDay }[name];
        $(`${name}-down`).addEventListener('click', (e) => set(Number(e.currentTarget.dataset.value)));
        $(`${name}-up`).addEventListener('click', (e) => set(Number(e.currentTarget.dataset.value)));
    });
    $('signup-year-next').addEventListener('click', () => go(stepRoute('month')));
    $('signup-month-next').addEventListener('click', () => go(stepRoute('day')));
    $('signup-day-next').addEventListener('click', () => go(stepRoute('profession')));
    $('signup-profession-next').addEventListener('click', () => go(stepRoute('email')));
    $('signup-email-form').addEventListener('submit', onSignupEmail);
    $('signup-review-next').addEventListener('click', () => go(stepRoute('password')));
    $('signup-password-form').addEventListener('submit', onSignupCreate);
    $('signup-reveal').addEventListener('click', onSignupReveal);

    $('home-account').addEventListener('click', () => go('#/account'));
    $('home-tasks').addEventListener('click', () => go('#/tasks/1'));
    $('home-skills').addEventListener('click', () => go('#/skills/1'));
    $('login-passkey').addEventListener('click', onPasskeyLogin);
    $('account-passkey').addEventListener('click', onPasskeyAdd);
    $('account-logout').addEventListener('click', () => go('#/account/logout'));
    $('account-logout-back').addEventListener('click', () => go('#/account'));
    $('account-logout-yes').addEventListener('click', onLogout);
    $('account-delete').addEventListener('click', () => go('#/account/delete'));
    $('account-sources').addEventListener('click', () => go('#/account/sources'));
    $('account-delete-back').addEventListener('click', () => go('#/account'));
    $('account-delete-yes').addEventListener('click', onAccountDelete);
    $('portal-item-previous').addEventListener('click', (e) => go(e.currentTarget.dataset.target));
    $('portal-item-next').addEventListener('click', (e) => go(e.currentTarget.dataset.target));
}
