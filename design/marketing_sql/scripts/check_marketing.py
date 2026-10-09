"""Functional checks of NEXT_marketing on the scratch database, run as the real web role (eyework_app).

Run after scripts/cycle.sh, which leaves mkt_spec_test at 0008. Prints one line per check and a total.
"""

from __future__ import annotations

import datetime
import hashlib
import sys
import threading
import time
from pathlib import Path

import psycopg
from psycopg import errors

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "base"))
from eyework.tests.conftest import as_user, make_user, sample_jpeg  # noqa: E402

DB = "mkt_spec_test"
OWNER = f"postgresql://eyework_owner:eyework_dev_owner@localhost:5432/{DB}"
APP = f"postgresql://eyework_app:eyework_dev_app@localhost:5432/{DB}"

owner = psycopg.connect(OWNER, autocommit=True)
app = psycopg.connect(APP, autocommit=True)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def raises(name: str, constraint: str | None, fn, *, sqlstate: str | None = None) -> None:
    try:
        fn()
    except psycopg.Error as exc:
        got = exc.diag.constraint_name
        state = exc.sqlstate
        ok = (constraint is None or got == constraint) and (sqlstate is None or state == sqlstate)
        check(name, ok, f"got constraint={got} sqlstate={state}")
        return
    check(name, False, "no error")


def one(sql: str, params=(), conn=None):
    conn = conn or app
    return conn.execute(sql, params).fetchone()


def today() -> datetime.date:
    return one("SELECT (now() AT TIME ZONE 'Asia/Riyadh')::date", conn=owner)[0]


def clean() -> None:
    owner.execute("TRUNCATE users, attempt_tombstones RESTART IDENTITY CASCADE")


def user(login: str, profession: str = "MARKETING") -> object:
    return make_user(owner, login=login.encode(), profession=profession)


def new_campaign(uid, name="حملة الشتاء") -> object:
    as_user(app, uid)
    return one("SELECT ew_mkt_campaign_create(%s)", (name,))[0]


def rv(table: str, rid) -> int:
    return one(f"SELECT row_version FROM {table} WHERE id = %s", (rid,), conn=owner)[0]


def save_plan(cid, *, name="حملة الشتاء", brief=None, goal="SALES", kpi=("ORDERS", 50), audience=None,
              budget=500000, starts=None, ends=None):
    starts = starts or today() - datetime.timedelta(days=5)
    ends = ends or today() + datetime.timedelta(days=20)
    return one("SELECT ew_mkt_campaign_save(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
               (cid, rv("mkt_campaigns", cid), name, brief, goal, kpi[0] if kpi else None,
                kpi[1] if kpi else None, audience, budget, starts, ends))[0]


def set_channels(cid, channels, allocations):
    return one("SELECT ew_mkt_set_channels(%s,%s,%s,%s)", (cid, rv("mkt_campaigns", cid), channels, allocations))[0]


def flags_campaign(cid) -> list[str]:
    return [r[0] for r in app.execute("SELECT flag_key FROM ew_mkt_campaign_flags(%s)", (cid,)).fetchall()]


def approve_campaign(cid, ack=None):
    ack = flags_campaign(cid) if ack is None else ack
    return one("SELECT ew_mkt_campaign_transition(%s,%s,'APPROVED',%s)", (cid, rv("mkt_campaigns", cid), ack))[0]


def new_item(cid, channel="INSTAGRAM", day=None, at=None, body="منشورٌ عن تشكيلة الشتاء الجديدة.", warnings=(),
             spend=None, source=None):
    day = day or today() + datetime.timedelta(days=1)
    return one("SELECT ew_mkt_item_create(%s,%s,%s,%s,%s,%s,%s,%s)",
               (cid, channel, day, at, body, list(warnings), spend, source))[0]


def flags_item(iid) -> list[str]:
    return [r[0] for r in app.execute("SELECT flag_key FROM ew_mkt_item_flags(%s)", (iid,)).fetchall()]


def item_to(iid, to, ack=None, published_at=None):
    if ack is None and to == "APPROVED":
        ack = flags_item(iid)
    return one("SELECT ew_mkt_item_transition(%s,%s,%s,%s,%s)",
               (iid, rv("mkt_items", iid), to, ack or [], published_at))[0]


def save_results(cid, channel, start, end, spend=None, impressions=None, clicks=None, leads=None, orders=None,
                 revenue=None, ack=None, result=None):
    if ack is None:
        ack = [r[0] for r in app.execute("SELECT flag_key FROM ew_mkt_results_flags(%s,%s,%s,%s)",
                                         (cid, channel, result, spend)).fetchall()]
    expected = rv("mkt_results", result) if result else None
    return one("SELECT ew_mkt_results_save(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
               (cid, channel, result, expected, start, end, spend, impressions, clicks, leads, orders, revenue,
                ack))[0]


