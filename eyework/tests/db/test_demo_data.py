"""
البيانات التجريبية (`demo_data.py` وأمر `seed-demo`): تذاكر الدعم الفني ومقالاته، ومنتجات أمين المخزون ومورّدوه
ورصيده وفواتيره. كلّها بدوالّ التطبيق وبهوية صاحب الحساب، فما يُرى هنا هو ما تقبله الشاشات.
"""

from __future__ import annotations

import base64

import pytest

from eyework import admin, auth, demo_data, inventory, support, support_notice
from eyework.db import Database
from eyework.tests.conftest import make_user

KEY = b"a" * 32


@pytest.fixture
def operator(owner, owner_url, app_url, monkeypatch):
    monkeypatch.setenv("EYEWORK_OWNER_DATABASE_URL", owner_url)
    monkeypatch.setenv("EYEWORK_APP_DATABASE_URL", app_url)
    monkeypatch.setenv("EYEWORK_LOGIN_KEY", base64.b64encode(KEY).decode())
    monkeypatch.setenv("EYEWORK_PUBLIC_ORIGIN", "https://work.example.sa")
    return owner


@pytest.fixture
def db(app_url):
    database = Database(app_url, max_size=2)
    yield database
    database.close()


def _account(owner, login: str, profession: str):
    return make_user(owner, login=auth.login_hmac(KEY, login), profession=profession)


def _seed(login: str, capsys) -> tuple[int, str, str]:
    code = admin.main(["seed-demo", "--login", login])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _rows(owner, statement: str, params: tuple) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall()


def _one(owner, statement: str, params: tuple):
    return _rows(owner, statement, params)[0][0]


# ── الدعم الفني ─────────────────────────────────────────────────────────
def test_support_waits_for_the_desk_notice(operator, capsys):
    user = _account(operator, "desk@example.sa", "SUPPORT")
    code, _, err = _seed("desk@example.sa", capsys)
    assert code == 1
    assert "إشعاره" in err
    assert _one(operator, "SELECT count(*) FROM support_tickets WHERE user_id = %s", (user,)) == 0
    assert _one(operator, "SELECT count(*) FROM kb_articles WHERE user_id = %s", (user,)) == 0


def test_support_gets_twelve_open_tickets_in_four_states_and_six_published_articles(operator, db, capsys):
    user = _account(operator, "desk@example.sa", "SUPPORT")
    support.accept_notice(db, user, support_notice.VERSION)
    code, out, err = _seed("desk@example.sa", capsys)
    assert code == 0, err
    assert "تذاكر مفتوحة جديدة: 12" in out
    assert "مقالات منشورة جديدة في قاعدة المعرفة: 6" in out

    states = dict(_rows(operator, "SELECT status, count(*) FROM support_tickets WHERE user_id = %s GROUP BY status",
                        (user,)))
    assert states == {"NEW": 5, "OPEN": 2, "PENDING": 3, "ESCALATED": 2}
    channels, categories, priorities = _rows(
        operator, "SELECT count(DISTINCT channel), count(DISTINCT category), count(DISTINCT priority)"
                  " FROM support_tickets WHERE user_id = %s", (user,))[0]
    assert (channels, categories, priorities) == (5, 9, 4)
    authors = dict(_rows(operator, "SELECT author, count(*) FROM support_messages WHERE user_id = %s GROUP BY author",
                         (user,)))
    # ثلاث عشرة رسالة عميل (واحدةٌ منها ثانيةٌ في تذكرتها)، وملاحظتان، وخمسة ردود أُرسلت.
    assert authors == {"CUSTOMER": 13, "NOTE": 2, "AGENT": 5}
    assert _one(operator, "SELECT count(*) FROM support_escalations WHERE user_id = %s", (user,)) == 2
    published = _one(operator, "SELECT count(*) FROM kb_articles WHERE user_id = %s AND state = 'PUBLISHED'", (user,))
    assert published == 6


def test_a_second_run_opens_new_tickets_and_keeps_the_articles(operator, db, capsys):
    user = _account(operator, "desk@example.sa", "SUPPORT")
    support.accept_notice(db, user, support_notice.VERSION)
    assert _seed("desk@example.sa", capsys)[0] == 0
    code, out, _ = _seed("desk@example.sa", capsys)
    assert code == 0
    assert "تذاكر مفتوحة جديدة: 12" in out
    assert "مقالات منشورة جديدة في قاعدة المعرفة: 0" in out
    assert _one(operator, "SELECT count(*) FROM support_tickets WHERE user_id = %s", (user,)) == 24
    assert _one(operator, "SELECT count(*) FROM kb_articles WHERE user_id = %s", (user,)) == 6


# ── أمين المخزون ────────────────────────────────────────────────────────
def test_the_storekeeper_answers_the_setup_question_first(operator, capsys):
    user = _account(operator, "keeper@example.sa", "STOREKEEPER")
    code, _, err = _seed("keeper@example.sa", capsys)
    assert code == 1
    assert "سؤال الإعداد" in err
    assert _one(operator, "SELECT count(*) FROM inv_settings WHERE user_id = %s", (user,)) == 0
    assert _one(operator, "SELECT count(*) FROM inv_items WHERE user_id = %s", (user,)) == 0


