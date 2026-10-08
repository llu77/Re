"""
أداة المشغّل
============
تعمل بدور المالك (`EYEWORK_OWNER_DATABASE_URL`) من سطر الأوامر، لا من الويب:
خادم الويب لا يملك هذه الصلاحيات أصلاً.

    python -m eyework.admin create-user --login ali@example.sa [--name "علي"]
    python -m eyework.admin set-name --login ali@example.sa --name "علي" | --clear
    python -m eyework.admin reissue-activation --login ali@example.sa
    python -m eyework.admin deactivate --login ali@example.sa
    python -m eyework.admin delete-user --login ali@example.sa --confirm-delete-all-data
    python -m eyework.admin purge

**الدعوة رابطٌ يُطبع، لا يُرسل.** لا بريد يخرج من التطبيق ولا يُخزَّن: المشغّل
يسلّم الرابط بنفسه، ويحفظ صلة الاسم بصاحبه خارج النظام. والرمز في جزء
الرابط بعد `#`، فلا يصل خادماً ولا سجلّاً ولا إحالة.

**اسم الدخول بحروفٍ لاتينية بسيطة.** التوحيد (NFKC) لا يجمع «أ» و«ا» ولا «ى»
و«ي»؛ اسمٌ عربي قد يُكتب عند الدخول بغير ما كُتب عند الدعوة فلا يطابق.

**الاحتفاظ.** `purge` يُشغَّل يومياً من مجدول النظام: الحملة المعتمدة أو
الملغاة تُحذف بعد تسعين يوماً، وغير المنتهية بعد ثلاثين يوماً من آخر تعديل،
والجلسات والرموز المنتهية بعد ثلاثين يوماً.

**الاسم اختياري.** يناديه به المساعد في الواجهة («أنا سيمبول، مساعدك الشخصي يا
علي»). يُخزَّن في قاعدة التطبيق وحدها ولا يصل مزوّد النموذج. الاسم الأول أو
الكنية تكفي: كل حرفٍ زائد بيانٌ عن صاحبه لا تحتاجه الواجهة.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import psycopg

from eyework import auth, config

__all__ = ["main"]

ACTIVATION_HOURS = 72
_LOGIN = re.compile(r"^[a-z0-9._@+-]{3,254}$")
#: نظير القيد display_name_shape في الترحيل 0003.
_NAME = re.compile(r"^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$")
_NAME_MAX = 30

_CREATE_USER = "INSERT INTO users (login_hmac) VALUES (%s) RETURNING id"
_USER_BY_LOGIN = "SELECT id, is_active FROM users WHERE login_hmac = %s"
_CLOSE_TOKENS = "UPDATE activation_tokens SET used_at = now() WHERE user_id = %s AND used_at IS NULL"
_NEW_TOKEN = """
INSERT INTO activation_tokens (token_hash, user_id, expires_at)
VALUES (%s, %s, now() + make_interval(hours => %s))
"""
_DEACTIVATE = "UPDATE users SET is_active = false WHERE id = %s"
_SET_NAME = "UPDATE users SET display_name = %s WHERE id = %s"
_REVOKE_ALL = "UPDATE sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL"
_DELETE_USER = "DELETE FROM users WHERE id = %s"

# محاولات اليوم تعدّها السقوف (اليومي والعام). حذف حملتها يمحوها فيستردّ
# صاحبها حصّةً دُفعت؛ فلا تُحذف حملةٌ فيها محاولةٌ عمرها دون يوم (الشرط الأخير
# في العبارتين).
_PURGE_FINAL = """
DELETE FROM campaigns c
 WHERE ((c.status = 'READY' AND c.ready_at < now() - interval '90 days')
     OR (c.status = 'CANCELLED' AND c.cancelled_at < now() - interval '90 days'))
   AND NOT EXISTS (SELECT 1 FROM generation_attempts a
                    WHERE a.campaign_id = c.id AND a.started_at > now() - interval '24 hours')
"""
#: الخمول من آخر نشاطٍ أيّاً كان: تعديل الحملة، أو تغيير الصورة، أو محاولة كتابة.
_PURGE_IDLE = """
DELETE FROM campaigns c
 WHERE c.status IN ('DRAFT', 'COPY_PROPOSED', 'COPY_APPROVED')
   AND GREATEST(
           c.updated_at,
           coalesce((SELECT i.updated_at FROM campaign_images i WHERE i.campaign_id = c.id), c.updated_at),
           coalesce((SELECT max(a.started_at) FROM generation_attempts a WHERE a.campaign_id = c.id), c.updated_at)
       ) < now() - interval '30 days'
   AND NOT EXISTS (SELECT 1 FROM generation_attempts a
                    WHERE a.campaign_id = c.id AND a.started_at > now() - interval '24 hours')
"""
_PURGE_SESSIONS = """
DELETE FROM sessions
 WHERE expires_at < now() - interval '30 days' OR revoked_at < now() - interval '30 days'
"""
_PURGE_TOKENS = """
DELETE FROM activation_tokens
 WHERE expires_at < now() - interval '30 days' OR used_at < now() - interval '30 days'
