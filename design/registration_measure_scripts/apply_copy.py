"""Apply the proposed open-registration copy to a scratch copy of index.html.

    python3 apply_copy.py <path/to/index.html>
"""

from __future__ import annotations

import sys
from pathlib import Path

NOTICE_L1_OLD = ("يُحفظ في هذا التطبيق: الاسم، وتاريخ الميلاد، والمهنة، وكلمة المرور مجزّأة،"
                 " وبصمة البريد لا البريد، فلا يصله شيء ولا يُستردّ الحساب به.")
NOTICE_L1_NEW = ("يُحفظ في هذا التطبيق: الاسم، وتاريخ الميلاد، والمهنة، وكلمة المرور مجزّأة،"
                 " وبصمة البريد لا البريد؛ ومن يعرفه يعرف أن له حساباً هنا.")
NOTICE_L3_OLD = ("تحذف حسابك وبياناته متى شئت، أو يحذفه بطلبك مَن أعطاك الرابط إن أُوقف أو نسيت كلمة مرورك؛"
                 " والنسخ الاحتياطية الأقدم تبقى حتى تُحذف.")
NOTICE_L3_NEW = ("تحذف حسابك وبياناته متى شئت، أو يستردّه أو يحذفه مشغّل التطبيق إن كتبتَ إليه"
                 " من بريدك هذا؛ والنسخ الاحتياطية الأقدم تبقى حتى تُحذف.")

LOGIN_HELP_OLD = '<p class="help">تعذّر الدخول؟ اطلب رابطاً جديداً ممّن دعاك أو أعطاك رابط التسجيل.</p>'
LOGIN_HELP_NEW = '<p class="help" id="login-help">تعذّر الدخول؟ اطلب رابطاً جديداً ممّن دعاك أو أعطاك رابط التسجيل.</p>'

LOGIN_FOOTER_OLD = """            <div class="alert" role="alert" hidden><p class="alert__text"></p><button class="btn" type="button" data-ack data-safe>حسناً</button></div>
        </form>
        <footer class="bar bar--bottom"><div class="slot"></div><div class="slot"></div></footer>
    </section>

    <section class="screen" data-screen="activate" hidden>"""
LOGIN_FOOTER_NEW = """            <div class="alert" role="alert" hidden><p class="alert__text"></p><button class="btn" type="button" data-ack data-safe>حسناً</button></div>
        </form>
        <!-- «أنشئ حساباً» في الطرف الأسفل الأيمن: موضعه في «قبل أن تبدأ» منطقةٌ ميتة، و«رجوع»
             هناك في الطرف الأعلى الأيمن يعود إلى هنا حيث لا شيء. مخفيٌّ إلا في التسجيل المفتوح. -->
        <footer class="bar bar--bottom">
            <div class="slot"><button class="btn" type="button" id="login-signup" data-safe hidden>أنشئ حساباً</button></div>
            <div class="slot"></div>
        </footer>
    </section>

    <section class="screen" data-screen="activate" hidden>"""

EMAIL_OLD = """                <label class="label" for="signup-email-input">يكون اسم دخولك</label>
                <input class="field" id="signup-email-input" type="email" inputmode="email" autocomplete="email"
                       autocapitalize="none" autocorrect="off" spellcheck="false" enterkeyhint="next" dir="ltr" required>
            </div>"""
EMAIL_NEW = EMAIL_OLD + """
            <p class="help">من يعرف هذا البريد يستطيع أن يعرف أن له حساباً هنا؛ فإن شئت فاختر بريداً لك لا يعرفه غيرك.</p>"""

REVIEW_OLD = ('<p class="help">لا يصل هذا البريدَ شيء، ولا يُستردّ الحساب به.'
              ' إن نُسيت كلمة المرور فرابطٌ جديد ممّن أعطاك رابط التسجيل.</p>')
REVIEW_NEW = '<p class="help">لا يصل هذا البريدَ شيء. إن نسيت كلمة المرور فاكتب إلى مشغّل التطبيق من هذا البريد.</p>'

PROFESSION_OLD = '<p class="help">تُفتح بها بوابتك. تغييرها بعد التسجيل بطلبٍ ممّن أعطاك الرابط.</p>'
PROFESSION_NEW = '<p class="help">تُفتح بها بوابتك. تغييرها بعد التسجيل بطلبٍ إلى مشغّل التطبيق.</p>'

EDITS = [
    (NOTICE_L1_OLD, NOTICE_L1_NEW),
    (NOTICE_L3_OLD, NOTICE_L3_NEW),
    (LOGIN_HELP_OLD, LOGIN_HELP_NEW),
    (LOGIN_FOOTER_OLD, LOGIN_FOOTER_NEW),
    (EMAIL_OLD, EMAIL_NEW),
    (REVIEW_OLD, REVIEW_NEW),
    (PROFESSION_OLD, PROFESSION_NEW),
]


def main() -> int:
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    for old, new in EDITS:
        count = text.count(old)
        if count != 1:
            print(f"expected one occurrence, found {count}: {old[:60]}", file=sys.stderr)
            return 1
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("applied", len(EDITS), "edits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
