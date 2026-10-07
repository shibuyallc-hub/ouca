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
if MODE == 'age_report':
    print("== age_range_view (2026-09-01..2026-10-06) ==")
    for r in q("SELECT campaign.name, ad_group_criterion.age_range.type, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM age_range_view WHERE segments.date BETWEEN '2026-09-01' AND '2026-10-06'"):
        m = r.metrics
        print('AGE|', r.campaign.name, '|', r.ad_group_criterion.age_range.type_.name, '|', m.impressions, '|', m.clicks, '|', round(m.cost_micros/1e6), '|', m.conversions)
    print("== gender ==")
    for r in q("SELECT campaign.name, ad_group_criterion.gender.type, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM gender_view WHERE segments.date BETWEEN '2026-09-01' AND '2026-10-06'"):
        m = r.metrics
        print('GEN|', r.campaign.name, '|', r.ad_group_criterion.gender.type_.name, '|', m.impressions, '|', m.clicks, '|', round(m.cost_micros/1e6), '|', m.conversions)
    sys.exit(0)
if MODE == 'age_excl':
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    cid = {r.campaign.name: r.campaign.id for r in q("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED'")}
    for cname in ('検索_LP2_高価格・経営者', 'P-Max_LP2'):
        if cname not in cid: print('SKIP no campaign', cname); continue
        have = {r.campaign_criterion.age_range.type_.name: r.campaign_criterion.negative for r in q(f"SELECT campaign_criterion.age_range.type, campaign_criterion.negative FROM campaign_criterion WHERE campaign.id = {cid[cname]} AND campaign_criterion.type = 'AGE_RANGE'")}
        print(cname, 'existing age criteria:', have)
        for t in ('AGE_RANGE_18_24', 'AGE_RANGE_65_UP'):
            if have.get(t) is True: print('  already excluded', t); continue
            op = client.get_type("CampaignCriterionOperation")
            c = op.create; c.campaign = f"customers/{CID}/campaigns/{cid[cname]}"; c.negative = True
            c.age_range.type_ = getattr(E.AgeRangeTypeEnum, t)
            try:
                client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=CID, operations=[op])
                print('  OK excluded', t)
            except GoogleAdsException as ex:
                for e in ex.failure.errors[:3]: print('  FAILED', t, '-', e.message)
        print(cname, 'after:', {r.campaign_criterion.age_range.type_.name: r.campaign_criterion.negative for r in q(f"SELECT campaign_criterion.age_range.type, campaign_criterion.negative FROM campaign_criterion WHERE campaign.id = {cid[cname]} AND campaign_criterion.type = 'AGE_RANGE'")})
    sys.exit(0)
if MODE == 'aud_detail':
    print("== asset group signals (audience) ==")
    sig = []
    for r in q("SELECT asset_group_signal.resource_name, campaign.name, campaign.status, asset_group.name, asset_group.id, asset_group_signal.audience.audience FROM asset_group_signal"):
        sig.append((r.campaign.name, r.campaign.status.name, r.asset_group.name, r.asset_group.id, r.asset_group_signal.audience.audience))
    for x in sig:
        if x[4]: print('SIG|', x)
    for r in q("SELECT audience.resource_name, audience.name, audience.status, audience.dimensions, audience.asset_group FROM audience"):
        a = r.audience
        mem = []
        for d in a.dimensions:
            for sgm in d.audience_segments.segments:
                if sgm.custom_audience.custom_audience: mem.append('custom:' + sgm.custom_audience.custom_audience)
                if sgm.user_list.user_list: mem.append('userlist:' + sgm.user_list.user_list)
                if sgm.user_interest.user_interest_category: mem.append('interest:' + sgm.user_interest.user_interest_category)
            if d.age or d.gender: mem.append('demo')
        print('AUD|', a.resource_name, '|', a.name, '|', a.status.name, '|', a.asset_group, '|', mem)
    for r in q("SELECT custom_audience.resource_name, custom_audience.name, custom_audience.status, custom_audience.members FROM custom_audience WHERE custom_audience.status != 'REMOVED'"):
        c = r.custom_audience
        print('CUST|', c.resource_name, '|', c.name, '|', c.status.name, '|', [(m.member_type.name, m.keyword or m.url) for m in c.members])
    sys.exit(0)
