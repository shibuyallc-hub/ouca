"""Meta広告の新構成を「一時停止(PAUSED)」で作成。公開はしない。べき等：同名キャンペーンがあれば作成しない。
mode: apply / cleanup"""
import os, sys, json, glob, requests
MODE = (sys.argv[1] if len(sys.argv) > 1 else 'apply').strip()
TOKEN = os.environ['META_ACCESS_TOKEN']; ACC = os.environ['META_AD_ACCOUNT_ID']
if not ACC.startswith('act_'): ACC = 'act_' + ACC
V = 'v21.0'; BASE = f'https://graph.facebook.com/{V}'
PAGE, IG = '104217839436273', '17841460827331276'
UTM = 'utm_source=facebook&utm_medium=cpc&utm_campaign={{campaign.name}}&utm_content={{ad.name}}'
META = json.load(open('ads_setup/config.json', encoding='utf-8'))['META']

def call(method, path, data=None, files=None, params=None):
    d = dict(data or {}); d['access_token'] = TOKEN
    if method == 'GET':
        r = requests.get(f'{BASE}/{path}', params={**(params or {}), 'access_token': TOKEN}, timeout=90)
    else:
        r = requests.post(f'{BASE}/{path}', data=d, files=files, timeout=180)
    j = r.json()
    if 'error' in j:
        e = j['error']; print('  ERROR', path, '|', e.get('message'), '|', e.get('error_user_title', ''), '|', e.get('error_user_msg', ''), '| code', e.get('code'), e.get('error_subcode'))
        return None
    return j

existing = {c['name']: c['id'] for c in (call('GET', f'{ACC}/campaigns', params={'fields': 'name,status', 'limit': 200}) or {}).get('data', [])}
SPEC = {
 'LP1': dict(camp='OUCA_LP1', adset='LP1_腸活・女性', age_min=35,
             ads=[('LP1-A_世界観', 'lp1_sq_woman'), ('LP1-B_成分の違い', 'lp1_sq_pouch_box'), ('LP1-C_トライアル', 'lp1_sq_marble')]),
 'LP2': dict(camp='OUCA_LP2', adset='LP2_経営者・男性', age_min=40,
             ads=[('LP2-A_投資', 'lp2_sq_man'), ('LP2-B_価格の理由', 'lp2_sq_bag'), ('LP2-C_品質', 'lp2_sq_pouches')]),
}

if MODE == 'cleanup':
    for k, sp in SPEC.items():
        cid = existing.get(sp['camp'])
        if cid:
            r = call('POST', cid, {'status': 'DELETED'}); print('deleted', sp['camp'], r)
    sys.exit(0)

def upload(name):
    f = f'ads_setup/images/{name}.jpg'
    j = call('POST', f'{ACC}/adimages', files={'filename': (name + '.jpg', open(f, 'rb'), 'image/jpeg')})
    if not j: return None
    return list(j['images'].values())[0]['hash']

for key, sp in SPEC.items():
    m = META[key]; url = m['url']
    if sp['camp'] in existing: print('SKIP (exists):', sp['camp']); continue
    print('==', sp['camp'])
    hashes = {}
    for _, img in sp['ads']:
        hashes[img] = upload(img); print('  image', img, hashes[img])
    camp = call('POST', f'{ACC}/campaigns', {'name': sp['camp'], 'objective': 'OUTCOME_SALES', 'status': 'PAUSED',
        'special_ad_categories': json.dumps([]), 'buying_type': 'AUCTION', 'is_adset_budget_sharing_enabled': 'false'})
    if not camp: continue
    cid = camp['id']; print('  campaign', cid)
    base_t = {'geo_locations': {'countries': ['JP']}, 'age_min': sp['age_min'], 'age_max': 65,
              'targeting_automation': {'advantage_audience': 1}}
    adset = None
    for plats in (['facebook', 'instagram', 'threads'], ['facebook', 'instagram']):
        t = dict(base_t, publisher_platforms=plats)
        adset = call('POST', f'{ACC}/adsets', {'name': sp['adset'], 'campaign_id': cid, 'daily_budget': 2500, 'billing_event': 'IMPRESSIONS',
            'optimization_goal': 'LANDING_PAGE_VIEWS', 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'destination_type': 'WEBSITE',
            'targeting': json.dumps(t), 'status': 'PAUSED'})
        if adset: print('  adset', adset['id'], 'platforms', plats); break
    if not adset: continue
    heads = m['heads']
    for i, (adname, img) in enumerate(sp['ads']):
        if not hashes.get(img): continue
        story = {'page_id': PAGE, 'instagram_user_id': IG, 'link_data': {
            'link': url, 'message': m['prims'][i], 'name': heads[i], 'description': m['desc'],
            'image_hash': hashes[img], 'call_to_action': {'type': 'LEARN_MORE', 'value': {'link': url}}}}
        cr = call('POST', f'{ACC}/adcreatives', {'name': adname, 'object_story_spec': json.dumps(story), 'url_tags': UTM})
        if not cr: continue
        ad = call('POST', f'{ACC}/ads', {'name': adname, 'adset_id': adset['id'], 'creative': json.dumps({'creative_id': cr['id']}), 'status': 'PAUSED'})
        print('  ad', adname, ad and ad['id'])
print('done')
