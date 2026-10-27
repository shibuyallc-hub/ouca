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
if MODE == 'old_lp2_ad':
    import json as _j, unicodedata
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    cfg = _j.load(open('ads_setup/config.json', encoding='utf-8'))
    wd = lambda t: sum(2 if unicodedata.east_asian_width(c) in 'WFA' else 1 for c in t)
    cid = {r.campaign.name: r.campaign.id for r in q("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED'")}['OUCA_supplement_search']
    ag = list(q(f"SELECT ad_group.resource_name, ad_group.ad_rotation_mode FROM ad_group WHERE campaign.id = {cid} AND ad_group.status != 'REMOVED'"))[0].ad_group
    print('ad group:', ag.resource_name, 'rotation:', ag.ad_rotation_mode.name)
    urls = [list(r.ad_group_ad.ad.final_urls) for r in q(f"SELECT ad_group_ad.ad.final_urls FROM ad_group_ad WHERE campaign.id = {cid} AND ad_group_ad.status != 'REMOVED'")]
    print('existing ad urls:', urls)
    if not any(cfg['LP2'] in u for u in urls):
        op = client.get_type("AdGroupAdOperation"); a = op.create; a.ad_group = ag.resource_name; a.status = E.AdGroupAdStatusEnum.ENABLED
        a.ad.final_urls.append(cfg['LP2']); r = a.ad.responsive_search_ad
        for i, h in enumerate(cfg['LP2_H']):
            assert wd(h) <= 30, h
            t = client.get_type("AdTextAsset"); t.text = h
            if i == 0: t.pinned_field = E.ServedAssetFieldTypeEnum.HEADLINE_1
            r.headlines.append(t)
        for d in cfg['LP2_D']:
            assert wd(d) <= 90, d
            t = client.get_type("AdTextAsset"); t.text = d; r.descriptions.append(t)
        r.path1 = 'OUCA'; r.path2 = 'supplement'
        try:
            res = client.get_service("AdGroupAdService").mutate_ad_group_ads(customer_id=CID, operations=[op]); print('OK LP2 ad created:', res.results[0].resource_name)
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED ad -', e.message)
    else:
        print('LP2 ad already exists')
    # ローテーション：均等寄り
    try:
        from google.api_core import protobuf_helpers
        op = client.get_type("AdGroupOperation"); u = op.update; u.resource_name = ag.resource_name; u.ad_rotation_mode = E.AdGroupAdRotationModeEnum.ROTATE_FOREVER
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
        client.get_service("AdGroupService").mutate_ad_groups(customer_id=CID, operations=[op]); print('OK ad rotation -> ROTATE_FOREVER')
    except GoogleAdsException as ex:
        for e in ex.failure.errors[:3]: print('FAILED rotation -', e.message)
    # LP2用キーワード（フレーズ一致のみ）
    lp2 = [k for g in cfg['KW'] if g['url'] == cfg['LP2'] for k in g['kws']]
    have = {r.ad_group_criterion.keyword.text.lower() for r in q(f"SELECT ad_group_criterion.keyword.text FROM ad_group_criterion WHERE ad_group.resource_name = '{ag.resource_name}' AND ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED'")}
    missing = [k for k in dict.fromkeys(lp2) if k.lower() not in have]
    print('LP2 keywords:', len(set(lp2)), 'to add:', len(missing))
    ops = []
    for k in missing:
        op = client.get_type("AdGroupCriterionOperation"); c = op.create; c.ad_group = ag.resource_name
        c.status = E.AdGroupCriterionStatusEnum.ENABLED; c.keyword.text = k; c.keyword.match_type = E.KeywordMatchTypeEnum.PHRASE; ops.append(op)
    if ops:
        try:
            for i in range(0, len(ops), 400): client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(customer_id=CID, operations=ops[i:i+400])
            print('OK LP2 keywords added (phrase only):', len(ops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED kw -', e.message)
    n = list(q(f"SELECT campaign.id, ad_group_criterion.keyword.text FROM ad_group_criterion WHERE campaign.id = {cid} AND ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED'"))
    print('keywords in old ad group now:', len(n))
    for r in q(f"SELECT campaign.id, ad_group_ad.ad.final_urls, ad_group_ad.status, ad_group_ad.policy_summary.approval_status, ad_group_ad.policy_summary.review_status FROM ad_group_ad WHERE campaign.id = {cid} AND ad_group_ad.status != 'REMOVED'"):
        print('ADNOW|', list(r.ad_group_ad.ad.final_urls), r.ad_group_ad.status.name, r.ad_group_ad.policy_summary.approval_status.name, r.ad_group_ad.policy_summary.review_status.name)
    sys.exit(0)
if MODE == 'old_split':
    import json as _j, unicodedata
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    cfg = _j.load(open('ads_setup/config.json', encoding='utf-8'))
    wd = lambda t: sum(2 if unicodedata.east_asian_width(c) in 'WFA' else 1 for c in t)
    camps = {r.campaign.name: (r.campaign.id, r.campaign.resource_name) for r in q("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED'")}
    OLDC = camps['OUCA_supplement_search']; NEW2 = camps['検索_LP2_高価格・経営者']
    ag1 = list(q(f"SELECT campaign.id, ad_group.resource_name, ad_group.name FROM ad_group WHERE campaign.id = {OLDC[0]} AND ad_group.name = 'OUCA_supplement_ag' AND ad_group.status != 'REMOVED'"))[0].ad_group.resource_name
    # --- 広告グループLP2（同じキャンペーン内）---
    NAME2 = 'OUCA_supplement_ag_LP2'
    rows = list(q(f"SELECT campaign.id, ad_group.resource_name FROM ad_group WHERE campaign.id = {OLDC[0]} AND ad_group.name = '{NAME2}' AND ad_group.status != 'REMOVED'"))
    if rows: ag2 = rows[0].ad_group.resource_name; print('ad group LP2 exists')
    else:
        op = client.get_type("AdGroupOperation"); g = op.create; g.name = NAME2; g.campaign = OLDC[1]
        g.status = E.AdGroupStatusEnum.ENABLED; g.type_ = E.AdGroupTypeEnum.SEARCH_STANDARD
        ag2 = client.get_service("AdGroupService").mutate_ad_groups(customer_id=CID, operations=[op]).results[0].resource_name; print('OK ad group created', ag2)
    # --- キーワード割り振り ---
    lp1 = [k for g in cfg['KW'] if g['url'] == cfg['LP1'] for k in g['kws']]
    lp2 = [k for g in cfg['KW'] if g['url'] == cfg['LP2'] for k in g['kws']]
    old_lp1_only = ['集中力 サプリ', '巡り サプリ', '酪酸菌サプリ 口コミ', '腸活サプリ 人気', '便秘 サプリ 女性', 'サプリ 通販 口コミ', '丁寧な暮らし サプリ', 'インスタ映え サプリ', '贈り物 サプリ', 'カプセル サプリ 腸活']
    old_common = ['OUCA supplement 口コミ', 'OUCA 評判', 'オウカ 酪酸']
    old_lp2_only = ['接待 胃腸 対策', 'パフォーマンス サプリ 男性', '睡眠不足 サプリ 男性', 'プレミアムサプリ 腸活', 'サプリ 通販 高級', '忙しい人 サプリ']
    drop = ['OUCA 解約', 'サプリ 定期便', '健康 ギフト']
    KW1 = list(dict.fromkeys(lp1 + old_lp1_only + old_common))
    KW2 = list(dict.fromkeys(lp1 + old_lp1_only + old_common + lp2 + old_lp2_only))
    REMOVE1 = {k.lower() for k in lp2 + old_lp2_only + drop} - {k.lower() for k in KW1}
    print('KW1:', len(KW1), 'KW2:', len(KW2), 'remove from AG1:', len(REMOVE1))
    def crit(agrn):
        return list(q(f"SELECT ad_group_criterion.resource_name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type FROM ad_group_criterion WHERE ad_group.resource_name = '{agrn}' AND ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED'"))
    def add_kw(agrn, kws):
        have = {r.ad_group_criterion.keyword.text.lower() for r in crit(agrn)}
        ops = []
        for k in kws:
            if k.lower() in have: continue
            op = client.get_type("AdGroupCriterionOperation"); c = op.create; c.ad_group = agrn
            c.status = E.AdGroupCriterionStatusEnum.ENABLED; c.keyword.text = k; c.keyword.match_type = E.KeywordMatchTypeEnum.PHRASE; ops.append(op)
        for i in range(0, len(ops), 400): client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(customer_id=CID, operations=ops[i:i+400])
        return len(ops)
    try:
        print('AG2 keywords added:', add_kw(ag2, KW2)); print('AG1 keywords added:', add_kw(ag1, KW1))
        rem = [r.ad_group_criterion.resource_name for r in crit(ag1) if r.ad_group_criterion.keyword.text.lower() in REMOVE1]
        ops = []
        for rn in rem:
            op = client.get_type("AdGroupCriterionOperation"); op.remove = rn; ops.append(op)
        for i in range(0, len(ops), 400): client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(customer_id=CID, operations=ops[i:i+400])
        print('AG1 keywords removed:', len(ops))
    except GoogleAdsException as ex:
        for e in ex.failure.errors[:5]: print('FAILED kw -', e.message)
    # --- LP2広告（AG2）---
    has = list(q(f"SELECT ad_group_ad.ad.final_urls FROM ad_group_ad WHERE ad_group.resource_name = '{ag2}' AND ad_group_ad.status != 'REMOVED'"))
    if not has:
        op = client.get_type("AdGroupAdOperation"); a = op.create; a.ad_group = ag2; a.status = E.AdGroupAdStatusEnum.ENABLED
        a.ad.final_urls.append(cfg['LP2']); r_ = a.ad.responsive_search_ad
        for i, h in enumerate(cfg['LP2_H']):
            assert wd(h) <= 30, h
            t = client.get_type("AdTextAsset"); t.text = h
            if i == 0: t.pinned_field = E.ServedAssetFieldTypeEnum.HEADLINE_1
            r_.headlines.append(t)
        for d in cfg['LP2_D']:
            assert wd(d) <= 90, d
            t = client.get_type("AdTextAsset"); t.text = d; r_.descriptions.append(t)
        r_.path1 = 'OUCA'; r_.path2 = 'supplement'
        try:
            print('OK LP2 ad in AG2:', client.get_service("AdGroupAdService").mutate_ad_group_ads(customer_id=CID, operations=[op]).results[0].resource_name)
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED ad -', e.message)
    else: print('AG2 already has ad')
    # --- サイトリンク：広告グループ単位へ ---
    def sitelinks(cid):
        return [(r.campaign_asset.resource_name, r.campaign_asset.asset) for r in q(f"SELECT campaign.id, campaign_asset.resource_name, campaign_asset.asset FROM campaign_asset WHERE campaign.id = {cid} AND campaign_asset.field_type = 'SITELINK' AND campaign_asset.status != 'REMOVED'")]
    sl1 = sitelinks(OLDC[0]); sl2 = sitelinks(NEW2[0])
    print('sitelinks: old campaign', len(sl1), 'LP2 campaign', len(sl2))
    ops = []
    for agrn, items in ((ag1, sl1), (ag2, sl2)):
        have = {r.ad_group_asset.asset for r in q(f"SELECT ad_group.resource_name, ad_group_asset.asset FROM ad_group_asset WHERE ad_group.resource_name = '{agrn}' AND ad_group_asset.field_type = 'SITELINK' AND ad_group_asset.status != 'REMOVED'")}
        for rn, asset in items:
            if asset in have: continue
            m = client.get_type("MutateOperation"); c = m.ad_group_asset_operation.create; c.ad_group = agrn; c.asset = asset; c.field_type = E.AssetFieldTypeEnum.SITELINK; ops.append(m)
    for rn, asset in sl1:
        m = client.get_type("MutateOperation"); m.campaign_asset_operation.remove = rn; ops.append(m)
    if ops:
        try:
            client.get_service("GoogleAdsService").mutate(customer_id=CID, mutate_operations=ops); print('OK sitelinks moved to ad group level, ops:', len(ops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED sitelinks -', e.message)
    # --- 結果 ---
    for nm, agrn in (('AG1', ag1), ('AG2', ag2)):
        print('RESULT|', nm, 'keywords', len(crit(agrn)))
        for r in q(f"SELECT ad_group_ad.ad.final_urls, ad_group_ad.policy_summary.approval_status, ad_group_ad.policy_summary.review_status FROM ad_group_ad WHERE ad_group.resource_name = '{agrn}' AND ad_group_ad.status != 'REMOVED'"):
            print('RESULT|', nm, 'ad', list(r.ad_group_ad.ad.final_urls), r.ad_group_ad.policy_summary.approval_status.name, r.ad_group_ad.policy_summary.review_status.name)
        print('RESULT|', nm, 'sitelinks', len(list(q(f"SELECT ad_group.resource_name, ad_group_asset.asset FROM ad_group_asset WHERE ad_group.resource_name = '{agrn}' AND ad_group_asset.field_type = 'SITELINK' AND ad_group_asset.status != 'REMOVED'"))))
    sys.exit(0)
if MODE == 'sl_check':
    for r in q("SELECT ad_group.name, campaign.name, ad_group_asset.field_type, ad_group_asset.status, ad_group_asset.primary_status, ad_group_asset.primary_status_reasons, asset.sitelink_asset.link_text, asset.final_urls FROM ad_group_asset WHERE campaign.name = 'OUCA_supplement_search' AND ad_group_asset.field_type = 'SITELINK'"):
        a = r.ad_group_asset
        print('SL|', r.ad_group.name, '|', a.status.name, '|', a.primary_status.name, '|', [x.name for x in a.primary_status_reasons], '|', r.asset.sitelink_asset.link_text, '|', list(r.asset.final_urls))
    for r in q("SELECT campaign.name, campaign_asset.field_type, campaign_asset.status, asset.sitelink_asset.link_text FROM campaign_asset WHERE campaign.name = 'OUCA_supplement_search' AND campaign_asset.field_type = 'SITELINK'"):
        print('CSL|', r.campaign_asset.status.name, r.asset.sitelink_asset.link_text)
    sys.exit(0)
if MODE == 'old_pmax':
    import json as _j
    from google.ads.googleads.errors import GoogleAdsException
    from google.api_core import protobuf_helpers
    E = client.enums
    cfg = _j.load(open('ads_setup/config.json', encoding='utf-8'))
    SUF_P = 'utm_source=google&utm_medium=cpc&utm_campaign={campaignid}'
    camps = {r.campaign.name: (r.campaign.id, r.campaign.resource_name, False, r.campaign.final_url_suffix) for r in q("SELECT campaign.id, campaign.name, campaign.final_url_suffix FROM campaign WHERE campaign.status != 'REMOVED'")}
    OLDC = camps['ouca_supplement_pmax']; P1 = camps['P-Max_LP1']; P2 = camps['P-Max_LP2']
    print('url_expansion_opt_out old/P1/P2:', OLDC[2], P1[2], P2[2], '| old suffix:', OLDC[3])
    ag1 = list(q(f"SELECT campaign.id, asset_group.resource_name, asset_group.name, asset_group.final_urls, asset_group.path1, asset_group.path2 FROM asset_group WHERE campaign.id = {OLDC[0]} AND asset_group.status != 'REMOVED'"))
    for r in ag1: print('OLD AG:', r.asset_group.name, r.asset_group.resource_name, list(r.asset_group.final_urls), r.asset_group.path1, r.asset_group.path2)
    AG1 = ag1[0].asset_group.resource_name
    src = list(q(f"SELECT campaign.id, asset_group.resource_name, asset_group.final_urls, asset_group.path1, asset_group.path2 FROM asset_group WHERE campaign.id = {P2[0]} AND asset_group.status != 'REMOVED'"))[0].asset_group
    # 1) 既存アセットグループの遷移先 -> LP1、サフィックス
    op = client.get_type("AssetGroupOperation"); u = op.update; u.resource_name = AG1; del u.final_urls[:]; u.final_urls.append(cfg['LP1'])
    client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
    try:
        client.get_service("AssetGroupService").mutate_asset_groups(customer_id=CID, operations=[op]); print('OK old AG final url -> LP1')
    except GoogleAdsException as ex:
        for e in ex.failure.errors[:3]: print('FAILED AG1 url -', e.message)
    op = client.get_type("CampaignOperation"); u = op.update; u.resource_name = OLDC[1]; u.final_url_suffix = SUF_P
    client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
    try:
        client.get_service("CampaignService").mutate_campaigns(customer_id=CID, operations=[op]); print('OK campaign suffix')
    except GoogleAdsException as ex:
        for e in ex.failure.errors[:3]: print('FAILED suffix -', e.message)
    # 2) LP2アセットグループを新規作成（P-Max_LP2のアセットを共有）
    NAME2 = 'OUCA_supplement_pmax_LP2'
    ex2 = list(q(f"SELECT campaign.id, asset_group.resource_name FROM asset_group WHERE campaign.id = {OLDC[0]} AND asset_group.name = '{NAME2}' AND asset_group.status != 'REMOVED'"))
    if ex2: AG2 = ex2[0].asset_group.resource_name; print('AG2 exists', AG2)
    else:
        items = [(r.asset_group_asset.asset, r.asset_group_asset.field_type.name) for r in q(f"SELECT campaign.id, asset_group_asset.asset, asset_group_asset.field_type FROM asset_group_asset WHERE asset_group.resource_name = '{src.resource_name}' AND asset_group_asset.status != 'REMOVED'")]
        print('source assets:', len(items))
        ops = []
        m = client.get_type("MutateOperation"); g = m.asset_group_operation.create
        g.resource_name = client.get_service("AssetGroupService").asset_group_path(CID, -1); g.name = NAME2; g.campaign = OLDC[1]
        g.status = E.AssetGroupStatusEnum.ENABLED; g.final_urls.append(cfg['LP2']); g.path1 = src.path1 or 'OUCA'; g.path2 = src.path2 or 'supplement'; ops.append(m)
        for asset, ft in items:
            m = client.get_type("MutateOperation"); x = m.asset_group_asset_operation.create
            x.asset_group = g.resource_name; x.asset = asset; x.field_type = getattr(E.AssetFieldTypeEnum, ft); ops.append(m)
        try:
            res = client.get_service("GoogleAdsService").mutate(customer_id=CID, mutate_operations=ops)
            AG2 = res.mutate_operation_responses[0].asset_group_result.resource_name; print('OK AG2 created', AG2, 'ops', len(ops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:6]: print('FAILED AG2 -', e.message)
            sys.exit(0)
    # 3) 検索テーマ（元のAG1と同じ50個）をAG2へ
    th1 = [r.asset_group_signal.search_theme.text for r in q(f"SELECT campaign.id, asset_group_signal.search_theme.text FROM asset_group_signal WHERE asset_group.resource_name = '{AG1}'") if r.asset_group_signal.search_theme.text]
    th2 = {r.asset_group_signal.search_theme.text.lower() for r in q(f"SELECT campaign.id, asset_group_signal.search_theme.text FROM asset_group_signal WHERE asset_group.resource_name = '{AG2}'") if r.asset_group_signal.search_theme.text}
    ops = []
    for t in th1:
        if t.lower() in th2: continue
        o_ = client.get_type("AssetGroupSignalOperation"); sg = o_.create; sg.asset_group = AG2; sg.search_theme.text = t; ops.append(o_)
    print('themes src:', len(th1), 'to add:', len(ops))
    import time as _t
    for i in range(0, len(ops), 10):
        for attempt in range(4):
            try:
                client.get_service("AssetGroupSignalService").mutate_asset_group_signals(customer_id=CID, operations=ops[i:i+10]); print('OK themes chunk', i); break
            except GoogleAdsException as ex:
                print('retry themes chunk', i, [e.message[:80] for e in ex.failure.errors[:1]]); _t.sleep(3)
    # 4) オーディエンスシグナル（P-Max_LP2_AG1と同じ条件）
    has_aud = [r for r in q(f"SELECT campaign.id, asset_group_signal.audience.audience FROM asset_group_signal WHERE asset_group.resource_name = '{AG2}'") if r.asset_group_signal.audience.audience]
    if not has_aud:
        srcsig = [r.asset_group_signal.audience.audience for r in q(f"SELECT campaign.id, asset_group_signal.audience.audience FROM asset_group_signal WHERE asset_group.resource_name = '{src.resource_name}'") if r.asset_group_signal.audience.audience]
        if srcsig:
            sa = list(q(f"SELECT audience.resource_name, audience.dimensions FROM audience WHERE audience.resource_name = '{srcsig[0]}'"))[0].audience
            aop = client.get_type("AudienceOperation"); au = aop.create; au.name = 'adsx_old_pmax_LP2_' + str(int(__import__('time').time())); au.scope = E.AudienceScopeEnum.ASSET_GROUP; au.asset_group = AG2
            for d in sa.dimensions:
                nd = client.get_type("AudienceDimension"); client.copy_from(nd, d); au.dimensions.append(nd)
            try:
                au_rn = client.get_service("AudienceService").mutate_audiences(customer_id=CID, operations=[aop]).results[0].resource_name
                sop = client.get_type("AssetGroupSignalOperation"); sg = sop.create; sg.asset_group = AG2; sg.audience.audience = au_rn
                client.get_service("AssetGroupSignalService").mutate_asset_group_signals(customer_id=CID, operations=[sop]); print('OK audience signal for AG2')
            except GoogleAdsException as ex:
                for e in ex.failure.errors[:3]: print('FAILED audience -', e.message)
    # 5) キャンペーンのアセットをLP1の構成に（サイトリンク以外）
    def camp_assets(cid):
        d = {}
        for r in q(f"SELECT campaign.id, campaign_asset.resource_name, campaign_asset.asset, campaign_asset.field_type FROM campaign_asset WHERE campaign.id = {cid} AND campaign_asset.status != 'REMOVED'"):
            d.setdefault(r.campaign_asset.field_type.name, []).append((r.campaign_asset.resource_name, r.campaign_asset.asset))
        return d
    newa, olda = camp_assets(P1[0]), camp_assets(OLDC[0])
    print('P1 assets:', {k: len(v) for k, v in newa.items()}); print('OLD assets:', {k: len(v) for k, v in olda.items()})
    ops = []
    for ft, items in newa.items():
        na = {a for _, a in items}; oa = {a for _, a in olda.get(ft, [])}
        for rn, a in olda.get(ft, []):
            if a not in na:
                m = client.get_type("MutateOperation"); m.campaign_asset_operation.remove = rn; ops.append(m)
        for rn, a in items:
            if a not in oa:
                m = client.get_type("MutateOperation"); c = m.campaign_asset_operation.create; c.campaign = OLDC[1]; c.asset = a; c.field_type = getattr(E.AssetFieldTypeEnum, ft); ops.append(m)
    for ft, items in olda.items():
        if ft not in newa:
            print('OLD-only type removed:', ft, len(items))
            for rn, a in items:
                m = client.get_type("MutateOperation"); m.campaign_asset_operation.remove = rn; ops.append(m)
    if ops:
        try:
            client.get_service("GoogleAdsService").mutate(customer_id=CID, mutate_operations=ops); print('OK campaign assets replaced, ops:', len(ops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED campaign assets -', e.message)
    # 6) 結果
    for nm, agrn in (('AG1', AG1), ('AG2', AG2)):
        for r in q(f"SELECT campaign.id, asset_group.name, asset_group.final_urls, asset_group.ad_strength, asset_group.status, asset_group.primary_status FROM asset_group WHERE asset_group.resource_name = '{agrn}'"):
            print('RESULT|', nm, r.asset_group.name, list(r.asset_group.final_urls), r.asset_group.status.name, r.asset_group.primary_status.name, r.asset_group.ad_strength.name)
        cnt = {}
        for r in q(f"SELECT campaign.id, asset_group_asset.field_type FROM asset_group_asset WHERE asset_group.resource_name = '{agrn}' AND asset_group_asset.status != 'REMOVED'"):
            cnt[r.asset_group_asset.field_type.name] = cnt.get(r.asset_group_asset.field_type.name, 0) + 1
        print('RESULT|', nm, 'assets', cnt)
    print('RESULT| campaign assets now', {k: len(v) for k, v in camp_assets(OLDC[0]).items()})
    sys.exit(0)
if MODE == 'pmax_sl':
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    camps = {r.campaign.name: r.campaign.id for r in q("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED'")}
    OLDC = camps['ouca_supplement_pmax']
    ags = {r.asset_group.name: r.asset_group.resource_name for r in q(f"SELECT campaign.id, asset_group.name, asset_group.resource_name FROM asset_group WHERE campaign.id = {OLDC} AND asset_group.status != 'REMOVED'")}
    print('asset groups:', list(ags))
    def sl(cid):
        return [r.campaign_asset.asset for r in q(f"SELECT campaign.id, campaign_asset.asset FROM campaign_asset WHERE campaign.id = {cid} AND campaign_asset.field_type = 'SITELINK' AND campaign_asset.status != 'REMOVED'")]
    lp1 = sl(camps['P-Max_LP1']); lp2 = sl(camps['P-Max_LP2'])
    print('sitelinks LP1/LP2:', len(lp1), len(lp2))
    ok = True
    for nm, items in (('OUCA_supplement_pmax_LP2', lp2), ('OUCA_supplement_pmax', lp1)):
        ops = []
        for a in items:
            m = client.get_type("MutateOperation"); x = m.asset_group_asset_operation.create
            x.asset_group = ags[nm]; x.asset = a; x.field_type = E.AssetFieldTypeEnum.SITELINK; ops.append(m)
        try:
            client.get_service("GoogleAdsService").mutate(customer_id=CID, mutate_operations=ops); print('OK asset-group sitelinks:', nm, len(ops))
        except GoogleAdsException as ex:
            ok = False
            for e in ex.failure.errors[:3]: print('FAILED', nm, '-', str(e.error_code).replace(chr(10), ' '), '|', e.message)
    if ok:
        ops = []
        for r in q(f"SELECT campaign.id, campaign_asset.resource_name FROM campaign_asset WHERE campaign.id = {OLDC} AND campaign_asset.field_type = 'SITELINK' AND campaign_asset.status != 'REMOVED'"):
            m = client.get_type("MutateOperation"); m.campaign_asset_operation.remove = r.campaign_asset.resource_name; ops.append(m)
        client.get_service("GoogleAdsService").mutate(customer_id=CID, mutate_operations=ops); print('OK campaign-level sitelinks removed:', len(ops))
    for nm, rn in ags.items():
        n = len(list(q(f"SELECT campaign.id, asset_group_asset.asset FROM asset_group_asset WHERE asset_group.resource_name = '{rn}' AND asset_group_asset.field_type = 'SITELINK' AND asset_group_asset.status != 'REMOVED'")))
        print('RESULT|', nm, 'asset-group sitelinks', n)
    print('RESULT| campaign sitelinks', len(sl(OLDC)))
    sys.exit(0)
if MODE == 'neg_all':
    # config の NEG を、全キャンペーン（検索・P-Max／停止中も含む）へ「部分一致ではなくフレーズ一致」の除外KWとして差分登録
    import json as _j
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    cfg = _j.load(open('ads_setup/config.json', encoding='utf-8'))
    camps = [(r.campaign.id, r.campaign.name, r.campaign.status.name, r.campaign.advertising_channel_type.name) for r in q("SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type FROM campaign WHERE campaign.status != 'REMOVED' AND campaign.advertising_channel_type IN ('SEARCH', 'PERFORMANCE_MAX')")]
    for cid_, cname, cst, ctype in camps:
        hv = {r.campaign_criterion.keyword.text.lower() for r in q(f"SELECT campaign_criterion.keyword.text FROM campaign_criterion WHERE campaign.id = {cid_} AND campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'")}
        nops = []
        for t in cfg['NEG']:
            if t.lower() in hv: continue
            op = client.get_type("CampaignCriterionOperation"); n = op.create; n.campaign = f"customers/{CID}/campaigns/{cid_}"
            n.negative = True; n.keyword.text = t; n.keyword.match_type = E.KeywordMatchTypeEnum.PHRASE; nops.append(op)
        print(f'{cname} [{cst}/{ctype}] existing negatives: {len(hv)} / to add: {len(nops)}', [o.create.keyword.text for o in nops][:15])
        if nops:
            try:
                client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=CID, operations=nops); print('  OK added', len(nops))
            except GoogleAdsException as ex:
                for e in ex.failure.errors[:5]: print('  FAILED -', e.message)
    sys.exit(0)
if MODE == 'copy_scan':
    # 広告文・アセットに NG 表現（生きた／定着／増える／有効成分 等）が無いか全文スキャン（読み取りのみ）
    import re as _re
    PAT = _re.compile(r'生き|生菌|定着|増え|増や|有効成分|プロバイオ|ビフィズス|乳酸菌|菌を育て|菌を届け|菌の力|腸まで|腸に届|届く')
    def chk(tag, where, text):
        if text and PAT.search(text):
            print('HIT|', tag, '|', where, '|', text)
    print("== RSA ads ==")
    for r in q("SELECT campaign.name, campaign.status, ad_group.name, ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad WHERE ad_group_ad.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        tag = f"{r.campaign.name}[{r.campaign.status.name}]/{r.ad_group.name}/ad{r.ad_group_ad.ad.id}[{r.ad_group_ad.status.name}]"
        for h in r.ad_group_ad.ad.responsive_search_ad.headlines: chk(tag, 'headline', h.text)
        for d in r.ad_group_ad.ad.responsive_search_ad.descriptions: chk(tag, 'description', d.text)
    print("== asset group assets ==")
    for r in q("SELECT campaign.name, campaign.status, asset_group.name, asset_group.status, asset_group_asset.field_type, asset.text_asset.text FROM asset_group_asset WHERE asset_group_asset.status != 'REMOVED' AND campaign.status != 'REMOVED' AND asset.type = 'TEXT'"):
        chk(f"{r.campaign.name}[{r.campaign.status.name}]/{r.asset_group.name}[{r.asset_group.status.name}]", r.asset_group_asset.field_type.name, r.asset.text_asset.text)
    print("== sitelink / callout / snippet assets (account-wide) ==")
    for r in q("SELECT asset.id, asset.type, asset.sitelink_asset.link_text, asset.sitelink_asset.description1, asset.sitelink_asset.description2, asset.callout_asset.callout_text, asset.structured_snippet_asset.values, asset.promotion_asset.promotion_target FROM asset WHERE asset.type IN ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'PROMOTION')"):
        a = r.asset
        for w, t in (('sl_text', a.sitelink_asset.link_text), ('sl_d1', a.sitelink_asset.description1), ('sl_d2', a.sitelink_asset.description2), ('callout', a.callout_asset.callout_text), ('snippet', ' / '.join(a.structured_snippet_asset.values)), ('promo', a.promotion_asset.promotion_target)):
            chk(f'asset{a.id}[{a.type_.name}]', w, t)
    print("== search themes ==")
    for r in q("SELECT campaign.name, asset_group.name, asset_group_signal.search_theme.text FROM asset_group_signal WHERE asset_group_signal.search_theme.text != ''"):
        chk(f"{r.campaign.name}/{r.asset_group.name}", 'search_theme', r.asset_group_signal.search_theme.text)
    print("== image/video asset names (文字入り画像は目視確認が必要) ==")
    for r in q("SELECT campaign.name, campaign.status, asset_group.name, asset_group_asset.field_type, asset.name, asset.image_asset.full_size.url FROM asset_group_asset WHERE asset_group_asset.status != 'REMOVED' AND campaign.status != 'REMOVED' AND asset.type = 'IMAGE'"):
        print('IMG|', r.campaign.name, '|', r.asset_group.name, '|', r.asset_group_asset.field_type.name, '|', r.asset.name, '|', r.asset.image_asset.full_size.url)
    sys.exit(0)
if MODE == 'price_scan':
    # 価格・数量・初回特典の表記が残っている広告文／アセットを洗い出す（読み取りのみ）
    import re as _re
    PAT = _re.compile(r'\d+%|％|OFF|オフ|割引|初回|19,?980|16,?983|10,?800|4,?320|666|360|円|粒|袋|箱|1ヶ月|1か月|ヶ月分|定期|送料|限定|キャンペーン|お試し|トライアル')
    def chk(tag, where, text):
        if text and PAT.search(text):
            print('HIT|', tag, '|', where, '|', text)
    print("== RSA ads ==")
    for r in q("SELECT campaign.name, campaign.status, ad_group.name, ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.final_urls, ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad WHERE ad_group_ad.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        tag = f"{r.campaign.name}[{r.campaign.status.name}]/{r.ad_group.name}/ad{r.ad_group_ad.ad.id}[{r.ad_group_ad.status.name}]"
        print('AD|', tag, '|', list(r.ad_group_ad.ad.final_urls))
        for i, h in enumerate(r.ad_group_ad.ad.responsive_search_ad.headlines): chk(tag, f'headline{i+1}', h.text)
        for i, d in enumerate(r.ad_group_ad.ad.responsive_search_ad.descriptions): chk(tag, f'description{i+1}', d.text)
    print("== asset group assets ==")
    for r in q("SELECT campaign.name, campaign.status, asset_group.name, asset_group.status, asset_group_asset.field_type, asset_group_asset.asset, asset.text_asset.text FROM asset_group_asset WHERE asset_group_asset.status != 'REMOVED' AND campaign.status != 'REMOVED' AND asset.type = 'TEXT'"):
        chk(f"{r.campaign.name}[{r.campaign.status.name}]/{r.asset_group.name}[{r.asset_group.status.name}]", r.asset_group_asset.field_type.name + ' ' + r.asset_group_asset.asset, r.asset.text_asset.text)
    print("== sitelink / callout / snippet / promotion / price assets (account-wide) ==")
    for r in q("SELECT asset.id, asset.resource_name, asset.type, asset.sitelink_asset.link_text, asset.sitelink_asset.description1, asset.sitelink_asset.description2, asset.callout_asset.callout_text, asset.structured_snippet_asset.values, asset.promotion_asset.promotion_target, asset.promotion_asset.percent_off, asset.promotion_asset.money_amount_off.amount_micros, asset.price_asset.type FROM asset WHERE asset.type IN ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'PROMOTION', 'PRICE')"):
        a = r.asset
        for w, t in (('sl_text', a.sitelink_asset.link_text), ('sl_d1', a.sitelink_asset.description1), ('sl_d2', a.sitelink_asset.description2), ('callout', a.callout_asset.callout_text), ('snippet', ' / '.join(a.structured_snippet_asset.values)), ('promo', a.promotion_asset.promotion_target)):
            chk(f'asset{a.id}[{a.type_.name}]', w, t)
        if a.type_.name in ('PROMOTION', 'PRICE'): print('HIT|', f'asset{a.id}[{a.type_.name}]', '|', a.resource_name, '| percent_off', a.promotion_asset.percent_off, 'money_off', a.promotion_asset.money_amount_off.amount_micros)
    print("== which campaigns use those assets ==")
    for r in q("SELECT campaign.name, campaign.status, campaign_asset.field_type, campaign_asset.status, asset.id FROM campaign_asset WHERE campaign_asset.status != 'REMOVED' AND campaign.status != 'REMOVED' AND campaign_asset.field_type IN ('SITELINK','CALLOUT','STRUCTURED_SNIPPET','PROMOTION','PRICE')"):
        print('LINK|', r.campaign.name, r.campaign.status.name, r.campaign_asset.field_type.name, r.campaign_asset.status.name, 'asset', r.asset.id)
    sys.exit(0)
if MODE in ('copy_update_list', 'copy_update'):
    # 価格・数量表記の更新（配信中の3キャンペーンのみ）。copy_update_list は計画の表示だけ、copy_update が実行
    from google.ads.googleads.errors import GoogleAdsException
    from google.api_core import protobuf_helpers
    APPLY = (MODE == 'copy_update'); E = client.enums
    CAMPS = ('OUCA_supplement_search', 'ouca_supplement_pmax_LP1', 'ouca_supplement_pmax_LP2')
    CQ = ",".join("'%s'" % c for c in CAMPS)
    MAP = {
      '1ヶ月19,980円。理由がある': '通常10,800円。理由がある',
      '1日約666円という選び方': '1日約288円という選び方',
      '初回15%OFF 16,983円': '初回60%OFF 4,320円',
      'まず1ヶ月、自分に投資する': 'まず1袋、自分に投資する',
      'まずは1ヶ月、試してみる': 'まずは1袋、試してみる',
      '初回15%OFFで始める腸活': '初回60%OFFで始める腸活',
      '2粒に酪酸発酵物222mg': '1粒に酪酸発酵物111mg',
      '1ヶ月19,980円。高いのには理由があります。菌でなく酪酸を2粒に222mg配合。': '通常10,800円。高いのには理由があります。菌でなく酪酸を1粒に111mg配合。',
      '1日あたり約666円。安さでは選ばない、そう決めている方への酪酸サプリです。初回15%OFF。': '1日あたり約288円。安さでは選ばない、そう決めている方への酪酸サプリです。初回60%OFF。',
      '会社には投資する。自分には？経営者のためのハイエンドサプリメント。1日約666円。': '会社には投資する。自分には？経営者のためのハイエンドサプリメント。1日約288円。',
      '会社には投資する。自分には？初回15%OFF。': '会社には投資する。自分には？初回60%OFF。',
      '安いサプリを何年も続けるより、まず1ヶ月。人生を美しく謳歌するためのOUCA。': '安いサプリを何年も続けるより、まず1袋。人生を美しく謳歌するためのOUCA。',
      '菌ではなく、約1000日発酵させた酪酸発酵物そのものを届けます。初回15%OFF。': '菌ではなく、約1000日発酵させた酪酸発酵物そのものを届けます。初回60%OFF。',
      '1日あたり約666円。安さで選ばない、そんな基準で選ぶ酪酸サプリです。': '1日あたり約288円。安さで選ばない、そんな基準で選ぶ酪酸サプリです。',
      '安いサプリを続ける前に、まず1ヶ月。初回15%OFFで、丁寧に試せます。': '安いサプリを続ける前に、まず1袋。初回60%OFFで、丁寧に試せます。',
      '1日約666円。毎月300個限定生産のハイエンドサプリメントOUCA supplement。': '1日約288円。毎月300個限定生産のハイエンドサプリメントOUCA supplement。',
      '高い。だが、中身が違います。菌でなく酪酸そのものを2粒に222mg。': '高い。だが、中身が違います。菌でなく酪酸そのものを1粒に111mg。',
      '説明はいらない、結果で選ぶ。国内GMP工場製造、101種の成分を2粒に。': '説明はいらない、結果で選ぶ。国内GMP工場製造、101種の成分を1粒に。',
      '説明はいらない、中身で選ぶ。国内GMP工場製造、101種の成分を2粒に。': '説明はいらない、中身で選ぶ。国内GMP工場製造、101種の成分を1粒に。',
      # サイトリンク・コールアウト
      '初回15%OFF・送料無料': '初回60%OFF・送料無料',
      '¥19,980／30日分': '¥4,320（通常¥10,800）',
      '1日1〜3粒。まずは1ヶ月から': '1日1〜3粒。まずは1袋から',
      '初回15%OFF': '初回60%OFF',
    }
    def mp(t): return MAP.get(t, t)
    def mut(label, fn):
        if not APPLY: print('  (dry-run)', label); return None
        try:
            r = fn(); print('  OK', label); return r
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:3]: print('  FAILED', label, '|', e.message)
    # --- 1) 検索広告（その場で更新）---
    print('== RSA ==')
    for r in q(f"SELECT campaign.name, ad_group.name, ad_group_ad.ad.resource_name, ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad WHERE campaign.name = 'OUCA_supplement_search' AND ad_group_ad.status != 'REMOVED'"):
        ad = r.ad_group_ad.ad; rsa = ad.responsive_search_ad
        ch = [(h.text, mp(h.text)) for h in rsa.headlines]; cd = [(d.text, mp(d.text)) for d in rsa.descriptions]
        diffs = [(a, b) for a, b in ch + cd if a != b]
        print('RSA|', r.ad_group.name, '|', len(diffs), 'changes')
        for a, b in diffs: print('   ', a, '=>', b)
        if not diffs: continue
        def do(ad=ad, rsa=rsa):
            op = client.get_type("AdOperation"); u = op.update; u.resource_name = ad.resource_name
            seen = set()
            for h in rsa.headlines:
                t = mp(h.text)
                if t in seen: continue
                seen.add(t); x = client.get_type("AdTextAsset"); x.text = t
                if h.pinned_field: x.pinned_field = h.pinned_field
                u.responsive_search_ad.headlines.append(x)
            seen = set()
            for d in rsa.descriptions:
                t = mp(d.text)
                if t in seen: continue
                seen.add(t); x = client.get_type("AdTextAsset"); x.text = t
                if d.pinned_field: x.pinned_field = d.pinned_field
                u.responsive_search_ad.descriptions.append(x)
            client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
            return client.get_service("AdService").mutate_ads(customer_id=CID, operations=[op])
        mut('update RSA ' + r.ad_group.name, do)
    # --- 2) P-Max の文章アセット（新アセットに差し替え）---
    print('== PMAX text ==')
    text_assets = {}
    for r in q("SELECT asset.resource_name, asset.text_asset.text FROM asset WHERE asset.type = 'TEXT'"): text_assets[r.asset.text_asset.text] = r.asset.resource_name
    FT = {'HEADLINE': E.AssetFieldTypeEnum.HEADLINE, 'LONG_HEADLINE': E.AssetFieldTypeEnum.LONG_HEADLINE, 'DESCRIPTION': E.AssetFieldTypeEnum.DESCRIPTION}
    def get_text_asset(t):
        if t in text_assets: return text_assets[t]
        op = client.get_type("AssetOperation"); op.create.text_asset.text = t
        rn = client.get_service("AssetService").mutate_assets(customer_id=CID, operations=[op]).results[0].resource_name
        text_assets[t] = rn; return rn
    for r in q(f"SELECT campaign.name, asset_group.name, asset_group.resource_name, asset_group_asset.resource_name, asset_group_asset.field_type, asset.text_asset.text FROM asset_group_asset WHERE asset_group_asset.status != 'REMOVED' AND campaign.name IN ({CQ}) AND asset.type = 'TEXT'"):
        t = r.asset.text_asset.text; n = mp(t); ft = r.asset_group_asset.field_type.name
        if n == t or ft not in FT: continue
        print('PMAX|', r.campaign.name, '|', ft, '|', t, '=>', n)
        def do(r=r, n=n, ft=ft):
            if APPLY: new_rn = get_text_asset(n)
            ops = []
            m = client.get_type("MutateOperation"); m.asset_group_asset_operation.remove = r.asset_group_asset.resource_name; ops.append(m)
            m2 = client.get_type("MutateOperation"); c = m2.asset_group_asset_operation.create; c.asset_group = r.asset_group.resource_name; c.asset = new_rn; c.field_type = FT[ft]; ops.append(m2)
            return ga.mutate(customer_id=CID, mutate_operations=ops)
        mut(f'swap {ft} in {r.asset_group.name}', do)
    # --- 3) サイトリンク（新アセットを作って、キャンペーンの紐づけを入れ替え）---
    print('== SITELINK ==')
    sl_new = {}
    for r in q(f"SELECT campaign.name, campaign.resource_name, campaign_asset.resource_name, asset.id, asset.final_urls, asset.final_mobile_urls, asset.sitelink_asset.link_text, asset.sitelink_asset.description1, asset.sitelink_asset.description2 FROM campaign_asset WHERE campaign_asset.field_type = 'SITELINK' AND campaign_asset.status != 'REMOVED' AND campaign.name IN ({CQ})"):
        sa = r.asset.sitelink_asset; a, b, c_ = mp(sa.link_text), mp(sa.description1), mp(sa.description2)
        if (a, b, c_) == (sa.link_text, sa.description1, sa.description2): continue
        print('SITELINK|', r.campaign.name, '| asset', r.asset.id, '|', [sa.link_text, sa.description1, sa.description2], '=>', [a, b, c_])
        def do(r=r, sa=sa, a=a, b=b, c_=c_):
            key = (r.asset.id, a, b, c_)
            if key not in sl_new:
                op = client.get_type("AssetOperation"); x = op.create; x.sitelink_asset.link_text = a; x.sitelink_asset.description1 = b; x.sitelink_asset.description2 = c_
                x.final_urls.extend(list(r.asset.final_urls)); x.final_mobile_urls.extend(list(r.asset.final_mobile_urls))
                sl_new[key] = client.get_service("AssetService").mutate_assets(customer_id=CID, operations=[op]).results[0].resource_name
            ops = []
            o1 = client.get_type("CampaignAssetOperation"); o1.create.campaign = r.campaign.resource_name; o1.create.asset = sl_new[key]; o1.create.field_type = E.AssetFieldTypeEnum.SITELINK; ops.append(o1)
            o2 = client.get_type("CampaignAssetOperation"); o2.remove = r.campaign_asset.resource_name; ops.append(o2)
            return client.get_service("CampaignAssetService").mutate_campaign_assets(customer_id=CID, operations=ops)
        mut('swap sitelink in ' + r.campaign.name, do)
    # --- 4) コールアウト ---
    print('== CALLOUT ==')
    co_new = {}
    for r in q(f"SELECT campaign.name, campaign.resource_name, campaign_asset.resource_name, asset.id, asset.callout_asset.callout_text FROM campaign_asset WHERE campaign_asset.field_type = 'CALLOUT' AND campaign_asset.status != 'REMOVED' AND campaign.name IN ({CQ})"):
        t = r.asset.callout_asset.callout_text; n = mp(t)
        if n == t: continue
        print('CALLOUT|', r.campaign.name, '| asset', r.asset.id, '|', t, '=>', n)
        def do(r=r, n=n):
            if n not in co_new:
                op = client.get_type("AssetOperation"); op.create.callout_asset.callout_text = n
                co_new[n] = client.get_service("AssetService").mutate_assets(customer_id=CID, operations=[op]).results[0].resource_name
            ops = []
            o1 = client.get_type("CampaignAssetOperation"); o1.create.campaign = r.campaign.resource_name; o1.create.asset = co_new[n]; o1.create.field_type = E.AssetFieldTypeEnum.CALLOUT; ops.append(o1)
            o2 = client.get_type("CampaignAssetOperation"); o2.remove = r.campaign_asset.resource_name; ops.append(o2)
            return client.get_service("CampaignAssetService").mutate_campaign_assets(customer_id=CID, operations=ops)
        mut('swap callout in ' + r.campaign.name, do)
    print('done', MODE)
    sys.exit(0)
if MODE == 'rsa_dump':
    # 検索広告の全文（見出し・説明文・ピン留め）を出力（読み取りのみ）
    for r in q("SELECT campaign.name, campaign.status, ad_group.name, ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.final_urls, ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions, ad_group_ad.ad.responsive_search_ad.path1, ad_group_ad.ad.responsive_search_ad.path2 FROM ad_group_ad WHERE ad_group_ad.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        a = r.ad_group_ad.ad; rsa = a.responsive_search_ad
        print('RSA|', a.id, '|', r.campaign.name, r.campaign.status.name, '|', r.ad_group.name, '|', r.ad_group_ad.status.name, '|', list(a.final_urls), '| path', rsa.path1, rsa.path2)
        for i, h in enumerate(rsa.headlines): print('  H%d|%s|%s' % (i + 1, h.pinned_field.name if h.pinned_field else '', h.text))
        for i, d in enumerate(rsa.descriptions): print('  D%d|%s|%s' % (i + 1, d.pinned_field.name if d.pinned_field else '', d.text))
    sys.exit(0)
if MODE in ('rsa_sync_list', 'rsa_sync'):
    # 手直し済みの広告(825650261957)の文言に合わせて、他の検索広告(一時停止中のキャンペーン含む)を更新
    from google.ads.googleads.errors import GoogleAdsException
    from google.api_core import protobuf_helpers
    APPLY = (MODE == 'rsa_sync'); SKIP_AD = 825650261957
    P1, P2 = '1袋10,800円。初回4,320円', '1袋10,800円。高いのには理由があります。菌でなく酪酸を1粒に111mg配合。'
    MAP = {
      '1ヶ月19,980円。理由がある': P1, '通常10,800円。理由がある': P1,
      '1日約666円という選び方': '1日約288円という選び方',
      '初回15%OFF 16,983円': '初回60%OFF 4,320円',
      'まず1ヶ月、自分に投資する': 'まず1袋、自分に投資する',
      'まずは1ヶ月、試してみる': 'まずは1袋、試してみる',
      '初回15%OFFで始める腸活': '初回60%OFFで始める腸活',
      '2粒に酪酸発酵物222mg': '1粒に酪酸発酵物111mg',
      '1ヶ月19,980円。高いのには理由があります。菌でなく酪酸を2粒に222mg配合。': P2,
      '通常10,800円。高いのには理由があります。菌でなく酪酸を1粒に111mg配合。': P2,
      '1日あたり約666円。安さでは選ばない、そう決めている方への酪酸サプリです。初回15%OFF。': '1日あたり約288円。安さでは選ばない、そう決めている方への酪酸サプリです。初回60%OFF。',
      '会社には投資する。自分には？経営者のためのハイエンドサプリメント。1日約666円。': '会社には投資する。自分には？経営者のためのハイエンドサプリメント。1日約288円。',
      '安いサプリを何年も続けるより、まず1ヶ月。人生を美しく謳歌するためのOUCA。': '安いサプリを何年も続けるより、まず1袋。人生を美しく謳歌するためのOUCA。',
      '菌ではなく、約1000日発酵させた酪酸発酵物そのものを届けます。初回15%OFF。': '菌ではなく、約1000日発酵させた酪酸発酵物そのものを届けます。初回60%OFF。',
    }
    mp = lambda t: MAP.get(t, t)
    for r in q("SELECT campaign.name, campaign.status, ad_group.name, ad_group_ad.ad.id, ad_group_ad.ad.resource_name, ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions FROM ad_group_ad WHERE ad_group_ad.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        ad = r.ad_group_ad.ad; rsa = ad.responsive_search_ad
        if ad.id == SKIP_AD: continue
        diffs = [(x.text, mp(x.text)) for x in list(rsa.headlines) + list(rsa.descriptions) if mp(x.text) != x.text]
        print('RSA|', ad.id, r.campaign.name, r.campaign.status.name, '|', r.ad_group.name, '|', len(diffs), 'changes')
        for a, b in diffs: print('    ', a, '=>', b)
        if not diffs or not APPLY: continue
        op = client.get_type("AdOperation"); u = op.update; u.resource_name = ad.resource_name
        for coll, name in ((rsa.headlines, 'headlines'), (rsa.descriptions, 'descriptions')):
            seen = set()
            for x in coll:
                t = mp(x.text)
                if t in seen: continue
                seen.add(t); n = client.get_type("AdTextAsset"); n.text = t
                if x.pinned_field: n.pinned_field = x.pinned_field
                getattr(u.responsive_search_ad, name).append(n)
        client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, u._pb))
        try:
            client.get_service("AdService").mutate_ads(customer_id=CID, operations=[op]); print('  OK updated', ad.id)
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:3]: print('  FAILED', ad.id, '|', e.message)
    print('done', MODE); sys.exit(0)
if MODE == 'callout_use':
    for lv, qq in (('campaign', "SELECT campaign.name, campaign.status, campaign_asset.status, asset.callout_asset.callout_text FROM campaign_asset WHERE asset.type = 'CALLOUT' AND campaign_asset.status != 'REMOVED'"),
                   ('adgroup', "SELECT campaign.name, ad_group.name, ad_group_asset.status, asset.callout_asset.callout_text FROM ad_group_asset WHERE asset.type = 'CALLOUT' AND ad_group_asset.status != 'REMOVED'"),
                   ('customer', "SELECT customer_asset.status, asset.callout_asset.callout_text FROM customer_asset WHERE asset.type = 'CALLOUT' AND customer_asset.status != 'REMOVED'")):
        for r in q(qq):
            print('CALLOUT|', lv, '|', r.campaign.name if lv != 'customer' else '-', '|', r.asset.callout_asset.callout_text)
    sys.exit(0)
if MODE == 'callout_swap':
    # コールアウト「生きた菌でなく代謝物」→「菌でなく代謝物」。新アセットを作り、旧アセットのリンクを付け替える
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    OLD, NEW = '生きた菌でなく代謝物', '菌でなく代謝物'
    links = [(r.campaign_asset.resource_name, r.campaign.id, r.campaign.name, r.campaign_asset.asset, r.campaign_asset.status.name) for r in q(f"SELECT campaign.id, campaign.name, campaign_asset.resource_name, campaign_asset.asset, campaign_asset.status FROM campaign_asset WHERE asset.callout_asset.callout_text = '{OLD}' AND campaign_asset.status != 'REMOVED'")]
    print('old links:', len(links), [x[2] for x in links])
    exist = [r.asset.resource_name for r in q(f"SELECT asset.resource_name FROM asset WHERE asset.type = 'CALLOUT' AND asset.callout_asset.callout_text = '{NEW}'")]
    if exist: new_rn = exist[0]; print('new asset exists:', new_rn)
    else:
        op = client.get_type("AssetOperation"); op.create.callout_asset.callout_text = NEW
        new_rn = client.get_service("AssetService").mutate_assets(customer_id=CID, operations=[op]).results[0].resource_name; print('new asset:', new_rn)
    have = {r.campaign.id for r in q(f"SELECT campaign.id FROM campaign_asset WHERE asset.resource_name = '{new_rn}' AND campaign_asset.status != 'REMOVED'")}
    cons = []
    for rn, cid_, cname, a, st in links:
        if cid_ not in have:
            op = client.get_type("CampaignAssetOperation"); c = op.create; c.campaign = f"customers/{CID}/campaigns/{cid_}"; c.asset = new_rn; c.field_type = E.AssetFieldTypeEnum.CALLOUT; cons.append(op); have.add(cid_)
    if cons:
        try: client.get_service("CampaignAssetService").mutate_campaign_assets(customer_id=CID, operations=cons); print('linked new:', len(cons))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED link -', e.message)
    rops = []
    for rn, *_ in links:
        op = client.get_type("CampaignAssetOperation"); op.remove = rn; rops.append(op)
    if rops:
        try: client.get_service("CampaignAssetService").mutate_campaign_assets(customer_id=CID, operations=rops); print('removed old links:', len(rops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED remove -', e.message)
    sys.exit(0)
if MODE == 'callout_link':
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    NEW = '菌でなく代謝物'
    new_rn = [r.asset.resource_name for r in q(f"SELECT asset.resource_name FROM asset WHERE asset.type = 'CALLOUT' AND asset.callout_asset.callout_text = '{NEW}'")][0]
    camps = [(r.campaign.id, r.campaign.name) for r in q("SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED' AND campaign.advertising_channel_type IN ('SEARCH', 'PERFORMANCE_MAX')")]
    have = {r.campaign.id for r in q(f"SELECT campaign.id FROM campaign_asset WHERE asset.resource_name = '{new_rn}' AND campaign_asset.status != 'REMOVED'")}
    ops = []
    for cid_, cname in camps:
        if cid_ in have: continue
        op = client.get_type("CampaignAssetOperation"); c = op.create; c.campaign = f"customers/{CID}/campaigns/{cid_}"; c.asset = new_rn; c.field_type = E.AssetFieldTypeEnum.CALLOUT; ops.append(op); print('link ->', cname)
    if ops:
        try: client.get_service("CampaignAssetService").mutate_campaign_assets(customer_id=CID, operations=ops); print('linked:', len(ops))
        except GoogleAdsException as ex:
            for e in ex.failure.errors[:5]: print('FAILED link -', e.message)
    for r in q("SELECT campaign.name, campaign.status, asset.callout_asset.callout_text FROM campaign_asset WHERE asset.type = 'CALLOUT' AND campaign_asset.status != 'REMOVED' AND campaign.status != 'REMOVED'"):
        if '代謝物' in r.asset.callout_asset.callout_text: print('NOW|', r.campaign.name, r.campaign.status.name, r.asset.callout_asset.callout_text)
    sys.exit(0)
if MODE == 'budgets':
    for r in q("SELECT campaign.name, campaign.status, campaign_budget.amount_micros, campaign_budget.explicitly_shared, campaign.bidding_strategy_type, metrics.cost_micros FROM campaign WHERE campaign.status != 'REMOVED' AND segments.date DURING LAST_7_DAYS"):
        print('BUD|', r.campaign.name, '|', r.campaign.status.name, '|', int(r.campaign_budget.amount_micros/1e6), '|', r.campaign.bidding_strategy_type.name, '| 7d cost', int(r.metrics.cost_micros/1e6))
    sys.exit(0)
if MODE == 'neg_extra':
    # 依頼ベースの除外KW：phrase（NEG）／exact（NEG_EXACT）／broad（NEG_BROAD）。(テキスト, マッチ)で差分登録
    import json as _j
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    cfg = _j.load(open('ads_setup/config.json', encoding='utf-8'))
    want = [(t, 'PHRASE') for t in cfg['NEG']] + [(t, 'EXACT') for t in cfg.get('NEG_EXACT', [])] + [(t, 'BROAD') for t in cfg.get('NEG_BROAD', [])]
    MT = {'PHRASE': E.KeywordMatchTypeEnum.PHRASE, 'EXACT': E.KeywordMatchTypeEnum.EXACT, 'BROAD': E.KeywordMatchTypeEnum.BROAD}
    camps = [(r.campaign.id, r.campaign.name, r.campaign.status.name) for r in q("SELECT campaign.id, campaign.name, campaign.status FROM campaign WHERE campaign.status != 'REMOVED' AND campaign.advertising_channel_type IN ('SEARCH', 'PERFORMANCE_MAX')")]
    for cid_, cname, cst in camps:
        hv = {(r.campaign_criterion.keyword.text.lower(), r.campaign_criterion.keyword.match_type.name) for r in q(f"SELECT campaign_criterion.keyword.text, campaign_criterion.keyword.match_type FROM campaign_criterion WHERE campaign.id = {cid_} AND campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'")}
        ops = []
        for t, m_ in want:
            if (t.lower(), m_) in hv: continue
            op = client.get_type("CampaignCriterionOperation"); n = op.create; n.campaign = f"customers/{CID}/campaigns/{cid_}"
            n.negative = True; n.keyword.text = t; n.keyword.match_type = MT[m_]; ops.append(op)
        print(f'{cname} [{cst}] existing: {len(hv)} / to add: {len(ops)}')
        if ops:
            try:
                client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=CID, operations=ops); print('  OK added', len(ops))
            except GoogleAdsException as ex:
                for e in ex.failure.errors[:5]: print('  FAILED -', e.message)
    sys.exit(0)
if MODE == 'asset_perf':
    D1, D2 = '2026-10-07', '2026-10-25'
    def tryq(tag, gaql, fn):
        try:
            n = 0
            for r in q(gaql):
                fn(r); n += 1
            print(f'#{tag} rows={n}')
        except Exception as e:
            print(f'#{tag} ERROR', str(e)[:300].replace('\n', ' '))
    tryq('RSA', f"SELECT campaign.name, ad_group.name, ad_group_ad_asset_view.field_type, asset.text_asset.text, metrics.impressions, metrics.clicks, metrics.cost_micros FROM ad_group_ad_asset_view WHERE ad_group_ad_asset_view.field_type IN ('HEADLINE','DESCRIPTION') AND segments.date BETWEEN '{D1}' AND '{D2}' AND campaign.status != 'REMOVED'",
         lambda r: print('RSA|', r.campaign.name, '|', r.ad_group.name, '|', r.ad_group_ad_asset_view.field_type.name, '|', r.asset.text_asset.text, '|', r.metrics.impressions, '|', r.metrics.clicks, '|', int(r.metrics.cost_micros/1e6)))
    tryq('PMAX1', f"SELECT campaign.name, asset_group.name, asset_group_asset.field_type, asset.text_asset.text, metrics.impressions, metrics.clicks, metrics.interactions, metrics.conversions FROM asset_group_asset WHERE asset_group_asset.field_type IN ('HEADLINE','LONG_HEADLINE','DESCRIPTION') AND segments.date BETWEEN '{D1}' AND '{D2}' AND campaign.status != 'REMOVED'",
         lambda r: print('PMAX|', r.campaign.name, '|', r.asset_group.name, '|', r.asset_group_asset.field_type.name, '|', r.asset.text_asset.text, '|', r.metrics.impressions, '|', r.metrics.interactions, '|', r.metrics.conversions))
    tryq('SL', f"SELECT campaign.name, campaign_asset.field_type, asset.sitelink_asset.link_text, asset.callout_asset.callout_text, metrics.impressions, metrics.clicks FROM campaign_asset WHERE campaign_asset.field_type IN ('SITELINK','CALLOUT') AND segments.date BETWEEN '{D1}' AND '{D2}' AND campaign.status != 'REMOVED'",
         lambda r: print('EXT|', r.campaign.name, '|', r.campaign_asset.field_type.name, '|', r.asset.sitelink_asset.link_text, '|', r.asset.callout_asset.callout_text, '|', r.metrics.impressions, '|', r.metrics.clicks))
    tryq('KW', f"SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, metrics.cost_micros, metrics.clicks, metrics.impressions FROM keyword_view WHERE segments.date BETWEEN '{D1}' AND '{D2}' AND campaign.status != 'REMOVED' AND metrics.impressions > 0",
         lambda r: print('KW|', r.campaign.name, '|', r.ad_group.name, '|', r.ad_group_criterion.keyword.text, '|', r.ad_group_criterion.keyword.match_type.name, '|', int(r.metrics.cost_micros/1e6), '|', r.metrics.clicks, '|', r.metrics.impressions))
    sys.exit(0)
if MODE == 'ext_perf':
    D1, D2 = '2026-10-07', '2026-10-25'
    for tag, gaql in (
        ('SL_a', f"SELECT campaign.name, asset.sitelink_asset.link_text, asset.sitelink_asset.description1, metrics.impressions, metrics.clicks FROM campaign_asset WHERE campaign_asset.field_type = 'SITELINK' AND segments.date BETWEEN '{D1}' AND '{D2}'"),
        ('SL_b', f"SELECT campaign.name, asset.sitelink_asset.link_text, metrics.impressions, metrics.clicks FROM campaign_asset WHERE campaign_asset.field_type = 'SITELINK' AND segments.date BETWEEN '{D1}' AND '{D2}' AND campaign.status != 'REMOVED'"),
        ('SL_c', f"SELECT campaign.name, ad_group.name, asset.sitelink_asset.link_text, metrics.impressions, metrics.clicks FROM ad_group_asset WHERE ad_group_asset.field_type = 'SITELINK' AND segments.date BETWEEN '{D1}' AND '{D2}'"),
        ('CO', f"SELECT campaign.name, asset.callout_asset.callout_text, metrics.impressions, metrics.clicks FROM campaign_asset WHERE campaign_asset.field_type = 'CALLOUT' AND segments.date BETWEEN '{D1}' AND '{D2}'")):
        try:
            n = 0
            for r in q(gaql):
                n += 1
                if tag.startswith('SL_c'): print('EXT|', tag, '|', r.campaign.name, '|', r.ad_group.name, '|', r.asset.sitelink_asset.link_text, '|', r.metrics.impressions, '|', r.metrics.clicks)
                elif tag == 'CO': print('EXT|', tag, '|', r.campaign.name, '|', r.asset.callout_asset.callout_text, '|', r.metrics.impressions, '|', r.metrics.clicks)
                else: print('EXT|', tag, '|', r.campaign.name, '|', r.asset.sitelink_asset.link_text, '|', r.metrics.impressions, '|', r.metrics.clicks)
            print(f'#{tag} rows={n}')
        except Exception as e:
            print(f'#{tag} ERROR', str(e)[:200].replace('\n', ' '))
    sys.exit(0)
if MODE == 'kw_diag':
    # 読み取り専用：「腸活」「腸活 サプリ」のクリック率が低い原因の調査
    PERIODS = (('10/07-10/25', '2026-10-07', '2026-10-25'), ('09/17-10/06', '2026-09-17', '2026-10-06'))
    for label, d0, d1 in PERIODS:
        print(f'\n##### キーワード別（{label}） 表示>0')
        for r in q(f"""SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
            ad_group_criterion.status, ad_group_criterion.quality_info.quality_score, ad_group_criterion.quality_info.creative_quality_score,
            ad_group_criterion.quality_info.post_click_quality_score, ad_group_criterion.quality_info.search_predicted_ctr,
            metrics.impressions, metrics.clicks, metrics.ctr, metrics.average_cpc, metrics.search_impression_share,
            metrics.search_top_impression_share, metrics.search_rank_lost_impression_share
            FROM keyword_view WHERE segments.date BETWEEN '{d0}' AND '{d1}' AND metrics.impressions > 0
            ORDER BY metrics.impressions DESC LIMIT 40"""):
            k = r.ad_group_criterion; qi = k.quality_info; m = r.metrics
            print('|'.join(str(x) for x in [r.campaign.name, r.ad_group.name, k.keyword.text, k.keyword.match_type.name, k.status.name,
                  'QS', qi.quality_score, 'ad関連性', qi.creative_quality_score.name, 'LP', qi.post_click_quality_score.name, '予測CTR', qi.search_predicted_ctr.name,
                  'imp', m.impressions, 'clk', m.clicks, 'ctr', round(m.ctr * 100, 2), 'cpc', round(m.average_cpc / 1e6),
                  'IS', round(m.search_impression_share * 100, 1) if m.search_impression_share else None,
                  'topIS', round(m.search_top_impression_share * 100, 1) if m.search_top_impression_share else None,
                  'rankLost', round(m.search_rank_lost_impression_share * 100, 1) if m.search_rank_lost_impression_share else None]))
    print('\n##### 「腸活」を含むキーワードの検索語句（10/07-10/25）')
    try:
        for r in q("""SELECT search_term_view.search_term, segments.keyword.info.text, segments.keyword.info.match_type, ad_group.name,
            metrics.impressions, metrics.clicks, metrics.ctr FROM search_term_view
            WHERE segments.date BETWEEN '2026-10-07' AND '2026-10-25' AND segments.keyword.info.text LIKE '%腸活%'
            ORDER BY metrics.impressions DESC LIMIT 50"""):
            m = r.metrics
            print('|'.join(str(x) for x in [r.search_term_view.search_term, 'KW=', r.segments.keyword.info.text, r.segments.keyword.info.match_type.name,
                  r.ad_group.name, 'imp', m.impressions, 'clk', m.clicks, 'ctr', round(m.ctr * 100, 2)]))
    except Exception as e:
        print('ERROR', str(e)[:300])
    print('\n##### 広告（RSA）と広告の強度')
    for r in q("""SELECT campaign.name, ad_group.name, ad_group_ad.status, ad_group_ad.ad_strength, ad_group_ad.ad.responsive_search_ad.headlines,
        ad_group_ad.ad.final_urls, metrics.impressions, metrics.clicks, metrics.ctr FROM ad_group_ad
        WHERE ad_group_ad.status != 'REMOVED' AND campaign.advertising_channel_type = 'SEARCH' AND segments.date BETWEEN '2026-10-07' AND '2026-10-25'"""):
        a = r.ad_group_ad.ad.responsive_search_ad
        hs = [h.text for h in a.headlines]
        print('|'.join(str(x) for x in [r.campaign.name, r.ad_group.name, r.ad_group_ad.status.name, r.ad_group_ad.ad_strength.name,
              'imp', r.metrics.impressions, 'clk', r.metrics.clicks, 'ctr', round(r.metrics.ctr * 100, 2), 'URL', list(r.ad_group_ad.ad.final_urls),
              '見出し数', len(hs), '腸活を含む見出し', [h for h in hs if '腸活' in h]]))
    print('\n##### デバイス別（腸活系キーワード・10/07-10/25）')
    for r in q("""SELECT ad_group_criterion.keyword.text, segments.device, metrics.impressions, metrics.clicks, metrics.ctr
        FROM keyword_view WHERE segments.date BETWEEN '2026-10-07' AND '2026-10-25' AND ad_group_criterion.keyword.text LIKE '%腸活%' AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC"""):
        m = r.metrics
        print('|'.join(str(x) for x in [r.ad_group_criterion.keyword.text, r.segments.device.name, 'imp', m.impressions, 'clk', m.clicks, 'ctr', round(m.ctr * 100, 2)]))
    sys.exit(0)

if MODE == 'kw_diag2':
    # 読み取り専用：「腸活」系キーワードの週別推移、キャンペーン別のインプレッションシェア、直近の変更履歴
    print('\n##### 「腸活」を含むキーワード（全キャンペーン・状態問わず）週別')
    for r in q("""SELECT campaign.name, ad_group.name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, ad_group_criterion.status,
        segments.week, metrics.impressions, metrics.clicks, metrics.ctr FROM keyword_view
        WHERE segments.date BETWEEN '2026-09-14' AND '2026-10-25' AND ad_group_criterion.keyword.text LIKE '%腸活%' AND metrics.impressions > 0
        ORDER BY ad_group_criterion.keyword.text, segments.week"""):
        m = r.metrics; k = r.ad_group_criterion
        print('|'.join(str(x) for x in [k.keyword.text, k.keyword.match_type.name, k.status.name, r.campaign.name, r.ad_group.name, r.segments.week,
              'imp', m.impressions, 'clk', m.clicks, 'ctr', round(m.ctr * 100, 2)]))
    print('\n##### キャンペーン別 週別（検索）')
    for r in q("""SELECT campaign.name, campaign.status, campaign.bidding_strategy_type, segments.week, metrics.impressions, metrics.clicks, metrics.ctr, metrics.average_cpc,
        metrics.search_impression_share, metrics.search_budget_lost_impression_share, metrics.search_rank_lost_impression_share
        FROM campaign WHERE campaign.advertising_channel_type = 'SEARCH' AND segments.date BETWEEN '2026-09-14' AND '2026-10-25' AND metrics.impressions > 0
        ORDER BY campaign.name, segments.week"""):
        m = r.metrics
        print('|'.join(str(x) for x in [r.campaign.name, r.campaign.status.name, r.campaign.bidding_strategy_type.name, r.segments.week, 'imp', m.impressions, 'clk', m.clicks,
              'ctr', round(m.ctr * 100, 2), 'cpc', round(m.average_cpc / 1e6), 'IS', round(m.search_impression_share * 100, 1), 'budgetLost', round(m.search_budget_lost_impression_share * 100, 1),
              'rankLost', round(m.search_rank_lost_impression_share * 100, 1)]))
    print('\n##### 変更履歴（10/01〜）日別・種類別の件数')
    try:
        from collections import Counter
        c = Counter()
        for r in q("""SELECT change_event.change_date_time, change_event.change_resource_type, change_event.resource_change_operation, change_event.user_email
            FROM change_event WHERE change_event.change_date_time >= '2026-10-01' AND change_event.change_date_time <= '2026-10-26'
            ORDER BY change_event.change_date_time DESC LIMIT 10000"""):
            e = r.change_event
            c[(e.change_date_time[:10], e.change_resource_type.name, e.resource_change_operation.name)] += 1
        for k in sorted(c): print(k, c[k])
    except Exception as ex:
        print('ERROR', str(ex)[:300])
    sys.exit(0)

if MODE in ('intent_list', 'intent_pilot', 'intent_all'):
    # フレーズ一致のキーワードを「インテント マッチ」（API上は BROAD）へ変更する。
    # 一致タイプは直接編集できないため、「同じ内容で新しい一致タイプを作成し、古いものを削除」する。
    from google.ads.googleads.errors import GoogleAdsException
    E = client.enums
    print('KeywordMatchType members:', [m.name for m in E.KeywordMatchTypeEnum])
    rows = q("""SELECT campaign.name, campaign.status, ad_group.name, ad_group.status, ad_group_criterion.criterion_id, ad_group_criterion.resource_name,
        ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, ad_group_criterion.status, ad_group_criterion.cpc_bid_micros,
        ad_group_criterion.final_urls, ad_group_criterion.final_mobile_urls, ad_group_criterion.final_url_suffix, ad_group_criterion.tracking_url_template
        FROM ad_group_criterion WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE
        AND ad_group_criterion.status != 'REMOVED' AND ad_group.status != 'REMOVED' AND campaign.status != 'REMOVED'""")
    from collections import Counter
    cnt = Counter((r.campaign.name, r.ad_group_criterion.keyword.match_type.name, r.ad_group_criterion.status.name) for r in rows)
    for k in sorted(cnt): print('COUNT', k, cnt[k])
    phrase = [r for r in rows if r.ad_group_criterion.keyword.match_type.name == 'PHRASE']
    print('PHRASE total:', len(phrase), '/ with own bid:', sum(1 for r in phrase if r.ad_group_criterion.cpc_bid_micros),
          '/ with own final_urls:', sum(1 for r in phrase if r.ad_group_criterion.final_urls),
          '/ with suffix/tracking:', sum(1 for r in phrase if r.ad_group_criterion.final_url_suffix or r.ad_group_criterion.tracking_url_template))
    if MODE == 'intent_list':
        sys.exit(0)
    have = {(r.ad_group.name, r.ad_group_criterion.keyword.text.lower()) for r in rows if r.ad_group_criterion.keyword.match_type.name == 'BROAD'}
    targets = phrase
    if MODE == 'intent_pilot':
        targets = [r for r in phrase if r.ad_group.name == 'OUCA_supplement_ag_LP1' and r.ad_group_criterion.keyword.text == '腸活サプリ ランキング']
        print('PILOT targets:', len(targets))
    svc = client.get_service("AdGroupCriterionService")
    def chunk(lst, n):
        for i in range(0, len(lst), n): yield lst[i:i + n]
    ok = fail = skipped = 0
    for part in chunk(targets, 100):
        ops = []
        for r in part:
            c0 = r.ad_group_criterion
            rm = client.get_type("AdGroupCriterionOperation"); rm.remove = c0.resource_name; ops.append(rm)
            if (r.ad_group.name, c0.keyword.text.lower()) in have:
                skipped += 1; continue
            op = client.get_type("AdGroupCriterionOperation"); c = op.create
            c.ad_group = c0.resource_name.rsplit('~', 1)[0].replace('adGroupCriteria', 'adGroups')
            c.status = c0.status
            c.keyword.text = c0.keyword.text; c.keyword.match_type = E.KeywordMatchTypeEnum.BROAD
            if c0.cpc_bid_micros: c.cpc_bid_micros = c0.cpc_bid_micros
            for u in c0.final_urls: c.final_urls.append(u)
            for u in c0.final_mobile_urls: c.final_mobile_urls.append(u)
            if c0.final_url_suffix: c.final_url_suffix = c0.final_url_suffix
            if c0.tracking_url_template: c.tracking_url_template = c0.tracking_url_template
            ops.append(op)
        try:
            svc.mutate_ad_group_criteria(customer_id=CID, operations=ops)
            ok += len(part)
        except GoogleAdsException as ex:
            fail += len(part)
            for e in ex.failure.errors[:3]: print('FAILED -', e.message)
    print(f'RESULT mode={MODE} converted={ok} failed={fail} skipped_dup={skipped}')
    chk = q("""SELECT ad_group.name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, ad_group_criterion.status
        FROM ad_group_criterion WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED'
        AND ad_group.status != 'REMOVED' AND campaign.status != 'REMOVED'""")
    cc = Counter(r.ad_group_criterion.keyword.match_type.name for r in chk); print('AFTER match types:', dict(cc))
    sys.exit(0)

if MODE in ('exact_pause_list', 'exact_pause'):
    # 同じ広告グループに「同じ文言のインテント マッチ（BROAD）」がある完全一致キーワードを、一時停止にする（削除はしない）
    from google.ads.googleads.errors import GoogleAdsException
    from google.api_core import protobuf_helpers
    E = client.enums
    rows = q("""SELECT campaign.name, campaign.status, ad_group.name, ad_group_criterion.resource_name, ad_group_criterion.keyword.text,
        ad_group_criterion.keyword.match_type, ad_group_criterion.status FROM ad_group_criterion
        WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED'
        AND ad_group.status != 'REMOVED' AND campaign.status != 'REMOVED'""")
    norm = lambda t: ' '.join(t.lower().split())
    broad = {(r.ad_group.name, norm(r.ad_group_criterion.keyword.text)) for r in rows if r.ad_group_criterion.keyword.match_type.name == 'BROAD'}
    ex = [r for r in rows if r.ad_group_criterion.keyword.match_type.name == 'EXACT']
    both = [r for r in ex if (r.ad_group.name, norm(r.ad_group_criterion.keyword.text)) in broad]
    todo = [r for r in both if r.ad_group_criterion.status.name == 'ENABLED']
    print(f'EXACT total={len(ex)} / 同文言のインテント マッチあり={len(both)} / うち有効（停止対象）={len(todo)} / 対象外（同文言なし）={len(ex) - len(both)}')
    for r in ex:
        if r not in both: print('NOT-PAIRED|', r.campaign.name, r.ad_group.name, r.ad_group_criterion.keyword.text)
    if MODE == 'exact_pause' and todo:
        svc = client.get_service("AdGroupCriterionService"); ok = fail = 0
        for i in range(0, len(todo), 100):
            ops = []
            for r in todo[i:i + 100]:
                op = client.get_type("AdGroupCriterionOperation"); c = op.update
                c.resource_name = r.ad_group_criterion.resource_name; c.status = E.AdGroupCriterionStatusEnum.PAUSED
                client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, c._pb)); ops.append(op)
            try:
                svc.mutate_ad_group_criteria(customer_id=CID, operations=ops); ok += len(ops)
            except GoogleAdsException as e:
                fail += len(ops)
                for er in e.failure.errors[:3]: print('FAILED -', er.message)
        print(f'RESULT paused={ok} failed={fail}')
        from collections import Counter
        chk = q("""SELECT ad_group_criterion.keyword.match_type, ad_group_criterion.status FROM ad_group_criterion WHERE ad_group_criterion.type = 'KEYWORD'
            AND ad_group_criterion.negative = FALSE AND ad_group_criterion.status != 'REMOVED' AND ad_group.status != 'REMOVED' AND campaign.status != 'REMOVED'""")
        print('AFTER:', dict(Counter((r.ad_group_criterion.keyword.match_type.name, r.ad_group_criterion.status.name) for r in chk)))
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
# 1791377837
