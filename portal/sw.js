/*
 * عامل الخدمة — العمل دون اتصال
 * ==============================
 * يخزّن قشرة التطبيق فقط. **لا يخزّن أي استجابة من `/patient/*`**: تخزين
 * محتوى سريري في ذاكرة المتصفح يعني احتمال تسليم خطة بعد أن سُحب اعتمادها أو
 * انتهت صلاحيتها — أي التفافاً على نقطة العبور.
 *
 * آخر خطة معتمدة تبقى قابلة للقراءة عبر تخزين صريح يديره `app.js`، لا عبر
 * تخزين شبكي ضمني.
 *
 * القشرة تُطلب من الشبكة أولاً والذاكرة احتياط. العكس — الذاكرة أولاً — يُبقي
 * على جهاز المريض نسخةً قديمة من الواجهة إلى أن يتغيّر اسم المخزن يدوياً،
 * فيظلّ عيبٌ أُصلح يعمل عنده. في واجهة سريرية هذا ثمن لا يُدفع مقابل طلب
 * شبكي واحد.
 */

const SHELL = 'symbol-shell-v2';
const ASSETS = ['./', 'index.html', 'styles.css', 'app.js', 'manifest.webmanifest'];

self.addEventListener('install', (event) => {
    event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(ASSETS)));
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((key) => key !== SHELL).map((key) => caches.delete(key)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;

    // المحتوى السريري لا يُخزَّن ولا يُخدم من الذاكرة — يمر إلى الشبكة دائماً
    if (url.pathname.startsWith('/patient/')) return;

    event.respondWith((async () => {
        try {
            const fresh = await fetch(event.request);
            if (fresh.ok) (await caches.open(SHELL)).put(event.request, fresh.clone());
            return fresh;
        } catch (disconnected) {
            const hit = await caches.match(event.request);
            if (hit) return hit;
            throw disconnected;
        }
    })());
});
