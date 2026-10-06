import os, json, requests
TOKEN = os.environ['META_ACCESS_TOKEN']; ACC = os.environ['META_AD_ACCOUNT_ID']
if not ACC.startswith('act_'): ACC = 'act_' + ACC
V = 'v21.0'
def get(path, params):
    p = dict(params); p['access_token'] = TOKEN
    r = requests.get(f'https://graph.facebook.com/{V}/{path}', params=p, timeout=60).json()
    if 'error' in r: print('ERROR', path, r['error'].get('message')); return []
    return r.get('data', r)
print('== ad creatives detail ==')
for a in get(f'{ACC}/ads', {'fields': 'name,creative{asset_feed_spec,object_story_spec,title,body,link_url,call_to_action_type}', 'limit': 50}):
    c = a.get('creative', {}); f = c.get('asset_feed_spec', {})
    print('AD', a['name'])
    print('  bodies:', [b.get('text') for b in f.get('bodies', [])])
    print('  titles:', [t.get('text') for t in f.get('titles', [])])
    print('  descriptions:', [t.get('text') for t in f.get('descriptions', [])])
    print('  link_urls:', [u.get('website_url') for u in f.get('link_urls', [])], 'cta:', f.get('call_to_action_types'), 'optimization:', f.get('optimization_type'), 'ad_formats:', f.get('ad_formats'))
    print('  n_images:', len(f.get('images', [])), 'n_videos:', len(f.get('videos', [])))
print('== pixel ==')
for p in get(f'{ACC}/adspixels', {'fields': 'id,name,last_fired_time'}): 
    print(json.dumps(p, ensure_ascii=False))
    for st in get(f"{p['id']}/stats", {'aggregation': 'event', 'start_time': '2026-09-01'}) if isinstance(p, dict) else []:
        print('  stats', json.dumps(st, ensure_ascii=False)[:600])
print('== daily spend (last 20d) ==')
for i in get(f'{ACC}/insights', {'level': 'account', 'time_increment': 1, 'date_preset': 'last_30d', 'fields': 'spend,impressions,clicks,actions', 'limit': 40}):
    acts = {x['action_type']: x['value'] for x in i.get('actions', [])} if i.get('actions') else {}
    print(i['date_start'], i['spend'], i['impressions'], i['clicks'], {k: acts[k] for k in acts if k in ('landing_page_view', 'purchase', 'omni_purchase', 'initiate_checkout', 'omni_initiated_checkout', 'view_content')})