if MODE == 'lp2_age_signal':
    from google.ads.googleads.errors import GoogleAdsException
    from google.api_core import protobuf_helpers
    rows = list(q("SELECT asset_group_signal.audience.audience FROM asset_group_signal WHERE asset_group.id = 6755938081"))
    aud_rns = [r.asset_group_signal.audience.audience for r in rows if r.asset_group_signal.audience.audience]
    print('LP2 audiences:', aud_rns)
    for rn in aud_rns:
        a = list(q(f"SELECT audience.resource_name, audience.dimensions FROM audience WHERE audience.resource_name = '{rn}'"))[0].audience
        for i, d in enumerate(a.dimensions):
            if d.age.age_ranges or d.age.include_undetermined:
                print('before age dim:', [(x.min_age, x.max_age) for x in d.age.age_ranges], 'unknown', d.age.include_undetermined)
        op = client.get_type("AudienceOperation"); au = op.update; au.resource_name = rn
        for d in a.dimensions:
            nd = client.get_type("AudienceDimension")
            client.copy_from(nd, d)
            if d.age.age_ranges or d.age.include_undetermined:
                del nd.age.age_ranges[:]
                for lo, hi in ((35, 44), (45, 54), (55, 64)):
                    seg = client.get_type("AgeSegment"); seg.min_age = lo; seg.max_age = hi; nd.age.age_ranges.append(seg)
            au.dimensions.append(nd)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, au._pb))
        try:
            client.get_service("AudienceService").mutate_audiences(customer_id=CID, operations=[op]); print('OK updated', rn)
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:4]: print('FAILED', e.message)
        b = list(q(f"SELECT audience.dimensions FROM audience WHERE audience.resource_name = '{rn}'"))[0].audience
        for d in b.dimensions:
            if d.age.age_ranges or d.age.include_undetermined:
                print('after age dim:', [(x.min_age, x.max_age) for x in d.age.age_ranges], 'unknown', d.age.include_undetermined)
    sys.exit(0)
