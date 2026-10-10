import sys, re, html
from html.parser import HTMLParser
class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.out=[]; self.skip=0
    def handle_starttag(self, t, a):
        if t in ('script','style','noscript','svg'): self.skip+=1
        if t in ('p','div','li','tr','h1','h2','h3','h4','br','td','th','section','dt','dd'): self.out.append('\n')
    def handle_endtag(self, t):
        if t in ('script','style','noscript','svg'): self.skip-=1
    def handle_data(self, d):
        if not self.skip: self.out.append(d)
p=P(); p.feed(open(sys.argv[1], encoding='utf-8', errors='replace').read())
txt=''.join(p.out)
txt=re.sub(r'[ \t]+',' ',txt); txt=re.sub(r'\n\s*\n+','\n',txt)
print(txt)
