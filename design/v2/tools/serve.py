"""
يخدم dist-demo بسياسة المحتوى نفسها التي يرسلها eyework (web/app.py: APP_CSP)، فما يعمل
هنا يعمل هناك: لا سكربت مضمَّن، ولا نمطٌ مضمَّن، ولا خطٌّ ولا صورةٌ من خارج الأصل.

    python3 serve.py <dist-dir> <port>
"""
import functools
import http.server
import sys

APP_CSP = (
    "default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; "
    "font-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; connect-src 'self'; form-action 'self'"
)


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".woff2": "font/woff2", ".js": "text/javascript"}

    def end_headers(self):
        self.send_header("Content-Security-Policy", APP_CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    root, port = sys.argv[1], int(sys.argv[2])
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=root))
    server.serve_forever()