if MODE == 'headline_fix':
    from google.ads.googleads.errors import GoogleAdsException
    from google.api_core import protobuf_helpers
    OLD, NEW = 'OUCA supplement 公式', 'OUCA supplement'
    E = client.enums
    # --- 検索広告（レスポンシブ検索広告）---
    for r in q("SELECT campaign.name, ad_group.name, ad_group_ad.ad.resource_name, ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.status FROM ad_group_ad WHERE campaign.name IN ('検索_LP1','検索_LP2_高価格・経営者') AND ad_group_ad.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        ad = r.ad_group_ad.ad; heads = list(ad.responsive_search_ad.headlines)
        texts = [h.text for h in heads]
        print('RSA|', r.campaign.name, '|', r.ad_group.name, '|', texts.count(OLD), 'old;', 'has NEW:', NEW in texts)
        if OLD not in texts: continue
        op = client.get_type("AdOperation"); u = op.update; u.resource_name = ad.resource_name
        seen = set()
        for h in heads:
            t = NEW if h.text == OLD else h.text
            if t in seen: print('  duplicate skipped:', t); continue
            seen.add(t)
            nh = client.get_type("AdTextAsset"); nh.text = t
            if h.pinned_field: nh.pinned_field = h.pinned_field
            u.responsive_search_ad.headlines.append(nh)
        for dd in ad.responsive_search_ad.descriptions:
            nd = client.get_type("AdTextAsset"); nd.text = dd.text
            if dd.pinned_field: nd.pinned_field = dd.pinned_field
            u.responsive_search_ad.descriptions.append(nd)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
        try:
            client.get_service("AdService").mutate_ads(customer_id=CID, operations=[op]); print('  OK updated RSA')
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:4]: print('  FAILED', e.message)
    # --- P-Max ---
    for r in q("SELECT campaign.name, asset_group.name, asset_group.resource_name, asset_group_asset.resource_name, asset_group_asset.field_type, asset.text_asset.text FROM asset_group_asset WHERE campaign.name IN ('P-Max_LP1','P-Max_LP2') AND asset_group_asset.field_type IN ('HEADLINE','LONG_HEADLINE','DESCRIPTION') AND asset_group_asset.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        t = r.asset.text_asset.text
        if OLD in t:
            print('PMAX|', r.campaign.name, r.asset_group_asset.field_type.name, t)
            if r.asset_group_asset.field_type.name != 'HEADLINE' or t != OLD: print('  (not an exact headline match; skipped)'); continue
            ga_ = client.get_service("GoogleAdsService")
            ops = []
            m = client.get_type("MutateOperation"); m.asset_group_asset_operation.remove = r.asset_group_asset.resource_name; ops.append(m)
            tmp = -1
            m2 = client.get_type("MutateOperation"); a = m2.asset_operation.create; a.resource_name = client.get_service("AssetService").asset_path(CID, tmp); a.text_asset.text = NEW; ops.append(m2)
            m3 = client.get_type("MutateOperation"); c = m3.asset_group_asset_operation.create; c.asset_group = r.asset_group.resource_name; c.asset = a.resource_name; c.field_type = E.AssetFieldTypeEnum.HEADLINE; ops.append(m3)
            try:
                ga_.mutate(customer_id=CID, mutate_operations=ops); print('  OK replaced P-Max headline')
            except GoogleAdsException as ex:
                for e in ex.failure.errors[:4]: print('  FAILED', e.message)
    print('done')
    sys.exit(0)
if MODE == 'report_data':
    print("== google daily ==")
    for r in q("SELECT segments.date, campaign.name, campaign.advertising_channel_type, metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions, metrics.all_conversions FROM campaign WHERE segments.date BETWEEN '2026-09-01' AND '2026-10-07' AND metrics.impressions > 0"):
        m = r.metrics
        print('GD|', r.segments.date, '|', r.campaign.name, '|', r.campaign.advertising_channel_type.name, '|', round(m.cost_micros/1e6), '|', m.impressions, '|', m.clicks, '|', round(m.conversions, 2), '|', round(m.all_conversions, 2))
    sys.exit(0)
if MODE == 'old_kw_report':
    print("== old search ad groups/keywords ==")
    for r in q("SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, ad_group_criterion.status FROM ad_group_criterion WHERE campaign.name = 'OUCA_supplement_search' AND ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED' AND ad_group.status != 'REMOVED'"):
        print('OK|', r.campaign.status.name, '|', r.ad_group.name, '|', r.ad_group.status.name, '|', r.ad_group_criterion.keyword.text, '|', r.ad_group_criterion.keyword.match_type.name, '|', r.ad_group_criterion.status.name)
    for r in q("SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, ad_group.resource_name FROM ad_group WHERE campaign.name = 'OUCA_supplement_search' AND ad_group.status != 'REMOVED'"):
        print('AG|', r.ad_group.name, r.ad_group.status.name, r.ad_group.resource_name)
    sys.exit(0)
if MODE == 'old_add':
    import json as _j
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    cfg = _j.load(open('ads_setup/config.json', encoding='utf-8'))
    lp1 = [k for g in cfg['KW'] if g['url'] == cfg['LP1'] for k in g['kws']]
    cid = {r.campaign.name: r.campaign.id for r in q("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED'")}
    agr = list(q(f"SELECT ad_group.resource_name FROM ad_group WHERE campaign.id = {cid['OUCA_supplement_search']} AND ad_group.status != 'REMOVED'"))[0].ad_group.resource_name
    have = {r.ad_group_criterion.keyword.text.lower() for r in q(f"SELECT ad_group_criterion.keyword.text FROM ad_group_criterion WHERE ad_group.resource_name = '{agr}' AND ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED'")}
    missing = [k for k in dict.fromkeys(lp1) if k.lower() not in have]
    print('LP1 keywords:', len(set(lp1)), 'already in old:', len(set(lp1)) - len(missing), 'to add:', len(missing))
    print('ADD|', missing)
    ops = []
    for k in missing:
        op = client.get_type("AdGroupCriterionOperation"); c = op.create; c.ad_group = agr
        c.status = E.AdGroupCriterionStatusEnum.ENABLED; c.keyword.text = k; c.keyword.match_type = E.KeywordMatchTypeEnum.PHRASE; ops.append(op)
    if ops:
        try:
            client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(customer_id=CID, operations=ops); print('OK keywords added (phrase only):', len(ops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED kw -', e.message)
    for cname in ('OUCA_supplement_search', 'ouca_supplement_pmax'):
        hv = {r.campaign_criterion.keyword.text.lower() for r in q(f"SELECT campaign_criterion.keyword.text FROM campaign_criterion WHERE campaign.id = {cid[cname]} AND campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'")}
        nops = []
        for t in cfg['NEG']:
            if t.lower() in hv: continue
            op = client.get_type("CampaignCriterionOperation"); n = op.create; n.campaign = f"customers/{CID}/campaigns/{cid[cname]}"
            n.negative = True; n.keyword.text = t; n.keyword.match_type = E.KeywordMatchTypeEnum.PHRASE; nops.append(op)
        print(cname, 'existing negatives:', len(hv), 'to add:', len(nops), [o.create.keyword.text for o in nops])
        if nops:
            try:
                client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=CID, operations=nops); print('  OK negatives added', len(nops))
            except GoogleAdsException as ex:
                for e in ex.failure.errors[:5]: print('  FAILED neg -', e.message)
    sys.exit(0)
if MODE == 'old_lp1_switch':
    import json as _j
    from google.ads.googleads.errors import GoogleAdsException
    from google.api_core import protobuf_helpers
    E = client.enums
    cfg = _j.load(open('ads_setup/config.json', encoding='utf-8'))
    URL = cfg['LP1']
    SUF = 'utm_source=google&utm_medium=cpc&utm_campaign={campaignid}&utm_content={adgroupid}'
    cs = {r.campaign.name: (r.campaign.id, r.campaign.resource_name, r.campaign.final_url_suffix, r.campaign.tracking_url_template) for r in q("SELECT campaign.id, campaign.name, campaign.final_url_suffix, campaign.tracking_url_template FROM campaign WHERE campaign.status != 'REMOVED'")}
    OLD, NEW = 'OUCA_supplement_search', '検索_LP1'
    print('old suffix/track:', cs[OLD][2], '|', cs[OLD][3])
    # 1) 広告の遷移先
    for r in q(f"SELECT ad_group_ad.ad.resource_name, ad_group_ad.ad.final_urls, ad_group_ad.ad.final_mobile_urls, ad_group_ad.ad.type, ad_group_ad.status FROM ad_group_ad WHERE campaign.id = {cs[OLD][0]} AND ad_group_ad.status != 'REMOVED'"):
        ad = r.ad_group_ad.ad
        print('AD|', ad.resource_name, ad.type_.name, r.ad_group_ad.status.name, list(ad.final_urls), list(ad.final_mobile_urls))
        op = client.get_type("AdOperation"); u = op.update; u.resource_name = ad.resource_name; u.final_urls.append(URL)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
        try:
            client.get_service("AdService").mutate_ads(customer_id=CID, operations=[op]); print('  OK final url ->', URL)
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:3]: print('  FAILED ad -', e.message)
    # 2) キャンペーンのURLサフィックス
    op = client.get_type("CampaignOperation"); u = op.update; u.resource_name = cs[OLD][1]; u.final_url_suffix = SUF
    client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
    try:
        client.get_service("CampaignService").mutate_campaigns(customer_id=CID, operations=[op]); print('OK campaign suffix set')
    except GoogleAdsException as ex:
        for e in ex.failure.errors[:3]: print('FAILED suffix -', e.message)
    # 3) アセット
    def camp_assets(cid):
        d = {}
        for r in q(f"SELECT campaign.id, campaign_asset.resource_name, campaign_asset.asset, campaign_asset.field_type, campaign_asset.status FROM campaign_asset WHERE campaign.id = {cid} AND campaign_asset.status != 'REMOVED'"):
            d.setdefault(r.campaign_asset.field_type.name, []).append((r.campaign_asset.resource_name, r.campaign_asset.asset))
        return d
    newa, olda = camp_assets(cs[NEW][0]), camp_assets(cs[OLD][0])
    print('NEW assets:', {k: len(v) for k, v in newa.items()})
    print('OLD assets:', {k: len(v) for k, v in olda.items()})
    ops = []
    for ft, items in newa.items():
        if ft in ('HEADLINE', 'DESCRIPTION'): continue
        new_assets = {a for rn, a in items}; old_assets = {a for rn, a in olda.get(ft, [])}
        for rn, a in olda.get(ft, []):
            if a not in new_assets:
                m = client.get_type("MutateOperation"); m.campaign_asset_operation.remove = rn; ops.append(m)
        for rn, a in items:
            if a not in old_assets:
                m = client.get_type("MutateOperation"); c = m.campaign_asset_operation.create
                c.campaign = cs[OLD][1]; c.asset = a; c.field_type = getattr(E.AssetFieldTypeEnum, ft); ops.append(m)
    # 新側にない種類（旧のURLを指すもの）は外す
    for ft, items in olda.items():
        if ft not in newa:
            print('OLD-only type removed:', ft, len(items))
            for rn, a in items:
                m = client.get_type("MutateOperation"); m.campaign_asset_operation.remove = rn; ops.append(m)
    if ops:
        try:
            client.get_service("GoogleAdsService").mutate(customer_id=CID, mutate_operations=ops); print('OK assets replaced, ops:', len(ops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED assets -', e.message)
    print('OLD assets after:', {k: len(v) for k, v in camp_assets(cs[OLD][0]).items()})
    # 4) 広告グループ単位のアセット（残っていれば表示）
    for r in q(f"SELECT campaign.id, ad_group.name, ad_group_asset.field_type, ad_group_asset.status FROM ad_group_asset WHERE campaign.id = {cs[OLD][0]} AND ad_group_asset.status != 'REMOVED'"):
        print('AGASSET|', r.ad_group.name, r.ad_group_asset.field_type.name)
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
