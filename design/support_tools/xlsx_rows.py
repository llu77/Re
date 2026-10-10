import sys, zipfile, re, xml.etree.ElementTree as ET
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
z=zipfile.ZipFile(sys.argv[1])
ss=[]
if 'xl/sharedStrings.xml' in z.namelist():
    r=ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in r.findall('m:si',ns):
        ss.append(''.join(t.text or '' for t in si.iter('{%s}t'%ns['m'])))
sheets=[n for n in z.namelist() if n.startswith('xl/worksheets/sheet')]
want=sys.argv[2]
for s in sheets:
    r=ET.fromstring(z.read(s))
    for row in r.iter('{%s}row'%ns['m']):
        vals=[]
        for c in row.findall('m:c',ns):
            v=c.find('m:v',ns); t=c.get('t')
            if v is None:
                isv=c.find('m:is',ns)
                vals.append(''.join(x.text or '' for x in isv.iter('{%s}t'%ns['m'])) if isv is not None else '')
            elif t=='s': vals.append(ss[int(v.text)])
            else: vals.append(v.text)
        if any(x.strip()==want for x in vals):
            print(s, '|'.join(vals))
