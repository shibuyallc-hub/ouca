"""Google広告の新構成を「一時停止」状態で作成する。mode: inspect / validate / apply"""
import os, sys, json
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
    for t, f in [('customer',customer),('campaigns',campaigns),('conversion actions',convs),('image assets',images),
                 ('asset group image assets',ag_assets),('campaign assets',camp_assets),('bidding strategies',bidstr),
                 ('custom audiences',custaud),('ad groups',adgroups)]:
        section(t, f)
    sys.exit(0)
print("unknown mode", MODE)
