import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()

def swap(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)

swap('''- **Code of record.** HEAD `fa84cd1` on `omar/symbol-rehab-phase-0-audit-crwci6`, which PR #10 brings to `main` (`origin/main` is `0171655`). Migration 0007 builds on HEAD's 0001–0006. Its down migration restores HEAD's 0005 functions word for word.
- **Work in progress by others.** The working tree has uncommitted changes that are not this track's:
  - The notice merges its first two lines.
  - `TERMS_VERSION` goes to `2026-10-09`, with digest `baba6ba6…`. I reproduced that digest exactly from the in-flight text.
  - A sign-out confirmation screen.
  - `eyework/client/`, a 21st.dev port (task #20).

  This spec's notice is that in-flight text plus two edits (§9). If the in-flight change doesn't land, apply the same two edits to whatever ships, then measure again (§10.4).
- **No welcome screen in HEAD.** The sign-in screen alone is enough to open registration. §8.3 sets the rules a welcome screen's entry must meet if the design track adds one.''',
'''- **Code of record.** `origin/main` at `d543356` (PR #10 merged). It contains:
  - migrations 0001–0006, unchanged since `fa84cd1`. Migration 0007 builds on them, and its down migration restores their 0005 functions word for word;
  - the notice at `TERMS_VERSION = "2026-10-09"`, digest `baba6ba6…`, from `03a12ec`;
  - the two-step sign-out, also from `03a12ec`.
- **What my measurements ran on.** The static client from `fa84cd1`, with main's notice text applied. I reproduced the `2026-10-09` digest exactly from that text. Between `fa84cd1` and `d543356`, the sign-in markup and `styles.css` did not change (checked with `git diff`), so the measurements hold for main.
- **This spec's notice** is main's text plus two edits (§9). If main's text changes before this lands, apply the same two edits and run the checks in §10.4 again.
- **The React client.** `a519ddb` on the working branch adds `eyework/client`: a Vite, React and shadcn client with the 21st.dev AuthForm and DropdownNavigation. FastAPI does not serve it yet; the static pages stay the app until the redesign moves screens over. §8.5 says what the client needs from this spec.
- **No welcome screen on main.** The sign-in screen alone is enough to open registration. §8.3 sets the rules a welcome screen's entry must meet if the design track adds one.''')

swap('''**Back from the notice.** `signupParent('signup-notice')` returns `'#/welcome'` when `state.signup.from === 'welcome'`, otherwise `'#/login'`.''',
'''**Back from the notice.** `signupParent('signup-notice')` returns `'#/welcome'` when `state.signup.from === 'welcome'`, otherwise `'#/login'`.

**Entry from outside this page: `#/signup/new`.** The React AuthForm's «ابدأ التسجيل» and any link opened from a home-screen shortcut need a way to start a sign-up without a link. They use this route.

- `renderSignup('new')` is handled before the `!state.signup` check:
  - in `open` mode: `state.signup = blankSignup(null, 'login'); go('#/signup', { replace: true });`, with no alert;
  - otherwise: sign-in with `detail` of `REGISTER_LINK` or `REGISTER_CLOSED`, taken from the mode in choices.
- `new` matches the existing route pattern (`[a-z]+`) and is not a step name, so step order is unaffected.''')

swap('''### 8.5 21st.dev''', '''### 8.5 21st.dev and the React client''')

swap('''- **The gaze contract overrides component defaults.** The usual 21st.dev «Don't have an account? Sign up» inline text link would fail it: the target is too small and it often sits next to the commit button. It must become the full 72×72 button in the top-end slot described above, with the same id (`login-signup`). The rules in §8.3 apply to any 21st.dev hero or welcome block.''',
'''- **The gaze contract overrides component defaults.** The usual 21st.dev «Don't have an account? Sign up» inline text link would fail it: the target is too small and it often sits next to the commit button. It must become the full 72×72 button in the top-end slot described above, with the same id (`login-signup`). The rules in §8.3 apply to any 21st.dev hero or welcome block.
- **The React AuthForm (`a519ddb`).** It already starts the step-by-step sign-up rather than a six-field form: the «حساب جديد» tab, then «ابدأ التسجيل». When it is served, it needs four things:
  1. `onStartSignup` goes to `/#/signup/new`, not `/#/signup`. Under this spec, a bare `#/signup` with no sign-up in memory is the "page reloaded" path and shows that alert.
  2. It reads `registration.mode` from `/api/choices`. It shows «حساب جديد» only in `open` mode. In `code` mode, the panel says «التسجيل هنا برابطٍ ممّن يدير التطبيق.» and has no start button. In `closed` mode the tab is hidden.
  3. The consent rule in §8.3 applies to its «ابدأ التسجيل». After the press, the notice's «أوافق وأتابع» must not be the nearest control to the pressed spot. In the current layout that button is full width in the content area, so this must be measured once the client is served.
  4. The two clients name the entry differently: «أنشئ حساباً» on the static sign-in screen, as the owner's brief says, and «حساب جديد» as the React tab. The design track should pick one name when it moves the screens.''')

swap('''**`TERMS_VERSION`** becomes the release date of this change.

- It must be later than every key already in `DIGESTS`: `2026-10-08`, and `2026-10-09` if the in-flight change ships first.
- Add `"<that date>": "30af143d…"` to `DIGESTS` and keep the old entries.
- The shape check allows one version per day. If this change is released together with the still-unreleased in-flight text, they may share one new date with this digest. Precedent: `fa84cd1` replaced the digest of an unreleased version.''',
'''**`TERMS_VERSION`** becomes the release date of this change.

- It must be later than every key already in `DIGESTS` on main: `2026-10-08` and `2026-10-09`.
- Add `"<that date>": "30af143d…"` to `DIGESTS` and keep the old entries.
- The shape check allows one version per day. If no account has ever accepted `2026-10-09` (it is on main, but may not be deployed), this text may take that date with the new digest instead. Precedent: `fa84cd1` replaced the digest of an unreleased version. That choice is decision 7.''')

swap('''7. **The `TERMS_VERSION` date.** Should this notice ship together with the unreleased in-flight text under one new date, or as its own version after it?''',
'''7. **The `TERMS_VERSION` date.** If no account has ever accepted `2026-10-09`, should this notice take that date (replacing its digest), or ship as its own later version?''')

swap('''12. `test_a_second_press_while_the_check_is_in_flight_sends_nothing_more`: *with the route held by `page.route`, a double press sends exactly one GET.*''',
'''12. `test_a_second_press_while_the_check_is_in_flight_sends_nothing_more`: *with the route held by `page.route`, a double press sends exactly one GET.*
13. `test_the_new_sign_up_route_starts_without_a_link_and_without_an_alert`: *in `open` mode, `goto('/#/signup/new')` leads to the notice with no alert and one GET to the check route. In `code` mode it leads to sign-in with «التسجيل هنا برابطٍ ممّن يدير التطبيق. اطلبه منه.».*''')

swap('''- **Verified before writing.**''', '''- **Baseline.** `origin/main` `d543356` (§1).
- **Verified before writing.**''')

open(p, 'w', encoding='utf-8').write(s)
print('updated')
