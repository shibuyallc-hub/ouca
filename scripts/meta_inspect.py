import os, json, requests
TOKEN = os.environ['META_ACCESS_TOKEN']; ACC = os.environ['META_AD_ACCOUNT_ID']
if not ACC.startswith('act_'): ACC = 'act_' + ACC
V = 'v21.0'
def get(path, params):
    p = dict(params); p['access_token'] = TOKEN
    out = []; url = f'https://graph.facebook.com/{V}/{path}'
    while url:
        r = requests.get(url, params=p if 'access_token' not in url else None, timeout=60)
        j = r.json()
        if 'error' in j: print('ERROR', path, j['error'].get('message')); return out
        out += j.get('data', [])
        url = j.get('paging', {}).get('next'); p = {}
    return out
print('== account ==')
r = requests.get(f'https://graph.facebook.com/{V}/{ACC}', params={'fields': 'name,currency,timezone_name,account_status,amount_spent', 'access_token': TOKEN}).json()
print(json.dumps(r, ensure_ascii=False))
print('== campaigns ==')
for c in get(f'{ACC}/campaigns', {'fields': 'id,name,objective,status,effective_status,daily_budget,lifetime_budget,buying_type,special_ad_categories,bid_strategy', 'limit': 100}):
    print(json.dumps(c, ensure_ascii=False))
print('== adsets ==')
for a in get(f'{ACC}/adsets', {'fields': 'id,name,campaign_id,status,effective_status,daily_budget,optimization_goal,billing_event,bid_strategy,promoted_object,destination_type,targeting,attribution_spec', 'limit': 100}):
    t = a.get('targeting', {})
    a['targeting'] = {k: t.get(k) for k in ('age_min', 'age_max', 'genders', 'geo_locations', 'publisher_platforms', 'facebook_positions', 'instagram_positions', 'device_platforms', 'flexible_spec', 'interests', 'custom_audiences', 'excluded_custom_audiences', 'targeting_automation', 'locales') if t.get(k) is not None}
    print(json.dumps(a, ensure_ascii=False))
print('== ads ==')
for a in get(f'{ACC}/ads', {'fields': 'id,name,adset_id,campaign_id,status,effective_status,creative{id,name,title,body,object_story_spec,link_url,url_tags,call_to_action_type,image_url,thumbnail_url,asset_feed_spec,effective_object_story_id}', 'limit': 100}):
    print(json.dumps(a, ensure_ascii=False)[:2500])
print('== insights by ad (lifetime) ==')
for i in get(f'{ACC}/insights', {'level': 'ad', 'date_preset': 'maximum', 'fields': 'ad_name,adset_name,campaign_name,spend,impressions,reach,frequency,clicks,inline_link_clicks,inline_link_click_ctr,cpc,cpm,actions,cost_per_action_type,purchase_roas', 'limit': 100}):
    print(json.dumps(i, ensure_ascii=False)[:1200])
print('== insights by age/gender/placement (lifetime) ==')
for bd in ('age', 'gender', 'publisher_platform', 'platform_position'):
    for i in get(f'{ACC}/insights', {'level': 'account', 'date_preset': 'maximum', 'breakdowns': bd, 'fields': 'spend,impressions,clicks,inline_link_clicks,actions', 'limit': 100}):
        acts = {x['action_type']: x['value'] for x in i.get('actions', [])} if i.get('actions') else {}
        print(bd, i.get(bd), 'spend', i.get('spend'), 'imp', i.get('impressions'), 'clicks', i.get('clicks'), 'link_clicks', i.get('inline_link_clicks'), {k: acts[k] for k in acts if k in ('landing_page_view', 'purchase', 'omni_purchase', 'initiate_checkout', 'omni_initiated_checkout', 'add_to_cart')})
