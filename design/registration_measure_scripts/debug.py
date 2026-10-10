import functools, http.server, json, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
folder = Path(sys.argv[1])
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
handler.log_message = lambda *a, **k: None
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
port = httpd.server_address[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    page = b.new_page(viewport={"width": 320, "height": 635})
    page.route("**/app.js", lambda r: r.abort()); page.route("**/portal.js", lambda r: r.abort())
    page.goto(f"http://127.0.0.1:{port}/index.html"); page.evaluate("document.fonts.ready")
    print(json.dumps(page.evaluate("""() => {
      document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.dataset.screen !== 'signup-notice'; });
      const s = document.querySelector('.screen[data-screen="signup-notice"]');
      const c = s.querySelector('.content');
      const r = (e) => { const b = e.getBoundingClientRect(); return [e.tagName + '.' + e.className, Math.round(b.top), Math.round(b.bottom), Math.round(b.height)]; };
      return { screen: r(s), content: r(c), sh: c.scrollHeight, ch: c.clientHeight, cs: getComputedStyle(c).overflow,
               kids: [...c.children].map(r), bars: [...s.querySelectorAll('.bar')].map(r),
               docH: document.scrollingElement.scrollHeight, html: getComputedStyle(document.documentElement).fontSize,
               lineFs: getComputedStyle(c.querySelector('.line')).fontSize, lineLh: getComputedStyle(c.querySelector('.line')).lineHeight };
    }"""), ensure_ascii=False, indent=0))
    b.close()
