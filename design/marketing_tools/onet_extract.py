import re, sys, html
src = open(sys.argv[1], encoding="utf-8").read()
# Find the Tasks section rows
def sect(name):
    i = src.find(f'id="{name}"')
    return src[i:i+60000] if i >= 0 else ""
def text(s):
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()
for name in ["Tasks", "TechnologySkills", "WorkActivities", "DetailedWorkActivities"]:
    s = sect(name)
    print("=====", name, len(s))
    rows = re.findall(r"<tr.*?</tr>", s, flags=re.S)
    for r in rows[:40]:
        t = text(r)
        if t: print("-", t[:400])