def test_the_storekeeper_gets_products_in_every_unit_with_suppliers_stock_and_invoices(operator, db, capsys):
    user = _account(operator, "keeper@example.sa", "STOREKEEPER")
    inventory.put_settings(db, user, False, "المخزن الرئيسي", None, None)
    code, out, err = _seed("keeper@example.sa", capsys)
    assert code == 0, err
    for line in ("منتجات جديدة برصيدها الافتتاحي: 24", "مورّدون جدد بمندوبيهم: 5", "فئات جديدة: 6", "فواتير شراء: 3"):
        assert line in out

    units = {row[0] for row in _rows(operator, "SELECT unit FROM inv_items WHERE user_id = %s", (user,))}
    assert units == {"PIECE", "BOX", "CARTON", "PACK", "PALLET", "KG", "LITRE", "METRE", "SERVICE"}
    kinds = dict(_rows(operator, "SELECT kind, count(*) FROM inv_items WHERE user_id = %s GROUP BY kind", (user,)))
    assert kinds == {"STOCK": 23, "SERVICE": 1}
    vat = dict(_rows(operator, "SELECT vat_category, count(*) FROM inv_items WHERE user_id = %s GROUP BY vat_category",
                     (user,)))
    assert vat == {"S": 23, "Z": 1}
    barcodes = [row[0] for row in _rows(operator, "SELECT barcode FROM inv_items WHERE user_id = %s AND kind = 'STOCK'",
                                        (user,))]
    assert len(set(barcodes)) == 23
    assert all(code == demo_data.ean13(code[:12]) and code.startswith("628") for code in barcodes)

    assert _one(operator, "SELECT count(*) FROM inv_categories WHERE user_id = %s", (user,)) == 6
    assert _one(operator, "SELECT count(*) FROM inv_suppliers WHERE user_id = %s", (user,)) == 5
    reps = _rows(operator, "SELECT supplier_id, count(*), count(*) FILTER (WHERE is_default) FROM inv_supplier_reps"
                           " WHERE user_id = %s GROUP BY supplier_id", (user,))
    assert sum(count for _, count, _ in reps) == 7
    assert all(defaults == 1 for _, _, defaults in reps)

    purchases = dict(_rows(operator, "SELECT status, count(*) FROM inv_purchases WHERE user_id = %s GROUP BY status",
                           (user,)))
    assert purchases == {"POSTED": 2, "DRAFT": 1}
    # الماء والملفات تحت حدّ الطلب، فتظهر في «يحتاج طلباً».
    low = {row[0] for row in _rows(operator, "SELECT name FROM inv_items WHERE user_id = %s"
                                             " AND on_hand_milli < reorder_level_milli", (user,))}
    assert low == {"ماء معبأ 330 مل (40 عبوة)", "ملفات بلاستيكية (10 ملفات)"}
    # الأرز: 250 افتتاحياً و200 من الفاتورة الأولى.
    assert _one(operator, "SELECT on_hand_milli FROM inv_items WHERE user_id = %s AND name = 'أرز بسمتي'",
                (user,)) == 450_000


def test_a_second_storekeeper_run_adds_nothing(operator, db, capsys):
    user = _account(operator, "keeper@example.sa", "STOREKEEPER")
    inventory.put_settings(db, user, False, "المخزن الرئيسي", None, None)
    assert _seed("keeper@example.sa", capsys)[0] == 0
    code, out, _ = _seed("keeper@example.sa", capsys)
    assert code == 0
    for line in ("منتجات جديدة برصيدها الافتتاحي: 0", "مورّدون جدد بمندوبيهم: 0", "فئات جديدة: 0", "فواتير شراء: 0"):
        assert line in out
    assert _one(operator, "SELECT count(*) FROM inv_items WHERE user_id = %s", (user,)) == 24
    assert _one(operator, "SELECT count(*) FROM inv_purchases WHERE user_id = %s", (user,)) == 3
    assert _one(operator, "SELECT count(*) FROM inv_vouchers WHERE user_id = %s", (user,)) == 23


# ── ما يُرفض ────────────────────────────────────────────────────────────
def test_marketing_has_no_sample_data(operator, capsys):
    _account(operator, "seller@example.sa", "MARKETING")
    code, _, err = _seed("seller@example.sa", capsys)
    assert code == 1
    assert "set-profession" in err


def test_the_command_needs_the_web_role_and_a_known_account(operator, capsys, monkeypatch):
    assert _seed("nobody@example.sa", capsys)[0] == 1
    _account(operator, "keeper@example.sa", "STOREKEEPER")
    monkeypatch.delenv("EYEWORK_APP_DATABASE_URL")
    code, _, err = _seed("keeper@example.sa", capsys)
    assert code == 1
    assert "EYEWORK_APP_DATABASE_URL" in err


def test_the_owner_role_is_refused_as_the_web_role(operator, owner_url, capsys, monkeypatch):
    """بدور المالك تُتجاوز سياسات العزل: الأمر يرفضه كما يرفضه الخادم عند الإقلاع."""
    _account(operator, "keeper@example.sa", "STOREKEEPER")
    monkeypatch.setenv("EYEWORK_APP_DATABASE_URL", owner_url)
    code, _, err = _seed("keeper@example.sa", capsys)
    assert code == 1
    assert "eyework_app" in err


def test_the_barcode_check_digit_is_ean13():
    assert demo_data.ean13("400638133393") == "4006381333931"
    assert demo_data.ean13("628100000001")[-1].isdigit()
