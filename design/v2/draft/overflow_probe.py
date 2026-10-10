import socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
HERE='design/v2'
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
srv = subprocess.Popen([sys.executable, "-I", HERE+"/tools/serve.py", HERE+"/client/dist-demo", str(port)])
time.sleep(0.4)
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
        c = b.new_context(viewport={"width": 320, "height": 635}); p = c.new_page()
        p.goto(f"http://127.0.0.1:{port}/demo.html?screen=support-ticket&size=compact"); p.wait_for_load_state("networkidle")
        print(p.evaluate("""() => [...document.querySelectorAll('main *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.left < 15 || r.right > innerWidth - 15) }).slice(0, 12).map(e => e.tagName + '.' + (e.className.baseVal ?? e.className).toString().slice(0, 80) + ' ' + Math.round(e.getBoundingClientRect().left) + '..' + Math.round(e.getBoundingClientRect().right))"""))
        b.close()
finally:
    srv.terminate()