"""


class AdminError(Exception):
    """خطأٌ يُطبع للمشغّل ويُنهي الأمر بحالة 1."""


def _owner_url() -> str:
    value = os.environ.get("EYEWORK_OWNER_DATABASE_URL", "").strip()
    if not value:
        raise AdminError("EYEWORK_OWNER_DATABASE_URL غير مضبوط")
    return value


def _settings() -> tuple[bytes, str]:
    try:
        key = config.login_key()
        origin = config.public_origin()
    except config.ConfigError as exc:
        raise AdminError(str(exc)) from exc
    return key, origin


def _login(raw: str) -> str:
    login = auth.normalize_login(raw)
    if not _LOGIN.match(login):
        raise AdminError("اسم الدخول: من 3 إلى 254 حرفاً من a-z و0-9 و. _ @ + -")
    return login


def _name(raw: str | None) -> str | None:
    if raw is None:
        return None
    name = " ".join(raw.split())
    if not name or len(name) > _NAME_MAX or not _NAME.match(name):
        raise AdminError("الاسم: حتى 30 حرفاً عربياً أو لاتينياً، بمسافاتٍ مفردة، بلا أرقامٍ ولا تشكيل")
    return name


def _fragment_value(text: str) -> str:
    """ترميز ما يحتاج ترميزاً من الحروف المسموحة في اسم الدخول وحدها."""
    return text.replace("%", "%25").replace("@", "%40").replace("+", "%2B")


def _issue(cursor, user_id, origin: str, login: str) -> str:
    cursor.execute(_CLOSE_TOKENS, (user_id,))
    token = auth.new_token()
    cursor.execute(_NEW_TOKEN, (auth.hash_token(token), user_id, ACTIVATION_HOURS))
    return f"{origin}/#activate={token}&u={_fragment_value(login)}"


def _find(cursor, key: bytes, login: str):
    cursor.execute(_USER_BY_LOGIN, (auth.login_hmac(key, login),))
    row = cursor.fetchone()
    if row is None:
        raise AdminError("لا حساب بهذا الاسم")
    return row


def create_user(raw_login: str, raw_name: str | None = None) -> str:
    key, origin = _settings()
    login = _login(raw_login)
    name = _name(raw_name)
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        try:
            cursor.execute(_CREATE_USER, (auth.login_hmac(key, login),))
        except psycopg.errors.UniqueViolation as exc:
            raise AdminError("الاسم مستعملٌ لحسابٍ قائم. استعمل reissue-activation") from exc
        user_id = cursor.fetchone()[0]
        if name is not None:
            cursor.execute(_SET_NAME, (name, user_id))
        return _issue(cursor, user_id, origin, login)


def set_name(raw_login: str, raw_name: str | None) -> None:
    """يضع الاسم الذي يناديه به المساعد، أو يمحوه (`None`)."""
    key, _ = _settings()
    name = _name(raw_name)
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, _ = _find(cursor, key, _login(raw_login))
        cursor.execute(_SET_NAME, (name, user_id))


def reissue_activation(raw_login: str) -> str:
    """رابطٌ جديد، والقديم يُغلق. هذا طريق الاسترداد الوحيد."""
    key, origin = _settings()
    login = _login(raw_login)
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, is_active = _find(cursor, key, login)
        if not is_active:
            raise AdminError("الحساب معطّل")
        return _issue(cursor, user_id, origin, login)


def deactivate(raw_login: str) -> None:
    key, _ = _settings()
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, _ = _find(cursor, key, _login(raw_login))
        cursor.execute(_DEACTIVATE, (user_id,))
        cursor.execute(_REVOKE_ALL, (user_id,))


def delete_user(raw_login: str) -> None:
    """يحذف الحساب وكل ما يتبعه: الجلسات، والرموز، والحملات، والنسخ، والصور."""
    key, _ = _settings()
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        user_id, _ = _find(cursor, key, _login(raw_login))
        cursor.execute(_DELETE_USER, (user_id,))


def purge() -> dict[str, int]:
    counts = {}
    with psycopg.connect(_owner_url()) as connection, connection.cursor() as cursor:
        for name, statement in (("final_campaigns", _PURGE_FINAL), ("idle_campaigns", _PURGE_IDLE),
                                ("sessions", _PURGE_SESSIONS), ("activation_tokens", _PURGE_TOKENS)):
            cursor.execute(statement)
            counts[name] = cursor.rowcount
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eyework.admin", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create-user", "reissue-activation", "deactivate", "delete-user", "set-name"):
        command = commands.add_parser(name)
        # بلا --login يُسأل عنه: سطر الأوامر يُحفظ في سجلّ الصدفة، فتتجمّع فيه
        # قائمة المستخدمين التي لا تحفظها القاعدة إلا HMAC.
        command.add_argument("--login")
        if name == "delete-user":
            command.add_argument("--confirm-delete-all-data", action="store_true", required=True)
        if name == "create-user":
            command.add_argument("--name")
        if name == "set-name":
            choice = command.add_mutually_exclusive_group(required=True)
            choice.add_argument("--name")
            choice.add_argument("--clear", action="store_true")
    commands.add_parser("purge")
    args = parser.parse_args(argv)
    if getattr(args, "login", "absent") is None:
        args.login = input("اسم الدخول: ").strip()

    try:
        if args.command == "create-user":
            print(create_user(args.login, args.name))
        elif args.command == "set-name":
            set_name(args.login, None if args.clear else args.name)
            print("مُحي الاسم" if args.clear else "وُضع الاسم")
        elif args.command == "reissue-activation":
            print(reissue_activation(args.login))
        elif args.command == "deactivate":
            deactivate(args.login)
            print("عُطّل الحساب وأُلغيت جلساته")
        elif args.command == "delete-user":
            delete_user(args.login)
            print("حُذف الحساب وكل بياناته")
        else:
            for name, count in purge().items():
                print(f"{name}: {count}")
    except AdminError as exc:
        print(f"خطأ: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
