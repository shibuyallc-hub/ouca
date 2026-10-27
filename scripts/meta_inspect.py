import os, json, re, requests
TOKEN = os.environ['META_ACCESS_TOKEN']; ACC = os.environ['META_AD_ACCOUNT_ID']
if not ACC.startswith('act_'): ACC = 'act_' + ACC
V = 'v21.0'
PAT = re.compile(r'生き|生菌|定着|増え|増や|有効成分|プロバイオ|ビフィズス|乳酸菌|菌を育て|菌を届け|菌の力|腸まで|腸に届|届く')
def get(path, params):
    p = dict(params); p['access_token'] = TOKEN
    r = requests.get(f'https://graph.facebook.com/{V}/{path}', params=p, timeout=60).json()
    if 'error' in r: print('ERROR', path, r['error'].get('message')); return []
    return r.get('data', r)
print('== meta ad copy scan (read-only) ==')
ads = get(f'{ACC}/ads', {'fields': 'name,effective_status,adset{name},campaign{name},creative{body,title,object_story_spec,asset_feed_spec,image_url,thumbnail_url}', 'limit': 200})
for a in ads:
    tag = f"{a.get('campaign', {}).get('name')}/{a.get('adset', {}).get('name')}/{a['name']}[{a['effective_status']}]"
    cr = a.get('creative', {}) or {}
    texts = []
    for k in ('body', 'title'):
        if cr.get(k): texts.append((k, cr[k]))
    oss = cr.get('object_story_spec') or {}
    for k, v in (oss.get('link_data') or {}).items():
        if k in ('message', 'name', 'description', 'caption') and isinstance(v, str): texts.append(('link_data.' + k, v))
    afs = cr.get('asset_feed_spec') or {}
    for k in ('bodies', 'titles', 'descriptions'):
        for x in afs.get(k, []) or []: texts.append(('afs.' + k, x.get('text', '')))
    print('AD|', tag, '| texts:', len(texts))
    for k, t in texts:
        print('   TXT|', k, '|', t.replace('\n', ' / '))
        if PAT.search(t): print('   HIT|', tag, '|', k, '|', t.replace('\n', ' / '))

# rerun 1793111144

# rerun 1793114798

# rerun 1793115132

# rerun 1793115327

# rerun 1793115756

# rerun 1793115821
