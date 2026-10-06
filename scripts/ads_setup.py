"""Google広告の新構成を「一時停止」状態で作成する。mode: inspect / validate / apply"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.ads.googleads.client import GoogleAdsClient

MODE = sys.argv[1].strip() if len(sys.argv) > 1 else 'inspect'
client = GoogleAdsClient.load_from_dict({
    "developer_token": os.environ['GOOGLE_ADS_DEVELOPER_TOKEN'],
    "client_id": os.environ['GOOGLE_ADS_CLIENT_ID'],
    "client_secret": os.environ['GOOGLE_ADS_CLIENT_SECRET'],
    "refresh_token": os.environ['GOOGLE_ADS_REFRESH_TOKEN'],
    "login_customer_id": os.environ['GOOGLE_ADS_CUSTOMER_ID'],
    "use_proto_plus": True,
})
CID = os.environ['GOOGLE_ADS_CUSTOMER_ID']
ga = client.get_service("GoogleAdsService")

def q(gaql):
    return list(ga.search(customer_id=CID, query=gaql))

if MODE == 'inspect':
    import traceback
    def section(title, fn):
        print('==', title, '==')
        try:
            fn()
        except Exception as e:
            print('ERROR:', str(e)[:600])
    def customer():
        for r in q("SELECT customer.id, customer.currency_code, customer.time_zone, customer.descriptive_name FROM customer"):
            print(r.customer.id, r.customer.currency_code, r.customer.time_zone, r.customer.descriptive_name)
    def campaigns():
        for r in q("""SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
            campaign.bidding_strategy_type, campaign.final_url_suffix, campaign.tracking_url_template,
            campaign_budget.amount_micros, campaign_budget.explicitly_shared,
            campaign.network_settings.target_search_network, campaign.network_settings.target_content_network
            FROM campaign WHERE campaign.status != 'REMOVED'"""):
            c = r.campaign
            print(c.id, c.name, c.status.name, c.advertising_channel_type.name, c.bidding_strategy_type.name,
                  'suffix=', c.final_url_suffix, 'track=', c.tracking_url_template,
                  'budget=', r.campaign_budget.amount_micros // 1_000_000, 'shared=', r.campaign_budget.explicitly_shared,
                  'net=', c.network_settings.target_search_network, c.network_settings.target_content_network)
    def convs():
        for r in q("""SELECT conversion_action.id, conversion_action.name, conversion_action.category, conversion_action.status,
            conversion_action.primary_for_goal, conversion_action.type FROM conversion_action WHERE conversion_action.status != 'REMOVED'"""):
            a = r.conversion_action
            print(a.id, a.name, a.category.name, a.status.name, 'primary=', a.primary_for_goal, a.type_.name)
    def images():
        for r in q("""SELECT asset.id, asset.name, asset.type, asset.image_asset.full_size.width_pixels,
            asset.image_asset.full_size.height_pixels, asset.image_asset.file_size FROM asset WHERE asset.type = 'IMAGE'"""):
            a = r.asset
            print(a.id, a.name, a.image_asset.full_size.width_pixels, 'x', a.image_asset.full_size.height_pixels, a.image_asset.file_size)
    def ag_assets():
        for r in q("""SELECT asset_group.id, asset_group.name, asset_group.final_urls, asset_group_asset.field_type, asset.id, asset.name, asset.type
            FROM asset_group_asset WHERE asset_group_asset.status != 'REMOVED'"""):
            if r.asset.type.name in ('IMAGE', 'MEDIA_BUNDLE', 'YOUTUBE_VIDEO'):
                print(r.asset_group.id, r.asset_group.name, r.asset_group_asset.field_type.name, r.asset.id, r.asset.name, r.asset.type.name)
    def camp_assets():
        for r in q("""SELECT campaign.name, campaign_asset.field_type, asset.id, asset.name, asset.type, asset.text_asset.text
            FROM campaign_asset WHERE campaign_asset.status != 'REMOVED'"""):
            print(r.campaign.name, r.campaign_asset.field_type.name, r.asset.id, r.asset.type.name, r.asset.text_asset.text, r.asset.name)
    def bidstr():
        for r in q("SELECT bidding_strategy.id, bidding_strategy.name, bidding_strategy.type, bidding_strategy.target_cpa.target_cpa_micros FROM bidding_strategy"):
            b = r.bidding_strategy
            print(b.id, b.name, b.type_.name, b.target_cpa.target_cpa_micros)
    def custaud():
        for r in q("SELECT custom_audience.id, custom_audience.name, custom_audience.status FROM custom_audience"):
            print(r.custom_audience.id, r.custom_audience.name, r.custom_audience.status.name)
    def adgroups():
        for r in q("SELECT ad_group.id, ad_group.name, ad_group.status, campaign.name FROM ad_group WHERE ad_group.status != 'REMOVED'"):
            print(r.campaign.name, r.ad_group.id, r.ad_group.name, r.ad_group.status.name)
    def ext_assets():
        for r in q("""SELECT asset.id, asset.type, asset.final_urls, asset.callout_asset.callout_text,
            asset.sitelink_asset.link_text, asset.sitelink_asset.description1, asset.sitelink_asset.description2,
            asset.structured_snippet_asset.header, asset.structured_snippet_asset.values,
            asset.youtube_video_asset.youtube_video_id, asset.youtube_video_asset.youtube_video_title
            FROM asset WHERE asset.type IN ('CALLOUT','SITELINK','STRUCTURED_SNIPPET','YOUTUBE_VIDEO','PRICE')"""):
            a = r.asset
            t = a.type_.name
            if t == 'CALLOUT': print(a.id, t, a.callout_asset.callout_text)
            elif t == 'SITELINK': print(a.id, t, a.sitelink_asset.link_text, '|', a.sitelink_asset.description1, '|', a.sitelink_asset.description2, '|', list(a.final_urls))
            elif t == 'STRUCTURED_SNIPPET': print(a.id, t, a.structured_snippet_asset.header, list(a.structured_snippet_asset.values))
            elif t == 'YOUTUBE_VIDEO': print(a.id, t, a.youtube_video_asset.youtube_video_id, a.youtube_video_asset.youtube_video_title)
            else: print(a.id, t)
    def existing_neg():
        for r in q("SELECT campaign.name, campaign_criterion.keyword.text FROM campaign_criterion WHERE campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'"):
            pass
        n = {}
        for r in q("SELECT campaign.name, campaign_criterion.keyword.text FROM campaign_criterion WHERE campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'"):
            n.setdefault(r.campaign.name, []).append(r.campaign_criterion.keyword.text)
        for k, v in n.items(): print(k, len(v), v[:100])
    def geo_lang():
        for r in q("SELECT campaign.name, campaign_criterion.type, campaign_criterion.location.geo_target_constant, campaign_criterion.language.language_constant, campaign_criterion.negative FROM campaign_criterion WHERE campaign_criterion.type IN ('LOCATION','LANGUAGE')"):
            print(r.campaign.name, r.campaign_criterion.type_.name, r.campaign_criterion.location.geo_target_constant, r.campaign_criterion.language.language_constant)
    for t, f in [('customer',customer),('campaigns',campaigns),('conversion actions',convs),('image assets',images),
                 ('asset group image assets',ag_assets),('campaign assets',camp_assets),('bidding strategies',bidstr),
                 ('custom audiences',custaud),('extension assets',ext_assets),('existing negatives',existing_neg),('geo/lang',geo_lang),('ad groups',adgroups)]:
        section(t, f)
    sys.exit(0)


if MODE == 'verify':
    names = ('検索_LP1', '検索_LP2_高価格・経営者', 'P-Max_LP1', 'P-Max_LP2')
    print("== campaigns ==")
    for r in q("SELECT campaign.name, campaign.status, campaign.primary_status, campaign.bidding_strategy_type, campaign.maximize_conversions.target_cpa_micros, campaign.final_url_suffix, campaign_budget.amount_micros FROM campaign WHERE campaign.status != 'REMOVED'"):
        if r.campaign.name in names or r.campaign.name.startswith(('OUCA', 'ouca')):
            c = r.campaign
            print(c.name, c.status.name, c.primary_status.name, c.bidding_strategy_type.name, 'tCPA=', c.maximize_conversions.target_cpa_micros // 1_000_000, 'budget=', r.campaign_budget.amount_micros // 1_000_000)
    print("== ad groups / keywords ==")
    for r in q("SELECT campaign.name, ad_group.name, ad_group.status FROM ad_group WHERE campaign.name IN ('検索_LP1','検索_LP2_高価格・経営者') AND ad_group.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        print(r.campaign.name, '|', r.ad_group.name, r.ad_group.status.name)
    n = {}
    for r in q("SELECT campaign.name, ad_group_criterion.keyword.text FROM ad_group_criterion WHERE campaign.name IN ('検索_LP1','検索_LP2_高価格・経営者') AND ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        n[r.campaign.name] = n.get(r.campaign.name, 0) + 1
    print("keywords:", n)
    print("== ads (policy) ==")
    for r in q("SELECT campaign.name, ad_group.name, ad_group_ad.status, ad_group_ad.policy_summary.approval_status, ad_group_ad.policy_summary.review_status, ad_group_ad.ad_strength FROM ad_group_ad WHERE campaign.name IN ('検索_LP1','検索_LP2_高価格・経営者') AND ad_group_ad.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        a = r.ad_group_ad
        print(r.campaign.name, '|', r.ad_group.name, a.status.name, a.policy_summary.approval_status.name, a.policy_summary.review_status.name, a.ad_strength.name)
    print("== asset groups ==")
    for r in q("SELECT campaign.name, asset_group.name, asset_group.status, asset_group.primary_status, asset_group.ad_strength, asset_group.final_urls FROM asset_group WHERE campaign.name IN ('P-Max_LP1','P-Max_LP2') AND campaign.status != 'REMOVED'"):
        g = r.asset_group
        print(r.campaign.name, g.name, g.status.name, g.primary_status.name, g.ad_strength.name, list(g.final_urls))
    for r in q("SELECT asset_group.name, asset_group.resource_name, campaign.name, campaign.status, asset_group_signal.resource_name, asset_group_signal.audience.audience FROM asset_group_signal"):
        print('signal', r.campaign.name, r.campaign.status.name, r.asset_group.name, r.asset_group.resource_name, r.asset_group_signal.audience.audience)
    for r in q("SELECT audience.id, audience.name, audience.status, audience.asset_group FROM audience"):
        print('audience', r.audience.id, r.audience.name, r.audience.status.name, r.audience.asset_group)
    sys.exit(0)
if MODE == 'list_neg':
    print("== campaign negatives ==")
    for r in q("SELECT campaign.name, campaign.status, campaign_criterion.keyword.text, campaign_criterion.keyword.match_type FROM campaign_criterion WHERE campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD' AND campaign.status != 'REMOVED'"):
        print('NEG|', r.campaign.name, '|', r.campaign.status.name, '|', r.campaign_criterion.keyword.text, '|', r.campaign_criterion.keyword.match_type.name)
    print("== adgroup negatives ==")
    for r in q("SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type FROM ad_group_criterion WHERE ad_group_criterion.negative = TRUE AND ad_group_criterion.type = 'KEYWORD' AND campaign.status != 'REMOVED' AND ad_group.status != 'REMOVED'"):
        print('AGNEG|', r.campaign.name, '|', r.ad_group.name, '|', r.ad_group_criterion.keyword.text, '|', r.ad_group_criterion.keyword.match_type.name)
    print("== account negatives ==")
    try:
        for r in q("SELECT customer_negative_criterion.keyword.text, customer_negative_criterion.keyword.match_type FROM customer_negative_criterion WHERE customer_negative_criterion.type = 'KEYWORD'"):
            print('ACCNEG|', r.customer_negative_criterion.keyword.text, '|', r.customer_negative_criterion.keyword.match_type.name)
    except Exception as e: print('acc err', str(e)[:200])
    print("== shared sets ==")
    try:
        for r in q("SELECT shared_set.name, shared_set.type, shared_set.status, shared_set.member_count FROM shared_set WHERE shared_set.status != 'REMOVED'"):
            print('SET|', r.shared_set.name, r.shared_set.type.name, r.shared_set.member_count)
        for r in q("SELECT campaign.name, shared_set.name FROM campaign_shared_set WHERE campaign.status != 'REMOVED' AND campaign_shared_set.status = 'ENABLED'"):
            print('CAMPSET|', r.campaign.name, '|', r.shared_set.name)
        for r in q("SELECT shared_set.name, shared_criterion.keyword.text, shared_criterion.keyword.match_type FROM shared_criterion WHERE shared_criterion.type = 'KEYWORD'"):
            print('SETKW|', r.shared_set.name, '|', r.shared_criterion.keyword.text, '|', r.shared_criterion.keyword.match_type.name)
    except Exception as e: print('set err', str(e)[:200])
    sys.exit(0)
if MODE == 'add_themes':
    from google.ads.googleads.errors import GoogleAdsException
    old = {}
    for r in q("SELECT asset_group.id, asset_group.name, campaign.name, campaign.status, asset_group_signal.search_theme.text FROM asset_group_signal WHERE asset_group_signal.search_theme.text != ''"):
        old.setdefault((r.campaign.name, r.asset_group.name, r.asset_group.id), []).append(r.asset_group_signal.search_theme.text)
    for k, v in old.items(): print('THEMES|', k, '|', v)
    src = [t for k, v in old.items() if k[2] == 6746797318 for t in v]
    print('source themes:', src)
    for r in q("SELECT asset_group.resource_name, asset_group.name, campaign.name FROM asset_group WHERE campaign.name IN ('P-Max_LP1','P-Max_LP2') AND campaign.status != 'REMOVED' AND asset_group.status != 'REMOVED'"):
        have = {t.lower() for k, v in old.items() if k[1] == r.asset_group.name and k[0] == r.campaign.name for t in v}
        ops = []
        for t in src:
            if t.lower() in have: continue
            op = client.get_type("AssetGroupSignalOperation"); sg = op.create
            sg.asset_group = r.asset_group.resource_name; sg.search_theme.text = t; ops.append(op)
        print(r.campaign.name, r.asset_group.name, 'to add:', len(ops))
        if ops:
            try:
                res = client.get_service("AssetGroupSignalService").mutate_asset_group_signals(customer_id=CID, operations=ops)
                print('  OK', len(res.results))
            except GoogleAdsException as ex:
                for e in ex.failure.errors[:5]: print('  FAILED -', e.message)
    sys.exit(0)
if MODE == 'rebuild_search':
    import ads_build
    ads_build.run(client, CID, 'cleanup_search')
    ads_build.run(client, CID, 'apply')
elif MODE == 'rebuild':
    import ads_build
    ads_build.run(client, CID, 'cleanup')
    ads_build.run(client, CID, 'apply')
elif MODE in ('apply', 'cleanup', 'add_kw'):
    import ads_build
    ads_build.run(client, CID, MODE)
else:
    print("unknown mode", MODE)
