"""
Prototype harness for the eyework client redesign.

Serves client/dist with the exact Content-Security-Policy and security headers of
eyework/web/app.py, and answers the handful of /api routes the prototype screens
call from JSON fixtures exported from the real modules (eyework.professions,
eyework.money, the /api/choices builder). It is a design harness, not the backend:
the real server is FastAPI; nothing here is meant to ship.

Session state is a cookie (`proto_session`), so the same build shows the logged-out
welcome and the logged-in home. `proto_tool=1` adds an illustrative tool code to the
storekeeper portal to render the tool slot.

Usage: python3 serve.py <dist> <fixtures> <port>
"""

from __future__ import annotations

import json
import mimetypes
import sys
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_CSP = (
    "default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; "
    "font-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'"
)
APP_CSP = f"{BASE_CSP}; connect-src 'self'; form-action 'self'"
SECURITY = {
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), display-capture=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("font/woff2", ".woff2")

DIST = Path(sys.argv[1]).resolve()
FIXTURES = Path(sys.argv[2]).resolve()
PORT = int(sys.argv[3])

CHOICES = json.loads((FIXTURES / "choices.json").read_text(encoding="utf-8"))
PORTALS = {p: json.loads((FIXTURES / f"portal_{p}.json").read_text(encoding="utf-8"))
           for p in ("MARKETING", "STOREKEEPER", "SUPPORT")}

STARTERS = {
    "suggestions": ["كيف أتحقّق من شحنةٍ واردة؟", "ماذا أفعل إن لم تطابق الفاتورةُ الشحنة؟"],
    "left_today": 38,
}

# The answer the prototype shows. Its steps restate O*NET task 1 of the storekeeper
# portal (the source line names it); the real answer comes from the assistant track.
ANSWER = {
    "question": "كيف أتحقّق من شحنةٍ واردة؟",
    "parts": [
        "خطواتٌ مقترحة من مهمة «فحص محتويات الشحنة ومقارنتها بالسجلات»:\n"
        "١. قابِل عدد الطرود بما في بيان الحمولة.\n"
        "٢. طابِق الأصناف والكميات مع الفاتورة أو أمر الشراء.\n"
        "٣. سجّل كلّ فرقٍ قبل اعتماد الاستلام، وأبلغ به المسؤول.",
        "ما يُؤدّى من هنا: مراجعة السجلات والفواتير ومطابقتها حين تصلك صورها أو ملفّاتها.\n"
        "وما يحتاج حضوراً في المستودع — عدّ الطرود وفحصها — يؤدّيه زميلٌ، وتراجع أنت ما سجّله.",
    ],
    "sources": ["المهمة 1 من مهامّ أمين المخزون", "O*NET® 43-5071.00، CC BY 4.0"],
}

PASSKEY_LOGIN_OPTIONS = {
    "challenge": "c2FtcGxlLWNoYWxsZW5nZS1mb3ItcHJvdG90eXBl",
    "timeout": 60000,
    "rpId": "localhost",
    "userVerification": "required",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "eyework-proto"

    def log_message(self, fmt, *args):  # quiet
        pass

    def _cookies(self) -> dict[str, str]:
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return {k: v.value for k, v in jar.items()}

    def _headers(self, status: int, content_type: str, length: int, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Security-Policy", APP_CSP)
        for name, value in SECURITY.items():
            self.send_header(name, value)
        cache = "no-store" if self.path.startswith("/api/") else (
            "public, max-age=31536000, immutable" if self.path.startswith("/assets/") else "no-cache")
        self.send_header("Cache-Control", cache)
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()

    def _json(self, status: int, payload, extra: dict | None = None) -> None:
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json", len(body), extra)
        if body:
            self.wfile.write(body)

    def _signed_in(self) -> bool:
        return self._cookies().get("proto_session") == "1"

    def _portal(self) -> dict:
        profession = self._cookies().get("proto_prof", "STOREKEEPER")
        portal = dict(PORTALS.get(profession, PORTALS["STOREKEEPER"]))
        if self._cookies().get("proto_tool") == "1":
            portal["tools"] = ["STOCK_COUNT"]
        return portal

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            if self.headers.get("X-Eyework") != "1":
                return self._json(403, {"code": "ORIGIN", "detail": "طلبٌ من خارج التطبيق."})
            if path == "/api/choices":
                return self._json(200, CHOICES)
            if not self._signed_in():
                return self._json(401, {"code": "SESSION", "detail": "سجّل الدخول للمتابعة."})
            if path == "/api/me":
                return self._json(200, {"generations_left": 40, "display_name": "سارة", "profession": "STOREKEEPER"})
            if path == "/api/portal":
                return self._json(200, self._portal())
            if path == "/api/assistant":
                return self._json(200, STARTERS)
            return self._json(404, {"code": "NOT_FOUND", "detail": "غير موجود."})
        target = (DIST / path.lstrip("/")).resolve()
        if path == "/" or not target.is_file() or DIST not in target.parents:
            target = DIST / "index.html"
        data = target.read_bytes()
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind in ("application/javascript",):
            kind += "; charset=utf-8"
        self._headers(200, kind, len(data))
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if self.headers.get("X-Eyework") != "1":
            return self._json(403, {"code": "ORIGIN", "detail": "طلبٌ من خارج التطبيق."})
        if path == "/api/auth/login":
            body = json.loads(raw or b"{}")
            if body.get("password") == "Strong-Password-2026-x":
                return self._json(204, None, {"Set-Cookie": "proto_session=1; Path=/; SameSite=Strict"})
            return self._json(401, {"code": "LOGIN", "detail": "اسم الدخول أو كلمة المرور غير صحيحة."})
        if path == "/api/auth/logout":
            return self._json(204, None, {"Set-Cookie": "proto_session=0; Path=/; Max-Age=0"})
        if path in ("/api/auth/passkey/options", "/api/me/passkeys/options"):
            return self._json(200, PASSKEY_LOGIN_OPTIONS)
        if path == "/api/assistant/ask":
            if not self._signed_in():
                return self._json(401, {"code": "SESSION", "detail": "سجّل الدخول للمتابعة."})
            body = json.loads(raw or b"{}")
            return self._json(200, {**ANSWER, "question": body.get("question") or ANSWER["question"]})
        return self._json(404, {"code": "NOT_FOUND", "detail": "غير موجود."})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
