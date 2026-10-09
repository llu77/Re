import sys, unicodedata, re
for line in open(sys.argv[1], encoding='utf-8'):
    s = unicodedata.normalize('NFKC', line.rstrip('\n'))
    print(' '.join(t[::-1] if re.search('[؀-ۿ]', t) else t for t in s.split()))
