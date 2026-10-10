"""Quick preview: renders the named scenes from shoot.SCENES at 390x844 @1 into visual/preview/ and a contact sheet."""
import subprocess, sys, time
from pathlib import Path
sys.argv = [sys.argv[0], sys.argv[1]] + sys.argv[2:]
ROOT = Path(sys.argv[1]).resolve()
names = sys.argv[2].split(",")
size = tuple(int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "390x844").split("x"))
sys.path.insert(0, str(ROOT / "visual" / "harness"))
import shoot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from PIL import Image  # noqa: E402

out = ROOT / "visual" / "preview"
out.mkdir(exist_ok=True)
server = subprocess.Popen([sys.executable, str(ROOT / "visual/harness/serve.py"), str(ROOT / "visual/client/dist"),
                           str(ROOT / "visual/fixtures"), str(shoot.PORT)])
time.sleep(0.8)
files = []
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shoot.CHROME, args=["--no-sandbox"])
        by = {s[0]: s for s in shoot.SCENES}
        for n in names:
            kw = {}
            base = n
            if n.endswith(":dark"):
                base, kw = n[:-5], {"scheme": "dark"}
            if n.endswith(":hc"):
                base, kw = n[:-3], {"contrast": "more"}
            ctx, page = shoot.open_scene(browser, by[base], size[0], size[1], scale=1, **kw)
            f = out / f"{n.replace(':', '_')}.png"
            page.screenshot(path=str(f))
            if page.errors:
                print(n, page.errors)
            files.append(f)
            ctx.close()
        browser.close()
finally:
    server.terminate()
ims = [Image.open(f) for f in files]
W = sum(i.width for i in ims) + 10 * (len(ims) - 1)
sheet = Image.new("RGB", (W, max(i.height for i in ims)), "white")
x = 0
for i in ims:
    sheet.paste(i, (x, 0)); x += i.width + 10
sheet.save(out / "sheet.png")
print(out / "sheet.png", sheet.size)
