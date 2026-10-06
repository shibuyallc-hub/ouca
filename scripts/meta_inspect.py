import os, json, requests
TOKEN = os.environ['META_ACCESS_TOKEN']; ACC = os.environ['META_AD_ACCOUNT_ID']
if not ACC.startswith('act_'): ACC = 'act_' + ACC
V = 'v21.0'
def get(path, params):
    p = dict(params); p['access_token'] = TOKEN
    r = requests.get(f'https://graph.facebook.com/{V}/{path}', params=p, timeout=60).json()
    if 'error' in r: print('ERROR', path, r['error'].get('message')); return []
    return r.get('data', r)
print('== campaigns ==')
for c in get(f'{ACC}/campaigns', {'fields': 'name,objective,status,buying_type,special_ad_categories,smart_promotion_type,bid_strategy,daily_budget', 'limit': 50}):
    print(json.dumps(c, ensure_ascii=False))
print('== adsets ==')
for s in get(f'{ACC}/adsets', {'fields': 'name,status,effective_status,campaign{name},daily_budget,optimization_goal,billing_event,bid_strategy,destination_type,attribution_spec,promoted_object,targeting,start_time,end_time', 'limit': 50}):
    print(json.dumps(s, ensure_ascii=False))
print('== ads ==')
for a in get(f'{ACC}/ads', {'fields': 'name,status,effective_status,adset{name},creative{object_story_spec,url_tags,call_to_action_type,degrees_of_freedom_spec,authorization_category}', 'limit': 50}):
    print(json.dumps(a, ensure_ascii=False)[:1500])
