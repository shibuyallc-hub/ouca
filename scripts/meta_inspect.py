import os, json, requests
TOKEN = os.environ['META_ACCESS_TOKEN']; ACC = os.environ['META_AD_ACCOUNT_ID']
if not ACC.startswith('act_'): ACC = 'act_' + ACC
V = 'v21.0'
def get(path, params):
    p = dict(params); p['access_token'] = TOKEN
    r = requests.get(f'https://graph.facebook.com/{V}/{path}', params=p, timeout=60).json()
    if 'error' in r: print('ERROR', path, r['error'].get('message')); return []
    return r.get('data', r)
print('== images ==')
for i in get(f'{ACC}/adimages', {'fields': 'hash,name,width,height', 'limit': 100}):
    print('IMG', i.get('hash'), i.get('name'), i.get('width'), i.get('height'))
print('== ads2 ==')
for a in get(f'{ACC}/ads', {'fields': 'name,status,effective_status,adset{name,daily_budget},campaign{name},creative{asset_feed_spec,object_story_spec,call_to_action_type,url_tags,title,body}', 'limit': 50}):
    c = a.get('creative', {}); f = c.get('asset_feed_spec', {}); o = c.get('object_story_spec', {})
    if 'LP' not in (a.get('campaign') or {}).get('name', ''): continue
    print('AD', a['name'], a['effective_status'], (a.get('adset') or {}).get('name'), 'page', o.get('page_id'), 'ig', o.get('instagram_user_id'))
    print('  bodies:', [b.get('text') for b in f.get('bodies', [])])
    print('  titles:', [t.get('text') for t in f.get('titles', [])])
    print('  descs:', [t.get('text') for t in f.get('descriptions', [])])
    print('  links:', [u.get('website_url') for u in f.get('link_urls', [])], 'cta:', f.get('call_to_action_types'), 'fmt:', f.get('ad_formats'), 'opt:', f.get('optimization_type'))
    print('  images:', [(i.get('hash'), i.get('url_tags')) for i in f.get('images', [])])
    ld = o.get('link_data')
    if ld: print('  link_data:', json.dumps(ld, ensure_ascii=False)[:900])