def ready_product_ad(uid) -> tuple[object, str]:
    """A READY product ad made the way the product tool makes it (0002 path), for the source checks."""
    as_user(app, uid)
    cid = one("INSERT INTO campaigns (user_id) VALUES (%s) RETURNING id", (uid,))[0]
    jpeg = sample_jpeg()
    app.execute("INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
                " VALUES (%s, %s, %s, 400, 400, %s)", (cid, uid, jpeg, hashlib.sha256(jpeg).digest()))
    attempt = one("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (cid,))[0]
    title, description = "حقيبة جلدية بنية أنيقة", "حقيبة يد من الجلد البني بتصميمٍ بسيط وأنيق، تتّسع للأغراض اليومية."
    app.execute("INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description, served_model,"
                " prompt_version) VALUES (%s,%s,%s,%s,%s,'claude-opus-5-5','test')",
                (cid, uid, attempt, title, description))
    app.execute("SELECT ew_finish_generation(%s,'OK',10,10)", (attempt,))
    version = one("SELECT current_version_id FROM campaigns WHERE id = %s", (cid,))[0]
    app.execute("UPDATE campaigns SET status = 'COPY_APPROVED' WHERE id = %s", (cid,))
    app.execute("UPDATE campaigns SET budget_sar = 500 WHERE id = %s", (cid,))
    app.execute("UPDATE campaigns SET days = 7 WHERE id = %s", (cid,))
    app.execute("UPDATE campaigns SET status = 'READY' WHERE id = %s", (cid,))
    assert version
    return cid, f"{title}\n{description}"


# ════════════════════════════════════════════════════════════════════════
clean()
T = today()
a = user("mkt-a")
b = user("mkt-b")
s = user("store-a", "STOREKEEPER")

# 1. Only a MARKETING account writes.
as_user(app, s)
raises("1 storekeeper cannot create a campaign", "mkt_needs_marketing",
       lambda: one("SELECT ew_mkt_campaign_create('حملة')"))

# 2. Isolation.
ca = new_campaign(a)
as_user(app, b)
check("2a another account does not see the campaign", one("SELECT count(*) FROM mkt_campaigns")[0] == 0)
raises("2b another account cannot save it", None,
       lambda: one("SELECT ew_mkt_campaign_save(%s,1,'x y',NULL,NULL,NULL,NULL,NULL,0,NULL,NULL)", (ca,)),
       sqlstate="P0002")
raises("2c another account cannot read its flags", None,
       lambda: app.execute("SELECT * FROM ew_mkt_campaign_flags(%s)", (ca,)).fetchall(), sqlstate="P0002")
as_user(app, None)
check("2d no session sees nothing", one("SELECT count(*) FROM mkt_campaigns")[0] == 0)

# 3. No direct writes for the web role.
as_user(app, a)
for stmt, label in [
    ("INSERT INTO mkt_campaigns (user_id, name) VALUES ('%s', 'abc')" % a, "insert"),
    ("UPDATE mkt_campaigns SET name = 'abc'", "update"),
    ("DELETE FROM mkt_campaigns", "delete"),
    ("TRUNCATE mkt_results", "truncate"),
    ("INSERT INTO mkt_ai_flags (item_id, user_id, body_digest, ordinal, kind, quote, reason)"
     " VALUES (gen_random_uuid(), '%s', '\\x00', 1, 'HEALTH', 'ab', 'x')" % a, "insert flag"),
    ("UPDATE mkt_review_calls SET outcome = 'OK'", "update ledger"),
]:
    raises(f"3 web role cannot {label}", None, lambda stmt=stmt: app.execute(stmt), sqlstate="42501")
for fn in ["SELECT ew_mkt_require()", f"SELECT ew_mkt_lock_campaign('{a}', '{ca}', 1)", "SELECT ew_ai_spend(false)"]:
    raises(f"3 web role cannot execute {fn.split('(')[0][7:]}", None, lambda fn=fn: app.execute(fn), sqlstate="42501")

# 4. Plan: save, stale, KPI rules, text rules, dates.
as_user(app, a)
save_plan(ca, kpi=None)
raises("4a stale row version is refused", "mkt_stale",
       lambda: one("SELECT ew_mkt_campaign_save(%s,1,'حملة الشتاء',NULL,'SALES',NULL,NULL,NULL,0,NULL,NULL)", (ca,)))
raises("4b KPI must fit the goal", "mkt_kpi_fits_goal", lambda: save_plan(ca, goal="AWARENESS", kpi=("ORDERS", 5)))
raises("4c KPI needs a target", "mkt_kpi_complete",
       lambda: one("SELECT ew_mkt_campaign_save(%s,%s,'حملة الشتاء',NULL,'SALES','ORDERS',NULL,NULL,0,NULL,NULL)",
                   (ca, rv("mkt_campaigns", ca))))
raises("4d a bidi control in the name is refused", "mkt_campaign_name", lambda: save_plan(ca, name="حملة‮الشتاء"))
raises("4e surrounding space is refused", "mkt_campaign_name", lambda: save_plan(ca, name=" حملة"))
raises("4f a non-NFC name is refused", "mkt_campaign_name", lambda: save_plan(ca, name="Café حملة"))
raises("4g end before start is refused", "mkt_dates_order",
       lambda: save_plan(ca, starts=T, ends=T - datetime.timedelta(days=1)))
raises("4h a span over a year is refused", "mkt_dates_span",
       lambda: save_plan(ca, starts=T, ends=T + datetime.timedelta(days=400)))
raises("4i a start more than two years ahead is refused", "mkt_dates_range",
       lambda: save_plan(ca, starts=T + datetime.timedelta(days=800), ends=T + datetime.timedelta(days=801)))
raises("4j a multi-line audience is refused", "mkt_campaign_audience", lambda: save_plan(ca, audience="نساء\nالرياض"))
save_plan(ca, kpi=None, brief="تشكيلة الشتاء\nخصم للأعضاء", audience="نساءٌ في الرياض")
check("4k a multi-line brief is accepted",
      one("SELECT brief FROM mkt_campaigns WHERE id = %s", (ca,))[0] == "تشكيلة الشتاء\nخصم للأعضاء")

# 5. Channels and allocations.
raises("5a approval needs a channel", "mkt_plan_incomplete", lambda: approve_campaign(ca, []))
raises("5b allocations over the budget are refused", "mkt_allocations_over_budget",
       lambda: set_channels(ca, ["INSTAGRAM", "X"], [300000, 300000]))
raises("5c a duplicated channel is refused", "mkt_channels_shape",
       lambda: set_channels(ca, ["INSTAGRAM", "INSTAGRAM"], [1, 1]))
raises("5d an unknown channel is refused", "mkt_channel_known", lambda: set_channels(ca, ["FAX"], [1]))
raises("5e a negative allocation is refused", "mkt_allocation_range", lambda: set_channels(ca, ["X"], [-1]))
set_channels(ca, ["INSTAGRAM", "X"], [300000, 200000])
raises("5f the budget cannot drop below the allocations", "mkt_allocations_over_budget",
       lambda: save_plan(ca, kpi=None, budget=400000))
set_channels(ca, ["INSTAGRAM", "X"], [200000, 300000])
check("5g moving money between channels within the budget passes",
      one("SELECT sum(allocated_halalas) FROM mkt_campaign_channels WHERE campaign_id = %s", (ca,))[0] == 500000)
raises("5h owner cannot exceed the budget either (deferred check)", "mkt_allocations_over_budget",
       lambda: owner.execute("UPDATE mkt_campaign_channels SET allocated_halalas = 999999 WHERE campaign_id = %s"
                             " AND channel = 'X'", (ca,)))

# 6. Plan approval with flags.
as_user(app, a)
keys = flags_campaign(ca)
check("6a a plan without KPI carries NO_KPI", keys == ["NO_KPI"], str(keys))
raises("6b approval without acknowledging is refused", "mkt_flags_changed", lambda: approve_campaign(ca, []))
approve_campaign(ca)
check("6c approval stores the acknowledged keys",
      one("SELECT status, approved_with_flags FROM mkt_campaigns WHERE id = %s", (ca,)) == ("APPROVED", ["NO_KPI"]))
raises("6d an approved plan is fixed", "mkt_plan_is_fixed", lambda: save_plan(ca))
raises("6e its channels are fixed", "mkt_plan_is_fixed", lambda: set_channels(ca, ["X"], [1]))
raises("6f even the owner cannot rename an approved plan", "mkt_plan_is_fixed",
       lambda: owner.execute("UPDATE mkt_campaigns SET name = 'حملة أخرى' WHERE id = %s", (ca,)))
raises("6g the owner cannot set approved_at or row_version", "mkt_campaign_managed_columns",
       lambda: owner.execute("UPDATE mkt_campaigns SET row_version = 99 WHERE id = %s", (ca,)))

# 7. Items.
as_user(app, a)
raises("7a an item on a channel outside the plan is refused", "mkt_channel_not_in_plan",
       lambda: new_item(ca, channel="TIKTOK"))
raises("7b an item body with a control character is refused", "mkt_item_body",
       lambda: new_item(ca, body="نصّ\x07"))
raises("7c an empty body is refused", "mkt_item_body", lambda: new_item(ca, body=""))
i1 = new_item(ca, at=datetime.time(20, 0), warnings=["PRICE"], spend=150000)
check("7d the digest is the database's",
      one("SELECT body_digest = sha256(convert_to(channel || E'\\n' || body, 'UTF8')) FROM mkt_items WHERE id = %s",
          (i1,))[0])
cb = new_campaign(a, "حملة العودة للمدارس")
save_plan(cb, kpi=("ORDERS", 10), budget=100000, starts=T, ends=T + datetime.timedelta(days=10))
set_channels(cb, ["INSTAGRAM"], [100000])
i2 = new_item(cb, at=datetime.time(20, 30))
check("7e a slot clash is flagged across campaigns", f"SLOT_CLASH:{i1}" in flags_item(i2), str(flags_item(i2)))
i3 = new_item(ca, spend=60000)
check("7f planned spend over the channel allocation is flagged",
      "CHANNEL_PLANNED_OVER_ALLOCATION:INSTAGRAM" in flags_item(i3), str(flags_item(i3)))
i4 = new_item(ca, day=T + datetime.timedelta(days=40))
check("7g an item outside the campaign dates is flagged", "ITEM_OUTSIDE_CAMPAIGN" in flags_item(i4))
i5 = new_item(ca, day=T - datetime.timedelta(days=2))
check("7h a draft whose date has passed is flagged", "ITEM_DATE_PASSED" in flags_item(i5))
check("7i copy warnings from the server are flags", "PRICE" in flags_item(i1))
raises("7j an item cannot be approved while its plan is in planning", "mkt_plan_not_approved",
       lambda: item_to(i2, "APPROVED"))
raises("7k approving without the exact acknowledgement is refused", "mkt_flags_changed",
       lambda: item_to(i1, "APPROVED", ack=["PRICE"]))
item_to(i1, "APPROVED")
check("7l approval stores the acknowledged keys",
      sorted(one("SELECT approved_with_flags FROM mkt_items WHERE id = %s", (i1,))[0])
      == sorted(["PRICE", f"SLOT_CLASH:{i2}", "CHANNEL_PLANNED_OVER_ALLOCATION:INSTAGRAM"]))
raises("7m an approved item is fixed", "mkt_item_is_fixed",
       lambda: one("SELECT ew_mkt_item_save(%s,%s,'INSTAGRAM',%s,NULL,'نصٌّ آخر',%s,NULL)",
                   (i1, rv("mkt_items", i1), T, [])))
raises("7n publishing in the future is refused", "mkt_published_at_range",
       lambda: item_to(i1, "PUBLISHED", published_at=datetime.datetime.now(datetime.timezone.utc)
                       + datetime.timedelta(hours=2)))
item_to(i1, "PUBLISHED")
raises("7o a published item is final", "mkt_item_is_final", lambda: item_to(i1, "CANCELLED"))
item_to(i3, "APPROVED")
item_to(i3, "DRAFT")
check("7p unapproving clears the approval", one("SELECT status, approved_at, approved_with_flags FROM mkt_items"
                                                " WHERE id = %s", (i3,)) == ("DRAFT", None, []))
one("SELECT ew_mkt_item_save(%s,%s,'X',%s,NULL,'منشورٌ معدَّل.',%s,NULL)", (i3, rv("mkt_items", i3), T, []))
check("7q a draft is editable and moves channel", one("SELECT channel FROM mkt_items WHERE id = %s", (i3,))[0] == "X")
raises("7r an item date more than two years ahead is refused", "mkt_item_date_range",
       lambda: new_item(ca, day=T + datetime.timedelta(days=800)))
raises("7s seconds in the time are refused", "mkt_item_time_minute", lambda: new_item(ca, at=datetime.time(9, 0, 30)))

# 8. Product ad as the source of an item.
as_user(app, a)
ad, ad_body = ready_product_ad(a)
as_user(app, a)
raises("8a the body must equal the ad's approved copy", "mkt_source_body",
       lambda: new_item(ca, body="نصٌّ مختلف عن الإعلان.", source=ad))
draft_ad = one("INSERT INTO campaigns (user_id) VALUES (%s) RETURNING id", (a,))[0]
raises("8b only a READY ad is a source", "mkt_source_not_ready", lambda: new_item(ca, body=ad_body, source=draft_ad))
i6 = new_item(ca, body=ad_body, source=ad, spend=50000)
item_to(i6, "APPROVED")
item_to(i6, "PUBLISHED")
owner.execute("DELETE FROM campaigns WHERE id = %s", (ad,))
check("8c deleting the ad empties the reference, even on a published item",
      one("SELECT source_campaign_id, status FROM mkt_items WHERE id = %s", (i6,)) == (None, "PUBLISHED"))
as_user(app, b)
raises("8d another account's ad is not a source", "mkt_source_not_ready",
       lambda: one("SELECT ew_mkt_item_create(%s,'INSTAGRAM',%s,NULL,%s,'{}',NULL,%s)",
                   (ca, T, ad_body, draft_ad)), sqlstate=None)

# 9. Results.
as_user(app, a)
y = T - datetime.timedelta(days=1)
raises("9a results for a plan in planning are refused", "mkt_results_need_approved_plan",
       lambda: save_results(cb, "INSTAGRAM", y, y, clicks=5))
raises("9b results for a period that has not come are refused", "mkt_results_in_future",
       lambda: save_results(ca, "INSTAGRAM", T, T + datetime.timedelta(days=1), clicks=5))
raises("9c results before the campaign are refused", "mkt_results_outside_campaign",
       lambda: save_results(ca, "INSTAGRAM", T - datetime.timedelta(days=9), y, clicks=5))
raises("9d results without any figure are refused", "mkt_results_some", lambda: save_results(ca, "INSTAGRAM", y, y))
r1 = save_results(ca, "INSTAGRAM", y, y, spend=10000, impressions=4000, clicks=120)
raises("9e an overlapping period on the same channel is refused", "mkt_results_overlap",
       lambda: save_results(ca, "INSTAGRAM", y - datetime.timedelta(days=1), y, clicks=1))
r2 = save_results(ca, "X", y, y, clicks=3)
check("9f the same period on another channel is accepted", r2 is not None)
keys = [r[0] for r in app.execute("SELECT flag_key FROM ew_mkt_results_flags(%s,'INSTAGRAM',NULL,%s)",
                                  (ca, 250000)).fetchall()]
check("9g spend over the channel allocation and over the budget are flagged",
      keys == ["CHANNEL_SPEND_OVER_ALLOCATION:INSTAGRAM"], str(keys))
d2 = y - datetime.timedelta(days=1)
raises("9h saving without acknowledging is refused", "mkt_flags_changed",
       lambda: save_results(ca, "INSTAGRAM", d2, d2, spend=250000, ack=[]))
r3 = save_results(ca, "INSTAGRAM", d2, d2, spend=250000)
check("9i the acknowledgement is stored with the entry",
      one("SELECT acknowledged_flags FROM mkt_results WHERE id = %s", (r3,))[0]
      == ["CHANNEL_SPEND_OVER_ALLOCATION:INSTAGRAM"])
keys = [r[0] for r in app.execute("SELECT flag_key FROM ew_mkt_results_flags(%s,'X',NULL,%s)",
                                  (ca, 300000)).fetchall()]
check("9j total spend over the budget is flagged", "TOTAL_SPEND_OVER_BUDGET" in keys, str(keys))
save_results(ca, "INSTAGRAM", y, y, spend=10000, impressions=4100, clicks=121, result=r1)
check("9k a correction bumps the row version", rv("mkt_results", r1) == 2)
raises("9l a stale correction is refused", "mkt_stale",
       lambda: one("SELECT ew_mkt_results_save(%s,'INSTAGRAM',%s,1,%s,%s,NULL,NULL,5,NULL,NULL,NULL,'{}')",
                   (ca, r1, y, y)))
check("9m plan flags count the spend", "CHANNEL_SPEND_OVER_ALLOCATION:INSTAGRAM" in flags_campaign(ca))

# 10. Reopen, dates around results, channel removal, cancel.
as_user(app, a)
one("SELECT ew_mkt_campaign_transition(%s,%s,'PLANNING','{}')", (ca, rv("mkt_campaigns", ca)))
check("10a reopening clears the approval",
      one("SELECT status, approved_at, approved_with_flags FROM mkt_campaigns WHERE id = %s", (ca,))
      == ("PLANNING", None, []))
raises("10b dates cannot be cut from under results", "mkt_dates_exclude_results",
       lambda: save_plan(ca, kpi=None, starts=T, ends=T + datetime.timedelta(days=20)))
raises("10c a channel with results cannot be removed", "mkt_channel_has_results",
       lambda: set_channels(ca, ["X"], [100000]))
cc = new_campaign(a, "حملة رمضان")
save_plan(cc, kpi=("LEADS", 30), goal="LEADS", budget=100000, starts=T, ends=T + datetime.timedelta(days=5))
set_channels(cc, ["SNAPCHAT", "WHATSAPP"], [50000, 50000])
ic = new_item(cc, channel="SNAPCHAT", day=T + datetime.timedelta(days=1))
raises("10d a channel with a live item cannot be removed", "mkt_channel_in_use",
       lambda: set_channels(cc, ["WHATSAPP"], [50000]))
item_to(ic, "CANCELLED")
set_channels(cc, ["WHATSAPP"], [50000])
check("10e removing a channel removes its cancelled items",
      one("SELECT count(*) FROM mkt_items WHERE id = %s", (ic,), conn=owner)[0] == 0)
id_ = new_item(cc, channel="WHATSAPP")
approve_campaign(cc)
item_to(id_, "APPROVED")
one("SELECT ew_mkt_campaign_transition(%s,%s,'CANCELLED','{}')", (cc, rv("mkt_campaigns", cc)))
check("10f cancelling cancels live items", one("SELECT status FROM mkt_items WHERE id = %s", (id_,))[0] == "CANCELLED")
raises("10g a cancelled campaign is final", "mkt_campaign_is_final",
       lambda: owner.execute("UPDATE mkt_campaigns SET name = 'حملة أخرى' WHERE id = %s", (cc,)))
raises("10h no item in a cancelled campaign", "mkt_campaign_is_final",
       lambda: owner.execute("INSERT INTO mkt_items (campaign_id, user_id, channel, publish_on, body)"
                             " VALUES (%s, %s, 'WHATSAPP', %s, 'نصّ')", (cc, a, T)))

# 11. AI review.
as_user(app, a)
ce = new_campaign(a, "حملة العناية")
save_plan(ce, kpi=("ORDERS", 10), budget=0, starts=T, ends=T + datetime.timedelta(days=10))
set_channels(ce, ["INSTAGRAM"], [0])
body = "كريمٌ يعالج حب الشباب خلال أسبوع، والأفضل في السوق."
ie = new_item(ce, body=body)
call = one("SELECT ew_mkt_review_begin(%s)", (ie,))[0]
check("11a a review call opens", call is not None)
raises("11b a second call while one is in flight is refused", "mkt_review_in_progress",
       lambda: one("SELECT ew_mkt_review_begin(%s)", (ie,)))
raises("11c a quote that is not in the text is refused", "mkt_review_quote",
       lambda: one("SELECT ew_mkt_review_record(%s,%s,%s,%s,10,10,'claude-opus-5-5','mkt-1',NULL)",
                   (call, ["HEALTH"], ["يشفي السكري"], ["ادّعاءٌ علاجي يحتاج إثباتاً."])))
before = rv("mkt_items", ie)
ok = one("SELECT ew_mkt_review_record(%s,%s,%s,%s,10,10,'claude-opus-5-5','mkt-1','req_1')",
         (call, ["HEALTH", "ABSOLUTE"], ["يعالج حب الشباب خلال أسبوع", "الأفضل في السوق"],
          ["ادّعاءٌ علاجي بنتيجةٍ محدّدة يحتاج إثباتاً.", "«الأفضل في السوق» مقارنةٌ مطلقة تحتاج ما يثبتها."]))[0]
check("11d the review is recorded", ok is True)
check("11e the review does not bump the item's row version", rv("mkt_items", ie) == before)
check("11f the AI flags are the item's flags", [k for k in flags_item(ie) if k.startswith("CLAIM")]
      == ["CLAIM_NEEDS_PROOF:1", "CLAIM_NEEDS_PROOF:2"])
check("11g the same text is not reviewed twice", one("SELECT ew_mkt_review_begin(%s)", (ie,))[0] is None)
raises("11h AI flags are append-only, even for the owner", None,
       lambda: owner.execute("UPDATE mkt_ai_flags SET reason = 'x' WHERE item_id = %s", (ie,)), sqlstate="42501")
call2_item = new_item(ce, body="عطرٌ يدوم طويلاً.")
call2 = one("SELECT ew_mkt_review_begin(%s)", (call2_item,))[0]
one("SELECT ew_mkt_item_save(%s,%s,'INSTAGRAM',%s,NULL,'عطرٌ يدوم يوماً كاملاً.','{}',NULL)",
    (call2_item, rv("mkt_items", call2_item), T + datetime.timedelta(days=1)))
check("11i a review of text that changed meanwhile is discarded",
      one("SELECT ew_mkt_review_record(%s,'{}','{}','{}',5,5,'claude-opus-5-5','mkt-1',NULL)", (call2,))[0] is False
      and one("SELECT outcome FROM mkt_review_calls WHERE id = %s", (call2,), conn=owner)[0] == "DISCARDED")
one("SELECT ew_mkt_item_save(%s,%s,'INSTAGRAM',%s,NULL,%s,'{}',NULL)",
    (ie, rv("mkt_items", ie), T + datetime.timedelta(days=1), body + " جرّبه اليوم."))
check("11j changing the text drops its AI flags", not [k for k in flags_item(ie) if k.startswith("CLAIM")]
      and one("SELECT count(*) FROM mkt_ai_flags WHERE item_id = %s", (ie,), conn=owner)[0] == 0)
raises("11k an unknown failure outcome is refused", "mkt_review_outcome",
       lambda: one("SELECT ew_mkt_review_finish(%s,'OK',1,1,NULL,NULL)", (one("SELECT ew_mkt_review_begin(%s)", (ie,))[0],)))
owner.execute("UPDATE mkt_review_calls SET finished_at = now(), outcome = 'UPSTREAM_BUSY' WHERE finished_at IS NULL")

# Daily cap: 30 billable for an established account, 10 for a new open one.
owner.execute("INSERT INTO mkt_review_calls (user_id, item_id, body_digest, finished_at, outcome, started_at)"
              " SELECT %s, %s, sha256('x'), now(), 'OK', now() - interval '1 hour' FROM generate_series(1, 30)",
              (a, ie))
raises("11l the daily cap holds", "mkt_review_daily_cap", lambda: one("SELECT ew_mkt_review_begin(%s)", (ie,)))
fresh = user("mkt-fresh")
owner.execute("UPDATE users SET self_registered = true, open_registered = true, terms_version = '2026-10-09',"
              " terms_accepted_at = now() WHERE id = %s", (fresh,))
cf = new_campaign(fresh, "حملة جديدة")
save_plan(cf, kpi=None, budget=0, starts=T, ends=T + datetime.timedelta(days=3))
set_channels(cf, ["X"], [0])
itf = new_item(cf, channel="X", body="منشورٌ قصير.")
owner.execute("INSERT INTO mkt_review_calls (user_id, item_id, body_digest, finished_at, outcome, started_at, new_account)"
              " SELECT %s, %s, sha256('x'), now(), 'OK', now() - interval '1 hour', true FROM generate_series(1, 10)",
              (fresh, itf))
as_user(app, fresh)
raises("11m a new open account has 10 a day", "mkt_review_new_account_cap",
       lambda: one("SELECT ew_mkt_review_begin(%s)", (itf,)))

# Upstream failures do not count.
owner.execute("DELETE FROM mkt_review_calls WHERE user_id = %s", (fresh,))
owner.execute("INSERT INTO mkt_review_calls (user_id, item_id, body_digest, finished_at, outcome, started_at, new_account)"
              " SELECT %s, %s, sha256('x'), now(), 'UPSTREAM_BUSY', now() - interval '1 hour', true"
              " FROM generate_series(1, 10)", (fresh, itf))
c3 = one("SELECT ew_mkt_review_begin(%s)", (itf,))[0]
check("11n unbilled outcomes do not count toward the cap", c3 is not None)
one("SELECT ew_mkt_review_finish(%s,'UPSTREAM_ERROR',NULL,NULL,NULL,NULL)", (c3,))

# Global cap: review calls count for the product tool, and the product tool's attempts count for reviews.
x = user("mkt-x")
owner.execute("INSERT INTO mkt_review_calls (user_id, item_id, body_digest, finished_at, outcome, started_at)"
              " SELECT %s, gen_random_uuid(), sha256('x'), now(), 'OK', now() - interval '2 hours'"
              " FROM generate_series(1, 2000 - (SELECT count(*) FROM mkt_review_calls"
              "  WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')"
              " - (SELECT count(*) FROM generation_attempts WHERE ew_is_billable(outcome)"
              "  AND started_at > now() - interval '24 hours'))", (x,))
as_user(app, b)
pb = one("INSERT INTO campaigns (user_id) VALUES (%s) RETURNING id", (b,))[0]
jpeg = sample_jpeg()
app.execute("INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
            " VALUES (%s, %s, %s, 400, 400, %s)", (pb, b, jpeg, hashlib.sha256(jpeg).digest()))
raises("11o review calls fill the app-wide cap for the product tool", "generation_global_cap",
       lambda: one("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (pb,)))
cbb = new_campaign(b, "حملة ب")
save_plan(cbb, kpi=None, budget=0, starts=T, ends=T + datetime.timedelta(days=3))
set_channels(cbb, ["X"], [0])
ib = new_item(cbb, channel="X", body="منشورٌ آخر.")
raises("11p the review hits the app-wide review cap first (600)", "mkt_review_app_cap",
       lambda: one("SELECT ew_mkt_review_begin(%s)", (ib,)))
owner.execute("DELETE FROM mkt_review_calls WHERE user_id = %s", (x,))
check("11q deleting calls leaves tombstones, so the cap does not empty",
      one("SELECT count(*) FROM attempt_tombstones", conn=owner)[0] >= 1900)
owner.execute("DELETE FROM attempt_tombstones")
owner.execute("INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at,"
              " outcome) SELECT %s, %s, 'INITIAL', %s, now() - interval '1 hour', now(), 'OUTPUT_INVALID'"
              " FROM generate_series(1, 2000)", (pb, b, hashlib.sha256(jpeg).digest()))
as_user(app, b)
raises("11r product-tool attempts fill the cap for reviews", "generation_global_cap",
       lambda: one("SELECT ew_mkt_review_begin(%s)", (ib,)))
owner.execute("DELETE FROM generation_attempts")
owner.execute("DELETE FROM attempt_tombstones")

# 12. Deletion paths.
as_user(app, a)
check("12a a's data exists", one("SELECT count(*) FROM mkt_items", conn=owner)[0] > 0)
owner.execute("DELETE FROM mkt_campaigns WHERE id = %s", (ca,))
check("12b deleting an approved-then-reopened campaign with results and published items cascades",
      one("SELECT count(*) FROM mkt_items WHERE campaign_id = %s", (ca,), conn=owner)[0] == 0
      and one("SELECT count(*) FROM mkt_results WHERE campaign_id = %s", (ca,), conn=owner)[0] == 0)
calls_a = one("SELECT count(*) FROM mkt_review_calls WHERE user_id = %s AND ew_is_billable(outcome)"
              " AND started_at > now() - interval '24 hours'", (a,), conn=owner)[0]
as_user(app, a)
app.execute("SELECT ew_delete_me()")
check("12c account deletion removes every marketing row",
      one("SELECT (SELECT count(*) FROM mkt_campaigns WHERE user_id = %s) + (SELECT count(*) FROM mkt_review_calls"
          " WHERE user_id = %s)", (a, a), conn=owner)[0] == 0)
check("12d and leaves a tombstone for each billable call of the day",
      one("SELECT count(*) FROM attempt_tombstones", conn=owner)[0] == calls_a, str(calls_a))

# 13. Concurrency: an item approval waits for a plan reopen holding the campaign.
as_user(app, b)
save_plan(cbb, kpi=("CLICKS", 100), goal="TRAFFIC", budget=0, starts=T, ends=T + datetime.timedelta(days=3))
approve_campaign(cbb)
ib_rv = rv("mkt_items", ib)
holder = psycopg.connect(APP)
as_user(holder, b)
holder.execute("SELECT ew_mkt_campaign_transition(%s,%s,'PLANNING','{}')", (cbb, rv("mkt_campaigns", cbb)))
outcome: dict[str, str] = {}


def approve_in_thread() -> None:
    conn = psycopg.connect(APP, autocommit=True)
    as_user(conn, b)
    try:
        conn.execute("SELECT ew_mkt_item_transition(%s,%s,'APPROVED',%s,NULL)",
                     (ib, ib_rv, ["ITEM_DATE_PASSED"] if False else []))
        outcome["r"] = "approved"
    except psycopg.Error as exc:
        outcome["r"] = exc.diag.constraint_name or exc.sqlstate
    conn.close()


t = threading.Thread(target=approve_in_thread)
t.start()
time.sleep(0.5)
waiting = t.is_alive()
holder.commit()
t.join(5)
holder.close()
check("13a the approval waited for the reopen", waiting)
check("13b and then saw the plan in planning", outcome.get("r") == "mkt_plan_not_approved", str(outcome))

# 14. The down refuses while campaigns exist.
down = (HERE / "NEXT_marketing.down.sql").read_text(encoding="utf-8")
try:
    with psycopg.connect(OWNER) as conn:
        conn.execute(down)
        conn.rollback()
    check("14 the down refuses while campaigns exist", False, "ran")
except psycopg.Error as exc:
    check("14 the down refuses while campaigns exist", "حملاتٌ" in str(exc), str(exc)[:80])

# ════════════════════════════════════════════════════════════════════════
passed = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
print(f"\n{passed}/{len(results)} passed")
clean()
sys.exit(0 if passed == len(results) else 1)
