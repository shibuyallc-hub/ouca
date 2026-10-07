import os, json, requests
TOKEN = os.environ['META_ACCESS_TOKEN']; ACC = os.environ['META_AD_ACCOUNT_ID']
if not ACC.startswith('act_'): ACC = 'act_' + ACC
V = 'v21.0'
def get(path, params):
    p = dict(params); p['access_token'] = TOKEN
    r = requests.get(f'https://graph.facebook.com/{V}/{path}', params=p, timeout=60).json()
    if 'error' in r: print('ERROR', path, r['error'].get('message')); return []
    return r.get('data', r)
print('== meta daily ==')
for i in get(f'{ACC}/insights', {'level': 'campaign', 'time_increment': 1, 'time_range': json.dumps({'since': '2026-09-01', 'until': '2026-10-07'}), 'fields': 'campaign_name,spend,impressions,clicks,inline_link_clicks,actions', 'limit': 500}):
    acts = {x['action_type']: x['value'] for x in i.get('actions', [])} if i.get('actions') else {}
    pur = max([float(acts.get(k, 0)) for k in ('purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase')] or [0])
    print('MD|', i['date_start'], '|', i['campaign_name'], '|', i['spend'], '|', i['impressions'], '|', i.get('clicks'), '|', i.get('inline_link_clicks'), '|', pur, '|', acts.get('landing_page_view', 0))
