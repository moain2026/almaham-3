import json,collections
I=json.load(open('/tmp/agD/h7/items.json')); L=json.load(open('/tmp/agD/h7/owner_labels.json'))['labels']
S=collections.defaultdict(dict)
for l in open('/tmp/mm/strong.jsonl'):
    d=json.loads(l); S[d['f']][d['m']]=d['ans']
out=[]
for l in sorted(L,key=lambda x:x['n']):
    r=l['reading']
    if not r.isdigit(): continue
    m=[a for a in S.get(l['filename'],{}).values() if a.isdigit()]
    c=collections.Counter(m)
    o=r.lstrip('0') or '0'
    match=[a for a in m if (a.lstrip('0') or '0')==o]
    dec=[a for a in m if (a.lstrip('0') or '0')==(o[:-1].lstrip('0') or '0') and len(o)>1]
    if match: cat='agree'
    elif dec and len(dec)>=2: cat='decimal'
    elif not m: cat='nomodel'
    else: cat='disagree'
    out.append(dict(n=l['n'],f=l['filename'],t=l['type'],r=r,m=dict(c),cat=cat))
json.dump(out,open('/tmp/mm/own7.json','w'))
print(collections.Counter(o['cat'] for o in out))
for o in out:
    if o['cat']!='agree': print(o['n'],o['t'][:10],o['r'],o['m'],o['cat'])
