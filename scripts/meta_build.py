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

if MODE == 'noop': sys.exit(0)
if MODE == 'scrape':
    # リンクプレビューのキャッシュ更新（OGPの再取得）。広告の設定は変えない
    for u in ('https://ouca.today/lp?u=lp-executive', 'https://ouca.today/lp?u=lp-supplement'):
        r = requests.post(f'{BASE}/', data={'id': u, 'scrape': 'true', 'access_token': TOKEN}, timeout=90).json()
        print('SCRAPE|', u, '|', json.dumps({k: r.get(k) for k in ('title', 'description', 'updated_time', 'error')}, ensure_ascii=False)[:500])
    sys.exit(0)
if MODE == 'perm':
    print('PERM|', json.dumps(call('GET', 'me/permissions') or {}, ensure_ascii=False))
    print('ME|', json.dumps(call('GET', 'me', params={'fields': 'id,name'}) or {}, ensure_ascii=False))
    print('ACC|', json.dumps(call('GET', ACC, params={'fields': 'id,name,account_status,currency,business{id,name}'}) or {}, ensure_ascii=False))
    print('CAN|', json.dumps(call('GET', f'{ACC}/assigned_users', params={'fields': 'id,name,tasks', 'business': ''}) or {}, ensure_ascii=False)[:600])
    print('PAGES|', json.dumps(call('GET', 'me/accounts', params={'fields': 'id,name,tasks', 'limit': 20}) or {}, ensure_ascii=False)[:800])
    sys.exit(0)
if MODE in ('edit_list', 'edit'):
    # 配信中の既存広告の文面を差し替え（新しいクリエイティブを作って広告に付け替える）。一時停止中の広告は対象外
    import functools
    APPLY = (MODE == 'edit')
    TARGETS = ('c-1_', 'c-2_', 'a-2_', 'b-1_', 'b-2_')
    RULES = [('1ヶ月19,980円（初回15%OFFで16,983円）', '1袋10,800円（初回60%OFFで4,320円）'),
             ('1ヶ月19,980円。1日あたりに直すと、約666円です。', '1袋10,800円。1日あたりに直すと、約720円です。初回は4,320円。'),
             ('1ヶ月19,980円', '1袋10,800円'), ('1日約666円', '1日約720円'),
             ('2粒で酪酸発酵物222mg', '1粒で酪酸発酵物111mg'), ('2粒に酪酸発酵物222mg', '1粒に酪酸発酵物111mg'),
             ('2粒に222mg', '1粒に111mg'), ('2粒222mg', '1粒111mg'), ('15%OFF', '60%OFF'),
             ('まずは1ヶ月', 'まずは1袋'), ('まず1ヶ月', 'まず1袋'), ('1ヶ月試して', '1袋試して')]
    fix = lambda t: functools.reduce(lambda x, r: x.replace(*r), RULES, t)
    changes = []
    def walk(o):
        if isinstance(o, str):
            n = fix(o)
            if n != o: changes.append((o, n))
            return n
        if isinstance(o, list): return [walk(x) for x in o]
        if isinstance(o, dict): return {k: walk(v) for k, v in o.items()}
        return o
    ads = (call('GET', f'{ACC}/ads', params={'fields': 'id,name,effective_status,status,campaign{name},creative{id,name,object_story_spec,asset_feed_spec,url_tags,degrees_of_freedom_spec,platform_customizations}', 'limit': 200}) or {}).get('data', [])
    for a in ads:
        if a['campaign']['name'] != 'OUCA' or a.get('status') != 'ACTIVE' or not a['name'].startswith(TARGETS): continue
        cr = a['creative']; changes.clear()
        oss = walk(cr.get('object_story_spec')) if cr.get('object_story_spec') else None
        afs = walk(cr.get('asset_feed_spec')) if cr.get('asset_feed_spec') else None
        print('AD|', a['id'], a['name'], '| old creative', cr['id'], '| keys', [k for k in cr if k not in ('id',)], '|', len(changes), 'text changes')
        if not changes: continue
        for o, n in changes[:40]: print('    ', o.replace('\n', ' / ')[:150], '=>', n.replace('\n', ' / ')[:150])
        if not APPLY: continue
        data = {'name': cr['name'] + '_v2'}
        if oss: data['object_story_spec'] = json.dumps(oss)
        if afs: data['asset_feed_spec'] = json.dumps(afs)
        if cr.get('url_tags'): data['url_tags'] = cr['url_tags']
        if cr.get('degrees_of_freedom_spec'): data['degrees_of_freedom_spec'] = json.dumps(cr['degrees_of_freedom_spec'])
        if cr.get('platform_customizations'): data['platform_customizations'] = json.dumps(cr['platform_customizations'])
        new = call('POST', f'{ACC}/adcreatives', data)
        if not new: print('  FAILED create creative for', a['name']); continue
        r = call('POST', a['id'], {'creative': json.dumps({'creative_id': new['id']})})
        print('  ', 'OK' if r else 'FAILED', 'ad', a['name'], 'creative', cr['id'], '->', new['id'])
    print('done', MODE); sys.exit(0)
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
