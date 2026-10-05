"""新構成のGoogle広告を「一時停止」で作成する。公開(有効化)はしない。
べき等：同名のキャンペーンがあれば作成しない。"""
import json, os, sys, glob, unicodedata, traceback
from google.ads.googleads.errors import GoogleAdsException

def wd(s): return sum(2 if unicodedata.east_asian_width(c) in 'WFA' else 1 for c in s)

def run(client, CID, MODE):
    ga = client.get_service("GoogleAdsService")
    E = client.enums
    cfg = json.load(open('ads_setup/config.json', encoding='utf-8'))
    LP = {'LP1': cfg['LP1'], 'LP2': cfg['LP2']}
    TCPA = 20_000_000_000
    SUF_S = 'utm_source=google&utm_medium=cpc&utm_campaign={campaignid}&utm_content={adgroupid}'
    SUF_P = 'utm_source=google&utm_medium=cpc&utm_campaign={campaignid}'
    A_BUSINESS, A_LOGO, A_LLOGO, A_SNIPPET = 420542818405, 422457716110, 422541197196, 420554566963
    CALLOUTS = [420445899503, 420445899506, 420445922297, 420445922300, 420445922303, 420445922306,
                420445922309, 420445922312, 420629474283, 420629543751, 420629543757]  # 初回10%OFF(…315)は除外
    VIDEOS_LP1 = [422920094248, 422921784307]
    NAMES = {'S1': '検索_LP1', 'S2': '検索_LP2_高価格・経営者', 'P1': 'P-Max_LP1', 'P2': 'P-Max_LP2'}
    BUDGET = {'S1': 1300, 'S2': 1300, 'P1': 1950, 'P2': 1950}

    def q(g): return list(ga.search(customer_id=CID, query=g))
    def cust(x): return f"customers/{CID}/{x}"

    if MODE == 'cleanup':
        for r in q("SELECT campaign.id, campaign.name, campaign.status, campaign_budget.resource_name FROM campaign WHERE campaign.status != 'REMOVED'"):
            if r.campaign.name in NAMES.values():
                if r.campaign.status.name != 'PAUSED':
                    print("SKIP (not paused):", r.campaign.name); continue
                svc = client.get_service("CampaignService"); op = client.get_type("CampaignOperation")
                op.remove = f"customers/{CID}/campaigns/{r.campaign.id}"
                svc.mutate_campaigns(customer_id=CID, operations=[op]); print("removed", r.campaign.name)
        return

    # ---------- 既存情報 ----------
    existing_campaigns = {r.campaign.name: r.campaign.id for r in q("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED'")}
    def load_text_assets():
        d = {}
        for r in q("SELECT asset.resource_name, asset.text_asset.text FROM asset WHERE asset.type = 'TEXT'"):
            d[r.asset.text_asset.text] = r.asset.resource_name
        return d
    text_assets = load_text_assets()
    named_assets = {}
    for r in q("SELECT asset.resource_name, asset.name, asset.type FROM asset WHERE asset.type IN ('IMAGE','CALL_TO_ACTION')"):
        named_assets[(r.asset.type.name, r.asset.name)] = r.asset.resource_name
    # 既存の除外キーワード（他社名など）を新キャンペーンにも引き継ぐ
    neg_by_camp = {}
    for r in q("SELECT campaign.name, campaign_criterion.keyword.text FROM campaign_criterion WHERE campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'"):
        neg_by_camp.setdefault(r.campaign.name, []).append(r.campaign_criterion.keyword.text)
    neg_search = list(dict.fromkeys(neg_by_camp.get('OUCA_supplement_search', []) + cfg['NEG']))
    neg_pmax = list(dict.fromkeys(neg_by_camp.get('ouca_supplement_pmax', []) + cfg['NEG']))
    print("引き継ぐ除外KW:", len(neg_search), len(neg_pmax))

    # ---------- 画像アセット：現行P-Maxのアセットグループで使われている画像・動画をそのまま使う ----------
    asvc = client.get_service("AssetService")
    EXCLUDE_PREFIX = ('ouca_a-1',)     # 「初回10%OFF」表記を含むバナー（現在の特典は15%OFF）
    cur_media = {'MARKETING_IMAGE': [], 'SQUARE_MARKETING_IMAGE': [], 'PORTRAIT_MARKETING_IMAGE': [],
                 'TALL_PORTRAIT_MARKETING_IMAGE': [], 'YOUTUBE_VIDEO': []}
    for r in q("""SELECT asset_group_asset.field_type, asset.resource_name, asset.name FROM asset_group_asset
                  WHERE asset_group.id = 6746797318 AND asset_group_asset.status != 'REMOVED'"""):
        ft = r.asset_group_asset.field_type.name
        if ft in cur_media and not r.asset.name.startswith(EXCLUDE_PREFIX):
            cur_media[ft].append(r.asset.resource_name)
    print("現行P-Maxの画像・動画:", {k: len(v) for k, v in cur_media.items()})

    # ---------- ヘルパー ----------
    class Ops:
        def __init__(self): self.ops = []; self.n = 0
        def new(self, field):
            m = client.get_type("MutateOperation"); obj = getattr(m, field).create
            self.ops.append(m); return obj
        def tmp(self): self.n -= 1; return self.n
    def mutate(ops, label):
        try:
            res = ga.mutate(customer_id=CID, mutate_operations=ops.ops)
            print("OK:", label, len(ops.ops), "operations")
            return res
        except GoogleAdsException as ex:
            print("FAILED:", label)
            for e in ex.failure.errors:
                path = '.'.join(p.field_name + (f"[{p.index}]" if getattr(p, 'index', 0) else '') for p in e.location.field_path_elements)
                if 'not found' in e.message.lower() and 'campaign' in path: continue   # 後続の連鎖エラーは省略
                print("  -", str(e.error_code).replace(chr(10), ' '), "|", e.message, "|", path)
            return None

    def add_campaign_common(o, key, channel):
        bt, ct = o.tmp(), o.tmp()
        b = o.new('campaign_budget_operation')
        b.resource_name = ga.campaign_budget_path(CID, bt); b.name = 'adsx_budget_' + NAMES[key]
        b.amount_micros = BUDGET[key] * 1_000_000; b.delivery_method = E.BudgetDeliveryMethodEnum.STANDARD
        b.explicitly_shared = False
        c = o.new('campaign_operation')
        c.resource_name = ga.campaign_path(CID, ct); c.name = NAMES[key]; c.status = E.CampaignStatusEnum.PAUSED
        c.advertising_channel_type = channel; c.campaign_budget = b.resource_name
        c.contains_eu_political_advertising = E.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
        c.geo_target_type_setting.positive_geo_target_type = E.PositiveGeoTargetTypeEnum.PRESENCE
        return c
    def add_geo_lang_neg(o, c, negs):
        g = o.new('campaign_criterion_operation'); g.campaign = c.resource_name; g.location.geo_target_constant = 'geoTargetConstants/2392'
        l = o.new('campaign_criterion_operation'); l.campaign = c.resource_name; l.language.language_constant = 'languageConstants/1005'
        for t in negs:
            n = o.new('campaign_criterion_operation'); n.campaign = c.resource_name; n.negative = True
            n.keyword.text = t; n.keyword.match_type = E.KeywordMatchTypeEnum.PHRASE
    def text_asset_rn(o, text):
        if text in text_assets: return text_assets[text]
        t = o.tmp(); a = o.new('asset_operation'); a.resource_name = ga.asset_path(CID, t); a.text_asset.text = text
        text_assets[text] = a.resource_name; return a.resource_name
    def link_campaign_asset(o, c, asset_rn, field):
        ca = o.new('campaign_asset_operation'); ca.campaign = c.resource_name; ca.asset = asset_rn; ca.field_type = field

    def extensions(o, c, lp):
        for aid in CALLOUTS: link_campaign_asset(o, c, ga.asset_path(CID, aid), E.AssetFieldTypeEnum.CALLOUT)
        # 新しい訴求（初回15%OFF）
        t = o.tmp(); a = o.new('asset_operation'); a.resource_name = ga.asset_path(CID, t); a.callout_asset.callout_text = '初回15%OFF'
        link_campaign_asset(o, c, a.resource_name, E.AssetFieldTypeEnum.CALLOUT)
        link_campaign_asset(o, c, ga.asset_path(CID, A_SNIPPET), E.AssetFieldTypeEnum.STRUCTURED_SNIPPET)
        url = LP[lp]
        if lp == 'LP1':
            sl = [('初回15%OFF・送料無料', '¥19,980／30日分', '1日1〜3粒。まずは1ヶ月から', url + '#order'),
                  ('OUCAのこだわり1', '40年の研究と1000日発酵', '菌でなく酪酸そのものを配合', url + '#features1'),
                  ('OUCAのこだわり2', '国内GMP工場で製造', '腸で生まれる「酪酸」という存在', url + '#features2'),
                  ('よくあるご質問', '成分・アレルギー表示を確認', '飲み方などの疑問に回答', url + '#qa')]
        else:
            sl = [('初回15%OFF・送料無料', '¥19,980／30日分', 'まず1ヶ月、自分に投資する', url + '#offer'),
                  ('高い。だが中身が違う', '約1000日発酵の酪酸発酵物', '1粒に酪酸発酵物111mg', url + '#s3'),
                  ('選んだ経営者の声', '経営者の方々の声を紹介', '再注文・まとめ買いも', url + '#s2'),
                  ('よくあるご質問', '成分・アレルギー表示を確認', '飲み方などの疑問に回答', url + '#s7')]
        for txt, d1, d2, u in sl:
            assert wd(txt) <= 25 and wd(d1) <= 35 and wd(d2) <= 35, (txt, d1, d2)
            t = o.tmp(); a = o.new('asset_operation'); a.resource_name = ga.asset_path(CID, t)
            a.sitelink_asset.link_text = txt; a.sitelink_asset.description1 = d1; a.sitelink_asset.description2 = d2; a.final_urls.append(u)
            link_campaign_asset(o, c, a.resource_name, E.AssetFieldTypeEnum.SITELINK)

    # ---------- 検索キャンペーン ----------
    def build_search(key, lp, groups, heads, descs):
        name = NAMES[key]
        if name in existing_campaigns: print("SKIP (exists):", name); return
        o = Ops(); c = add_campaign_common(o, key, E.AdvertisingChannelTypeEnum.SEARCH)
        c.maximize_conversions.target_cpa_micros = TCPA
        c.network_settings.target_google_search = True; c.network_settings.target_search_network = False
        c.network_settings.target_content_network = False; c.network_settings.target_partner_search_network = False
        c.final_url_suffix = SUF_S
        add_geo_lang_neg(o, c, neg_search)
        for g in groups:
            gt = o.tmp(); ag = o.new('ad_group_operation')
            ag.resource_name = ga.ad_group_path(CID, gt); ag.name = g['ag']; ag.campaign = c.resource_name
            ag.status = E.AdGroupStatusEnum.ENABLED; ag.type_ = E.AdGroupTypeEnum.SEARCH_STANDARD
            for kw in g['kws']:
                for mt in (E.KeywordMatchTypeEnum.EXACT, E.KeywordMatchTypeEnum.PHRASE):
                    k = o.new('ad_group_criterion_operation'); k.ad_group = ag.resource_name
                    k.status = E.AdGroupCriterionStatusEnum.ENABLED; k.keyword.text = kw; k.keyword.match_type = mt
            ad = o.new('ad_group_ad_operation'); ad.ad_group = ag.resource_name; ad.status = E.AdGroupAdStatusEnum.ENABLED
            ad.ad.final_urls.append(LP[lp]); r = ad.ad.responsive_search_ad
            for i, h in enumerate(heads):
                assert wd(h) <= 30, h
                t = client.get_type("AdTextAsset"); t.text = h
                if i == 0: t.pinned_field = E.ServedAssetFieldTypeEnum.HEADLINE_1
                r.headlines.append(t)
            for d in descs:
                assert wd(d) <= 90, d
                t = client.get_type("AdTextAsset"); t.text = d; r.descriptions.append(t)
            r.path1 = 'OUCA'; r.path2 = 'supplement'
        extensions(o, c, lp)
        mutate(o, name)

    kw_groups = cfg['KW']
    lp1_groups = [g for g in kw_groups if g['url'] == cfg['LP1']]
    lp2_groups = [g for g in kw_groups if g['url'] == cfg['LP2']]
    build_search('S1', 'LP1', lp1_groups, cfg['LP1_H'], cfg['LP1_D'])
    build_search('S2', 'LP2', lp2_groups, cfg['LP2_H'], cfg['LP2_D'])

    # ---------- P-Max ----------
    cta_rn = named_assets.get(('CALL_TO_ACTION', 'adsx_cta_learn_more'))
    if not cta_rn:
        op = client.get_type("AssetOperation"); a = op.create; a.name = 'adsx_cta_learn_more'
        a.call_to_action_asset.call_to_action = E.CallToActionTypeEnum.LEARN_MORE
        try:
            cta_rn = asvc.mutate_assets(customer_id=CID, operations=[op]).results[0].resource_name
        except GoogleAdsException as ex:
            print("CTA asset failed:", ex.failure.errors[0].message)

    def build_pmax(key, lp, heads, longs, short, descs, imgs=None, videos=None):
        name = NAMES[key]
        if name in existing_campaigns: print("SKIP (exists):", name); return
        text_assets.clear(); text_assets.update(load_text_assets())
        o = Ops(); c = add_campaign_common(o, key, E.AdvertisingChannelTypeEnum.PERFORMANCE_MAX)
        client.copy_from(c.maximize_conversions, client.get_type("MaximizeConversions"))
        c.final_url_suffix = SUF_P
        for t in ('FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION', 'TEXT_ASSET_AUTOMATION',
                  'GENERATE_IMAGE_ENHANCEMENT', 'GENERATE_IMAGE_EXTRACTION', 'GENERATE_DESIGN_VERSIONS_FOR_IMAGES'):
            s = client.get_type("Campaign").AssetAutomationSetting()
            s.asset_automation_type = getattr(E.AssetAutomationTypeEnum, t); s.asset_automation_status = E.AssetAutomationStatusEnum.OPTED_OUT
            c.asset_automation_settings.append(s)
        add_geo_lang_neg(o, c, neg_pmax)
        gt = o.tmp(); ag = o.new('asset_group_operation')
        ag.resource_name = ga.asset_group_path(CID, gt); ag.name = NAMES[key] + '_AG1'; ag.campaign = c.resource_name
        ag.status = E.AssetGroupStatusEnum.ENABLED; ag.final_urls.append(LP[lp]); ag.path1 = 'OUCA'; ag.path2 = 'supplement'
        def link(asset_rn, field):
            x = o.new('asset_group_asset_operation'); x.asset_group = ag.resource_name; x.asset = asset_rn; x.field_type = field
        for h in heads: assert wd(h) <= 30, h; link(text_asset_rn(o, h), E.AssetFieldTypeEnum.HEADLINE)
        for l in longs: assert wd(l) <= 90, l; link(text_asset_rn(o, l), E.AssetFieldTypeEnum.LONG_HEADLINE)
        assert wd(short) <= 60, short; link(text_asset_rn(o, short), E.AssetFieldTypeEnum.DESCRIPTION)
        for d in descs: assert wd(d) <= 90, d; link(text_asset_rn(o, d), E.AssetFieldTypeEnum.DESCRIPTION)
        link_campaign_asset(o, c, ga.asset_path(CID, A_BUSINESS), E.AssetFieldTypeEnum.BUSINESS_NAME)
        link_campaign_asset(o, c, ga.asset_path(CID, A_LOGO), E.AssetFieldTypeEnum.LOGO)
        link_campaign_asset(o, c, ga.asset_path(CID, A_LLOGO), E.AssetFieldTypeEnum.LANDSCAPE_LOGO)
        for ft, rns in cur_media.items():
            for rn_ in rns: link(rn_, getattr(E.AssetFieldTypeEnum, ft))
        if cta_rn: link(cta_rn, E.AssetFieldTypeEnum.CALL_TO_ACTION_SELECTION)
        extensions(o, c, lp)
        mutate(o, name)

    IM1 = {'land': ['lp1_land_woman', 'lp1_land_table', 'lp1_land_flat', 'lp1_land_lifestyle', 'lp1_land_capsule'],
           'sq': ['lp1_sq_box', 'lp1_sq_pouch_box', 'lp1_sq_marble', 'lp1_sq_woman', 'lp1_sq_supple1'],
           'port': ['lp1_port_hands', 'lp1_port_supple1']}
    IM2 = {'land': ['lp2_land_man', 'lp2_land_bag', 'lp2_land_stationery', 'lp2_land_top2', 'lp2_land_tilt', 'lp2_land_pouches'],
           'sq': ['lp2_sq_man', 'lp2_sq_bag', 'lp2_sq_pouches', 'lp2_sq_stationery'],
           'port': ['lp2_port_man', 'lp2_port_bag']}
    build_pmax('P1', 'LP1', cfg['LP1_H'], cfg['PM1_L'], cfg['PM1_SHORT'], cfg['LP1_D'], IM1, VIDEOS_LP1)
    build_pmax('P2', 'LP2', cfg['LP2_H'], cfg['PM2_L'], cfg['PM2_SHORT'], cfg['LP2_D'], IM2, [])

    # ---------- オーディエンスシグナル（P-Max） ----------
    def make_custom_audience(name, members, ctype):
        for r in q(f"SELECT custom_audience.resource_name FROM custom_audience WHERE custom_audience.name = '{name}'"):
            return r.custom_audience.resource_name
        op = client.get_type("CustomAudienceOperation"); ca = op.create; ca.name = name; ca.type_ = ctype
        for kind, val in members:
            m = client.get_type("CustomAudienceMember")
            if kind == 'kw':
                m.member_type = E.CustomAudienceMemberTypeEnum.KEYWORD; m.keyword = val
            else:
                m.member_type = E.CustomAudienceMemberTypeEnum.URL; m.url = val
            ca.members.append(m)
        return client.get_service("CustomAudienceService").mutate_custom_audiences(customer_id=CID, operations=[op]).results[0].resource_name
    def signal(ag_name, aud_name, members, ctype):
        try:
            rows = q(f"SELECT asset_group.resource_name FROM asset_group WHERE asset_group.name = '{ag_name}' AND asset_group.status != 'REMOVED'")
            if not rows: print("signal: asset group not found", ag_name); return
            ag_rn = rows[0].asset_group.resource_name
            if q(f"SELECT audience.resource_name FROM audience WHERE audience.name = '{aud_name}'"): print("signal exists:", aud_name); return
            ca_rn = make_custom_audience(aud_name, members, ctype)
            aop = client.get_type("AudienceOperation"); au = aop.create; au.name = aud_name
            au.scope = E.AudienceScopeEnum.ASSET_GROUP; au.asset_group = ag_rn
            seg = client.get_type("AudienceSegment"); seg.custom_audience.custom_audience = ca_rn
            dim = client.get_type("AudienceDimension"); dim.audience_segments.segments.append(seg); au.dimensions.append(dim)
            au_rn = client.get_service("AudienceService").mutate_audiences(customer_id=CID, operations=[aop]).results[0].resource_name
            sop = client.get_type("AssetGroupSignalOperation"); sg = sop.create; sg.asset_group = ag_rn; sg.audience.audience = au_rn
            client.get_service("AssetGroupSignalService").mutate_asset_group_signals(customer_id=CID, operations=[sop])
            print("signal OK:", aud_name)
        except GoogleAdsException as ex:
            print("signal FAILED:", aud_name, [ (str(e.error_code), e.message) for e in ex.failure.errors][:3])
        except Exception as ex:
            print("signal ERROR:", aud_name, str(ex)[:300])
    AMZ = ['B0CLHXWZ9J', 'B01N0H2P1S', 'B0CXPRX8Q2', 'B000T9IM48', 'B078YNB1XG', 'B0BYJLWV6D']
    ct = E.CustomAudienceTypeEnum
    signal('P-Max_LP1_AG1', 'adsx_LP1_検索語', [('kw', k) for k in ['酪酸菌 サプリ', '短鎖脂肪酸 サプリ', '腸活 サプリ', '酪酸サプリ']], ct.SEARCH)
    signal('P-Max_LP1_AG1', 'adsx_LP1_競合URL', [('url', 'https://www.amazon.co.jp/dp/' + a) for a in AMZ], ct.INTEREST)
    signal('P-Max_LP2_AG1', 'adsx_LP2_検索語', [('kw', k) for k in ['高級 サプリ', '経営者 サプリ', 'ハイエンド サプリメント', '経営者 健康 サプリ']], ct.SEARCH)
    print("done")
