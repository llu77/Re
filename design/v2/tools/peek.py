"""صورٌ سريعة لمراجعة التصميم أثناء العمل: python3 -I peek.py <mode> <w>x<h> screen..."""
import socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE = Path(__file__).resolve().parent
mode, size, *screens = sys.argv[1:]
w, h = map(int, size.split("x"))
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
srv = subprocess.Popen([sys.executable, "-I", str(HERE / "serve.py"), str(HERE.parent / "client/dist-demo"), str(port)])
time.sleep(0.4)
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
        for screen in screens:
            c = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="ar-SA", has_touch=True)
            p = c.new_page()
            errs = []
            p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(f"http://127.0.0.1:{port}/demo.html?screen={screen}&size={mode}")
            p.wait_for_load_state("networkidle"); p.evaluate("() => document.fonts.ready")
            p.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
            full = "--full" in screens
            p.screenshot(path=str(HERE.parent / "draft" / f"peek_{screen}_{mode}_{w}.png"), full_page=False)
            if errs: print(screen, errs)
            c.close()
        b.close()
finally:
    srv.terminate()
