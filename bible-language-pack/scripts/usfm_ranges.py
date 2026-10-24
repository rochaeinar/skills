"""usfm_ranges.py <lang>: accept the empty verses that the USFM itself prints as part of a verse range (\\v 6-7).
Prints the empty verses that are NOT inside a range (they need a real look)."""
import sys, json, zipfile, re, collections
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
lang = sys.argv[1]
sys.argv = ['x']
import pack

by = 'Claude (criterio pastoral)'
c_ = pack.cfg()
d = f"{pack.pack_dir(c_, lang).as_posix()}/"
p = json.load(open(d + 'pack.json', encoding='utf-8'))
c = json.load(open(d + 'criteria.json', encoding='utf-8'))
base = f"{c_['bibles_dir'].as_posix()}/"
BS = re.escape(chr(92))
ranges = {}
for b in p['bibles']:
    if not b.get('include') or b.get('role') == 'reference' or not b['file'].endswith('_usfm.zip'):
        continue
    z = zipfile.ZipFile(base + b['file'])
    rs = {}
    for name in z.namelist():
        t = z.read(name).decode('utf-8-sig')
        m = re.search(BS + r'id (\w+)', t)
        if not m:
            continue
        bk = pack.ALIASES.get(m.group(1)[:3].upper(), m.group(1)[:3].upper())
        ch = 0
        for line in t.split('\n'):
            mc = re.match(BS + r'c (\d+)', line)
            if mc:
                ch = int(mc.group(1))
            for mv in re.finditer(BS + r'v (\d+)[‎‏]*[-–‑][‎‏]*(\d+)', line):  # bidi marks around the dash in Persian/Arabic USFM ("26‏-47")
                a, z2 = int(mv.group(1)), int(mv.group(2))
                for v in range(a + 1, z2 + 1):
                    rs[(bk, ch, v)] = f'{a}-{z2}'
    ranges[b['id']] = rs
n, left = 0, collections.defaultdict(list)
for e in c['issues']:
    if e.get('decision') or e['check'] != 'estructura' or e['bible'] not in ranges:
        continue
    m = re.match(r'(\w+) (\d+):(\d+)$', e['ref'] or '')
    if not m:
        continue
    k = (m.group(1), int(m.group(2)), int(m.group(3)))
    r = ranges[e['bible']].get(k)
    if r:
        e['decision'] = {'action': 'accept', 'decided_by': by,
                         'note': f'Versículo combinado: el USFM de la propia traducción lo numera como rango («\\v {r}») y el texto de todos esos versículos está en el primero. Se lee entero; solo queda vacío el número.'}
        n += 1
    else:
        left[e['bible']].append((e['level'], e['ref'], e['detail'][:60]))
json.dump(c, open(d + 'criteria.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(lang, 'accepted as ranges:', n, {k: len(v) for k, v in ranges.items()})
for b, L in left.items():
    print(' ', b, len(L), 'not in a range:')
    for x in L[:40]:
        print('    ', x)
