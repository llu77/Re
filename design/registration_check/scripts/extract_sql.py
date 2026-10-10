import re, sys
s = open(sys.argv[1], encoding='utf-8').read()
up = re.search(r'### 6\.2 .*?```sql\n(.*?)```', s, re.S).group(1)
down = re.search(r'### 6\.3 .*?```sql\n(.*?)```', s, re.S).group(1)
open(sys.argv[2] + '/spec_up.sql', 'w', encoding='utf-8').write(up)
open(sys.argv[2] + '/spec_down.sql', 'w', encoding='utf-8').write(down)
