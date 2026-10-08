/*
 * صياغة — أدوات التفاعل بالنظر
 * ===========================
 * أدواتٌ لا تعرف شيئاً عن الحملات: إطار الشاشة، والتنبيه الذي يُقرّ، وزرّ
 * التقدّم الذي لا يعمل قبل الاختيار، ومجموعة الخيارات.
 *
 * القواعد التي تحكم كل ما هنا:
 *   • التفعيل بـclick وحده، على عناصر أصلية. لا pointerdown ولا hover ولا
 *     سحب: النظر لا يضغط ويسحب، وهل يُطلق مؤشره حدث مرورٍ في الصفحة لا يُعرف
 *     قبل بوابة الإصدار 0.
 *   • لا مؤقّتات: النظام يملك زمن المكوث، والمستخدم ضبطه بنفسه.
 *   • النصّ بـtextContent وحده.
 *   • التركيز على عنوان الشاشة عند تغيّرها، لا على زرّ: التركيز ليس تفعيلاً
 *     لكنه يعلن الشاشة لقارئ الشاشة.
 */

'use strict';

const UI = (() => {
    const screens = () => Array.from(document.querySelectorAll('.screen'));

    function screen(name) {
        return document.querySelector(`.screen[data-screen="${name}"]`);
    }

    function show(name) {
        let shown = null;
        screens().forEach((section) => {
            const match = section.dataset.screen === name;
            section.hidden = !match;
            if (match) {
                shown = section;
            }
        });
        clearAlert(shown);
        const heading = Array.from(shown.querySelectorAll('h2')).find((h) => !h.closest('[hidden]'));
        if (heading) {
            heading.focus({ preventScroll: true });
        }
        return shown;
    }

    /*
     * زرٌّ يتغيّر نصّه ووظيفته وحالته. `commit` يُعلَّم بـdata-commit:
     * اختبار الهبوط يرفض أن يقع زرٌّ كهذا تحت نقطة ضغطٍ سابقة.
     * `reserved` يُخفيه ويُبقي مكانه، فلا يتحرّك ما حوله.
     */
    function setButton(button, { label, enabled = true, commit = false, reserved = false } = {}) {
        if (label !== undefined) {
            button.textContent = label;
        }
        button.disabled = !enabled || reserved;
        button.classList.toggle('is-reserved', reserved);
        button.classList.toggle('btn--commit', commit);
        if (commit) {
            button.dataset.commit = '';
            delete button.dataset.safe;
        } else {
            button.dataset.safe = '';
            delete button.dataset.commit;
        }
    }

    /*
     * تنبيهٌ يبقى حتى «حسناً»، وأزرار الشريط السفلي معطّلةٌ ما دام ظاهراً:
     * نظرةٌ باقية على الزرّ الذي فشل لا تعيد طلباً مدفوعاً.
     */
    function showAlert(section, message) {
        const alert = section.querySelector('.alert');
        if (!alert) {
            // شاشةٌ بلا تنبيه تُسكت الخطأ؛ فشلٌ صريح يُكتشف في الاختبار.
            throw new Error(`الشاشة ${section.dataset.screen} بلا عنصر تنبيه`);
        }
        alert.querySelector('.alert__text').textContent = message;
        alert.hidden = false;
        // «حسناً» وحدها مفعّلة: فوق وسط الشريط العلوي، حيث لا زرّ في أيّ شاشة.
        section.querySelectorAll('.bar .btn').forEach((control) => {
            // الرابط لا يعرف disabled: يُقفل بـaria-disabled ولا يقبل نقرة (styles.css).
            if (control.tagName === 'A') {
                if (control.getAttribute('aria-disabled') !== 'true') {
                    control.dataset.lockedByAlert = '';
                    control.setAttribute('aria-disabled', 'true');
                    control.tabIndex = -1;
                }
            } else if (!control.disabled) {
                control.dataset.lockedByAlert = '';
                control.disabled = true;
            }
        });
    }

    function clearAlert(section) {
        if (!section) {
            return;
        }
        const alert = section.querySelector('.alert');
        if (alert) {
            alert.hidden = true;
        }
        section.querySelectorAll('[data-locked-by-alert]').forEach((control) => {
            delete control.dataset.lockedByAlert;
            if (control.tagName === 'A') {
                control.removeAttribute('aria-disabled');
                control.removeAttribute('tabindex');
            } else {
                control.disabled = false;
            }
        });
    }

    function alertOpen(section) {
        const alert = section.querySelector('.alert');
        return Boolean(alert && !alert.hidden);
    }

    /*
     * مجموعة خياراتٍ بأزرارٍ مطلقة القيمة: الضغط على المختار نفسه لا يفعل شيئاً،
     * فالضغطة المكرّرة بالنظر لا تغيّر شيئاً.
     */
    function choiceGroup(container, options, selected, onPick) {
        container.replaceChildren();
        options.forEach((option) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn chip';
            button.textContent = option.label;
            // مفتاحٌ ثابت للخيار: يُعاد بناء الأزرار بعد كل اختيار، والمفتاح
            // يقول إنه الخيار نفسه في مكانه.
            button.dataset.key = String(option.value);
            button.setAttribute('aria-pressed', String(option.value === selected));
            if (option.disabled) {
                button.disabled = true;
            }
            button.addEventListener('click', () => {
                if (button.getAttribute('aria-pressed') !== 'true') {
                    onPick(option.value);
                }
            });
            container.append(button);
        });
    }

    function bdi(text) {
        const element = document.createElement('bdi');
        element.textContent = text;
        return element;
    }

    return { screen, show, setButton, showAlert, clearAlert, alertOpen, choiceGroup, bdi };
})();
