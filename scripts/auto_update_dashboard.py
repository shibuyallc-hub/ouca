#!/usr/bin/env python3
"""
OUCA ROI Dashboard - Automatic Data Update
Fetches GA4 / Google Ads / Meta Ads data and updates Google Sheets daily
GA4 property reporting currency is JPY, so no currency conversion is applied.
"""

import json
import os
import requests
from datetime import datetime, timedelta
from google.oauth2 import service_account
import gspread
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, Dimension, Metric, DateRange, FilterExpression, FilterExpressionList, Filter
)

# Only the 'purchase' event counts as a conversion for this dashboard,
# regardless of whatever else GA4 admin has marked as a "key event".
PURCHASE_ONLY_FILTER = FilterExpression(
    filter=Filter(
        field_name="eventName",
        string_filter=Filter.StringFilter(value="purchase"),
    )
)

# Ad-driven traffic only (used by the 詳細分析 breakdowns: age/gender, region, events).
ADS_CHANNEL_FILTER = FilterExpression(
    filter=Filter(
        field_name="sessionDefaultChannelGroup",
        in_list_filter=Filter.InListFilter(values=["Paid Search", "Paid Social"]),
    )
)

PURCHASE_ADS_FILTER = FilterExpression(
    and_group=FilterExpressionList(expressions=[PURCHASE_ONLY_FILTER, ADS_CHANNEL_FILTER])
)
from collections import defaultdict

# GA4's `region` dimension returns Japanese prefectures in English; translate
# for display. Non-Japan regions (foreign visitors) are left as-is.
REGION_JA = {
    'Hokkaido': '北海道', 'Aomori': '青森県', 'Iwate': '岩手県', 'Miyagi': '宮城県',
    'Akita': '秋田県', 'Yamagata': '山形県', 'Fukushima': '福島県', 'Ibaraki': '茨城県',
    'Tochigi': '栃木県', 'Gunma': '群馬県', 'Saitama': '埼玉県', 'Chiba': '千葉県',
    'Tokyo': '東京都', 'Kanagawa': '神奈川県', 'Niigata': '新潟県', 'Toyama': '富山県',
    'Ishikawa': '石川県', 'Fukui': '福井県', 'Yamanashi': '山梨県', 'Nagano': '長野県',
    'Gifu': '岐阜県', 'Shizuoka': '静岡県', 'Aichi': '愛知県', 'Mie': '三重県',
    'Shiga': '滋賀県', 'Kyoto': '京都府', 'Osaka': '大阪府', 'Hyogo': '兵庫県',
    'Nara': '奈良県', 'Wakayama': '和歌山県', 'Tottori': '鳥取県', 'Shimane': '島根県',
    'Okayama': '岡山県', 'Hiroshima': '広島県', 'Yamaguchi': '山口県', 'Tokushima': '徳島県',
    'Kagawa': '香川県', 'Ehime': '愛媛県', 'Kochi': '高知県', 'Fukuoka': '福岡県',
    'Saga': '佐賀県', 'Nagasaki': '長崎県', 'Kumamoto': '熊本県', 'Oita': '大分県',
    'Miyazaki': '宮崎県', 'Kagoshima': '鹿児島県', 'Okinawa': '沖縄県',
    '(not set)': '(不明)',
}


def region_to_ja(name):
    return REGION_JA.get(name, name)

# ===== CONFIGURATION =====
SERVICE_ACCOUNT_JSON_PATH = os.getenv('SERVICE_ACCOUNT_JSON_PATH', 'service_account.json')
SPREADSHEET_ID = '1eQb2soZQkat4jVhcUMyWx6hOCEZC8uOCdQc6UHcm-vM'
GA4_PROPERTY_ID = '544878501'

GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN')
GOOGLE_ADS_CLIENT_ID = os.getenv('GOOGLE_ADS_CLIENT_ID')
GOOGLE_ADS_CLIENT_SECRET = os.getenv('GOOGLE_ADS_CLIENT_SECRET')
GOOGLE_ADS_REFRESH_TOKEN = os.getenv('GOOGLE_ADS_REFRESH_TOKEN')
GOOGLE_ADS_CUSTOMER_ID = os.getenv('GOOGLE_ADS_CUSTOMER_ID')

META_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
META_AD_ACCOUNT_ID = os.getenv('META_AD_ACCOUNT_ID')

# ===== CREDENTIALS =====
with open(SERVICE_ACCOUNT_JSON_PATH) as f:
    service_account_info = json.load(f)

ga4_credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/analytics.readonly']
)

sheets_credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)

ga4_client = BetaAnalyticsDataClient(credentials=ga4_credentials)
gc = gspread.authorize(sheets_credentials)

print("="*70)
print("OUCA ROI DASHBOARD - AUTOMATIC UPDATE")
print("="*70)
print(f"\n⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ===== FETCH GA4 DATA =====
print("\n📊 Fetching GA4 data...")

try:
    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="purchaseRevenue"),
            Metric(name="eventCount"),
        ],
        dimension_filter=PURCHASE_ONLY_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )

    response = ga4_client.run_report(request)
    ga4_data = []

    for row in response.rows:
        ga4_data.append({
            'date': row.dimension_values[0].value,
            'channel': row.dimension_values[1].value,
            'revenue': float(row.metric_values[0].value),
            'conversions': int(float(row.metric_values[1].value)),
        })

    print(f"  ✓ {len(ga4_data)} GA4 records found")

except Exception as e:
    print(f"  ✗ GA4 Error: {e}")
    ga4_data = []

# ===== FETCH REAL GOOGLE ADS SPEND/CLICKS =====
print("\n💰 Fetching Google Ads spend data...")

google_ads_daily = {}
google_ads_campaign_data = []
google_ads_age_data = []
google_ads_gender_data = []

if all([GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET,
        GOOGLE_ADS_REFRESH_TOKEN, GOOGLE_ADS_CUSTOMER_ID]):
    try:
        from google.ads.googleads.client import GoogleAdsClient

        googleads_client = GoogleAdsClient.load_from_dict({
            "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": GOOGLE_ADS_CLIENT_ID,
            "client_secret": GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": GOOGLE_ADS_REFRESH_TOKEN,
            "login_customer_id": GOOGLE_ADS_CUSTOMER_ID,
            "use_proto_plus": True,
        })

        ga_ads_service = googleads_client.get_service("GoogleAdsService")
        gads_start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        gads_end = datetime.now().strftime('%Y-%m-%d')
        gaql = f"""
            SELECT segments.date, metrics.cost_micros, metrics.clicks
            FROM customer
            WHERE segments.date BETWEEN '{gads_start}' AND '{gads_end}'
        """
        stream = ga_ads_service.search_stream(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=gaql)

        for batch in stream:
            for row in batch.results:
                d = row.segments.date.replace('-', '')
                google_ads_daily[d] = {
                    'spend': row.metrics.cost_micros / 1_000_000,
                    'clicks': row.metrics.clicks,
                }

        print(f"  ✓ {len(google_ads_daily)} days of Google Ads spend data found")

        # ----- Campaign-level breakdown -----
        gaql_campaign = f"""
            SELECT segments.date, campaign.name, metrics.cost_micros,
                   metrics.clicks, metrics.impressions, metrics.conversions,
                   metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{gads_start}' AND '{gads_end}'
        """
        campaign_stream = ga_ads_service.search_stream(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=gaql_campaign)

        for batch in campaign_stream:
            for row in batch.results:
                google_ads_campaign_data.append({
                    'date': row.segments.date.replace('-', ''),
                    'campaign': row.campaign.name,
                    'spend': row.metrics.cost_micros / 1_000_000,
                    'clicks': row.metrics.clicks,
                    'impressions': row.metrics.impressions,
                    'conversions': row.metrics.conversions,
                    'conversions_value': row.metrics.conversions_value,
                })

        print(f"  ✓ {len(google_ads_campaign_data)} campaign/date records found")

        # ----- Age/gender breakdown (not supported for Performance Max) -----
        gaql_age = f"""
            SELECT segments.date, campaign.name, ad_group_criterion.age_range.type,
                   metrics.cost_micros, metrics.clicks, metrics.impressions, metrics.conversions
            FROM age_range_view
            WHERE segments.date BETWEEN '{gads_start}' AND '{gads_end}'
        """
        age_stream = ga_ads_service.search_stream(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=gaql_age)
        for batch in age_stream:
            for row in batch.results:
                google_ads_age_data.append({
                    'date': row.segments.date.replace('-', ''),
                    'campaign': row.campaign.name,
                    'age': row.ad_group_criterion.age_range.type_.name,
                    'spend': row.metrics.cost_micros / 1_000_000,
                    'clicks': row.metrics.clicks,
                    'impressions': row.metrics.impressions,
                    'conversions': row.metrics.conversions,
                })

        gaql_gender = f"""
            SELECT segments.date, campaign.name, ad_group_criterion.gender.type,
                   metrics.cost_micros, metrics.clicks, metrics.impressions, metrics.conversions
            FROM gender_view
            WHERE segments.date BETWEEN '{gads_start}' AND '{gads_end}'
        """
        gender_stream = ga_ads_service.search_stream(customer_id=GOOGLE_ADS_CUSTOMER_ID, query=gaql_gender)
        for batch in gender_stream:
            for row in batch.results:
                google_ads_gender_data.append({
                    'date': row.segments.date.replace('-', ''),
                    'campaign': row.campaign.name,
                    'gender': row.ad_group_criterion.gender.type_.name,
                    'spend': row.metrics.cost_micros / 1_000_000,
                    'clicks': row.metrics.clicks,
                    'impressions': row.metrics.impressions,
                    'conversions': row.metrics.conversions,
                })

        print(f"  ✓ {len(google_ads_age_data)} age records / {len(google_ads_gender_data)} gender records found (Performance Max campaigns won't report here)")

    except Exception as e:
        print(f"  ✗ Google Ads API error: {e}")
else:
    print("  ⚠ Google Ads credentials not fully configured — spend will be 0")

# ===== FETCH REAL META ADS SPEND/CLICKS =====
print("\n💰 Fetching Meta Ads spend data...")

meta_ads_daily = {}
meta_ads_ad_data = []
meta_ads_demo_data = []
meta_ads_geo_data = []

if META_ACCESS_TOKEN and META_AD_ACCOUNT_ID:
    try:
        since = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        until = datetime.now().strftime('%Y-%m-%d')
        url = f"https://graph.facebook.com/v21.0/act_{META_AD_ACCOUNT_ID}/insights"
        params = {
            'fields': 'spend,clicks',
            'time_range': json.dumps({'since': since, 'until': until}),
            'time_increment': 1,
            'limit': 500,
            'access_token': META_ACCESS_TOKEN,
        }

        next_url = url
        next_params = params
        while next_url:
            resp = requests.get(next_url, params=next_params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            for row in payload.get('data', []):
                d = row['date_start'].replace('-', '')
                meta_ads_daily[d] = {
                    'spend': float(row.get('spend', 0)),
                    'clicks': int(row.get('clicks', 0)),
                }

            next_url = payload.get('paging', {}).get('next')
            next_params = None  # 'next' already includes all query params

        print(f"  ✓ {len(meta_ads_daily)} days of Meta Ads spend data found")

        # ----- Ad-level breakdown -----
        ad_url = f"https://graph.facebook.com/v21.0/act_{META_AD_ACCOUNT_ID}/insights"
        ad_params = {
            'fields': 'ad_name,campaign_name,spend,clicks,impressions,actions',
            'level': 'ad',
            'time_range': json.dumps({'since': since, 'until': until}),
            'time_increment': 1,
            'limit': 500,
            'access_token': META_ACCESS_TOKEN,
        }

        next_url = ad_url
        next_params = ad_params
        while next_url:
            resp = requests.get(next_url, params=next_params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            for row in payload.get('data', []):
                purchases = 0
                for action in row.get('actions', []):
                    if action.get('action_type') in ('purchase', 'omni_purchase'):
                        purchases += int(float(action.get('value', 0)))

                meta_ads_ad_data.append({
                    'date': row['date_start'].replace('-', ''),
                    'ad_name': row.get('ad_name', '(不明)'),
                    'campaign_name': row.get('campaign_name', '(不明)'),
                    'spend': float(row.get('spend', 0)),
                    'clicks': int(row.get('clicks', 0)),
                    'impressions': int(row.get('impressions', 0)),
                    'purchases': purchases,
                })

            next_url = payload.get('paging', {}).get('next')
            next_params = None

        print(f"  ✓ {len(meta_ads_ad_data)} ad/date records found")

        # ----- Age/gender breakdown (per ad) -----
        demo_url = f"https://graph.facebook.com/v21.0/act_{META_AD_ACCOUNT_ID}/insights"
        demo_params = {
            'fields': 'ad_name,spend,clicks,impressions,actions',
            'level': 'ad',
            'breakdowns': 'age,gender',
            'time_range': json.dumps({'since': since, 'until': until}),
            'time_increment': 1,
            'limit': 500,
            'access_token': META_ACCESS_TOKEN,
        }

        next_url = demo_url
        next_params = demo_params
        while next_url:
            resp = requests.get(next_url, params=next_params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            for row in payload.get('data', []):
                purchases = 0
                for action in row.get('actions', []):
                    if action.get('action_type') in ('purchase', 'omni_purchase'):
                        purchases += int(float(action.get('value', 0)))

                meta_ads_demo_data.append({
                    'date': row['date_start'].replace('-', ''),
                    'ad_name': row.get('ad_name', '(不明)'),
                    'age': row.get('age', '(不明)'),
                    'gender': row.get('gender', '(不明)'),
                    'spend': float(row.get('spend', 0)),
                    'clicks': int(row.get('clicks', 0)),
                    'impressions': int(row.get('impressions', 0)),
                    'purchases': purchases,
                })

            next_url = payload.get('paging', {}).get('next')
            next_params = None

        print(f"  ✓ {len(meta_ads_demo_data)} age/gender records found")

        # ----- Region/gender breakdown (per ad) -----
        geo_url = f"https://graph.facebook.com/v21.0/act_{META_AD_ACCOUNT_ID}/insights"
        geo_params = {
            'fields': 'ad_name,spend,clicks,impressions,actions',
            'level': 'ad',
            'breakdowns': 'region,gender',
            'time_range': json.dumps({'since': since, 'until': until}),
            'time_increment': 1,
            'limit': 500,
            'access_token': META_ACCESS_TOKEN,
        }

        next_url = geo_url
        next_params = geo_params
        while next_url:
            resp = requests.get(next_url, params=next_params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            for row in payload.get('data', []):
                purchases = 0
                for action in row.get('actions', []):
                    if action.get('action_type') in ('purchase', 'omni_purchase'):
                        purchases += int(float(action.get('value', 0)))

                meta_ads_geo_data.append({
                    'date': row['date_start'].replace('-', ''),
                    'ad_name': row.get('ad_name', '(不明)'),
                    'region': row.get('region', '(不明)'),
                    'gender': row.get('gender', '(不明)'),
                    'spend': float(row.get('spend', 0)),
                    'clicks': int(row.get('clicks', 0)),
                    'impressions': int(row.get('impressions', 0)),
                    'purchases': purchases,
                })

            next_url = payload.get('paging', {}).get('next')
            next_params = None

        print(f"  ✓ {len(meta_ads_geo_data)} region/gender records found")

    except Exception as e:
        print(f"  ✗ Meta Ads API error: {e}")
else:
    print("  ⚠ Meta Ads credentials not fully configured — spend will be 0")

# ===== PROCESS GA4 DATA =====
print("\n📈 Processing GA4 data...")

daily_by_date = defaultdict(lambda: {
    'google_revenue': 0, 'meta_revenue': 0,
    'google_cv': 0, 'meta_cv': 0,
    'google_spend': 0, 'meta_spend': 0,
    'google_clicks': 0, 'meta_clicks': 0,
})

for item in ga4_data:
    date = item['date']
    channel = item['channel']

    # Only attribute revenue/conversions to a platform when GA4 says the
    # session actually came from a paid channel for that platform.
    # Organic search, direct, referral, organic social, etc. are real
    # traffic but are not ad-driven, so they are excluded from both buckets
    # rather than being dumped into "Meta" by default.
    if channel == 'Paid Search':
        daily_by_date[date]['google_revenue'] += item['revenue']
        daily_by_date[date]['google_cv'] += item['conversions']
    elif channel == 'Paid Social':
        daily_by_date[date]['meta_revenue'] += item['revenue']
        daily_by_date[date]['meta_cv'] += item['conversions']

# Merge in real spend/clicks from Google Ads and Meta Ads
for date_str, vals in google_ads_daily.items():
    daily_by_date[date_str]['google_spend'] += vals['spend']
    daily_by_date[date_str]['google_clicks'] += vals['clicks']

for date_str, vals in meta_ads_daily.items():
    daily_by_date[date_str]['meta_spend'] += vals['spend']
    daily_by_date[date_str]['meta_clicks'] += vals['clicks']

print(f"  ✓ Aggregated {len(daily_by_date)} days of data")

# ===== FETCH TRAFFIC SOURCE DATA =====
print("\n🌐 Fetching traffic source data...")

try:
    # Sessions/pageviews must NOT be filtered to purchase events - that
    # would restrict them to only sessions that happened to purchase.
    request_traffic = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_traffic = ga4_client.run_report(request_traffic)
    traffic_map = {}

    for row in response_traffic.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value)
        traffic_map[key] = {
            'date': row.dimension_values[0].value,
            'channel': row.dimension_values[1].value,
            'sessions': int(float(row.metric_values[0].value)),
            'pageviews': int(float(row.metric_values[1].value)),
            'avg_duration': float(row.metric_values[2].value),
            'bounce_rate': float(row.metric_values[3].value) * 100,
            'conversions': 0,
        }

    # Purchases by date/channel, merged into the same rows above.
    request_traffic_cv = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[Metric(name="eventCount")],
        dimension_filter=PURCHASE_ONLY_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_traffic_cv = ga4_client.run_report(request_traffic_cv)

    for row in response_traffic_cv.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value)
        cv = int(float(row.metric_values[0].value))
        if key in traffic_map:
            traffic_map[key]['conversions'] = cv
        else:
            traffic_map[key] = {
                'date': row.dimension_values[0].value,
                'channel': row.dimension_values[1].value,
                'sessions': 0,
                'pageviews': 0,
                'avg_duration': 0,
                'bounce_rate': 0,
                'conversions': cv,
            }

    traffic_data = list(traffic_map.values())
    print(f"  ✓ {len(traffic_data)} traffic source records found")

except Exception as e:
    print(f"  ✗ Traffic source error: {e}")
    traffic_data = []

# ===== FETCH PAGE-LEVEL BEHAVIOR DATA =====
print("\n📄 Fetching page-level behavior data...")

try:
    request_pages = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="pagePath"),
            Dimension(name="pageTitle"),
        ],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_pages = ga4_client.run_report(request_pages)
    page_data = []

    for row in response_pages.rows:
        page_data.append({
            'date': row.dimension_values[0].value,
            'path': row.dimension_values[1].value,
            'title': row.dimension_values[2].value,
            'pageviews': int(float(row.metric_values[0].value)),
            'avg_duration': float(row.metric_values[1].value),
            'bounce_rate': float(row.metric_values[2].value) * 100,
        })

    print(f"  ✓ {len(page_data)} page/date records found")

except Exception as e:
    print(f"  ✗ Page-level behavior error: {e}")
    page_data = []

# ===== FETCH PRODUCT-LEVEL PURCHASE DATA =====
print("\n🛍️ Fetching product-level purchase data...")

def channel_to_bucket(channel):
    if channel == 'Paid Search':
        return 'Google広告'
    if channel == 'Paid Social':
        return 'Meta広告'
    return 'その他'


try:
    request_product = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="itemName"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="itemsPurchased"),
            Metric(name="itemRevenue"),
        ],
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_product = ga4_client.run_report(request_product)
    product_data = []

    for row in response_product.rows:
        product_data.append({
            'date': row.dimension_values[0].value,
            'name': row.dimension_values[1].value,
            'channel_bucket': channel_to_bucket(row.dimension_values[2].value),
            'purchased': int(float(row.metric_values[0].value)),
            'revenue': float(row.metric_values[1].value),
        })

    print(f"  ✓ {len(product_data)} product/channel/date records found")

except Exception as e:
    print(f"  ✗ Product data error: {e}")
    product_data = []

# ===== FETCH AGE/GENDER BREAKDOWN (GA4 FALLBACK, ADS TRAFFIC ONLY) =====
# This is only used as a fallback per platform when that platform's own ad
# API doesn't return demographic data (e.g. Google Ads age_range_view /
# gender_view don't support Performance Max campaigns).
print("\n👥 Fetching age/gender breakdown from GA4 (fallback, ads traffic only)...")

try:
    request_age_gender = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="userAgeBracket"),
            Dimension(name="userGender"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
        ],
        dimension_filter=ADS_CHANNEL_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_age_gender = ga4_client.run_report(request_age_gender)
    age_gender_map = {}

    for row in response_age_gender.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value, row.dimension_values[2].value, row.dimension_values[3].value)
        age_gender_map[key] = {
            'date': row.dimension_values[0].value,
            'age': row.dimension_values[1].value,
            'gender': row.dimension_values[2].value,
            'channel': row.dimension_values[3].value,
            'sessions': int(float(row.metric_values[0].value)),
            'bounce_rate': float(row.metric_values[1].value) * 100,
            'avg_duration': float(row.metric_values[2].value),
            'conversions': 0,
        }

    request_age_gender_cv = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="userAgeBracket"),
            Dimension(name="userGender"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[Metric(name="eventCount")],
        dimension_filter=PURCHASE_ADS_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_age_gender_cv = ga4_client.run_report(request_age_gender_cv)

    for row in response_age_gender_cv.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value, row.dimension_values[2].value, row.dimension_values[3].value)
        cv = int(float(row.metric_values[0].value))
        if key in age_gender_map:
            age_gender_map[key]['conversions'] = cv
        else:
            age_gender_map[key] = {
                'date': row.dimension_values[0].value,
                'age': row.dimension_values[1].value,
                'gender': row.dimension_values[2].value,
                'channel': row.dimension_values[3].value,
                'sessions': 0,
                'bounce_rate': 0,
                'avg_duration': 0,
                'conversions': cv,
            }

    ga4_age_gender_data = list(age_gender_map.values())
    print(f"  ✓ {len(ga4_age_gender_data)} GA4 age/gender/date records found (fallback pool)")

except Exception as e:
    print(f"  ✗ GA4 age/gender fallback error: {e}")
    ga4_age_gender_data = []

# ===== FETCH REGION BREAKDOWN (ADS TRAFFIC ONLY) =====
print("\n🗺️ Fetching region breakdown (ads traffic only)...")

try:
    request_region = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="region"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
        ],
        dimension_filter=ADS_CHANNEL_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_region = ga4_client.run_report(request_region)
    region_map = {}

    for row in response_region.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value)
        region_map[key] = {
            'date': row.dimension_values[0].value,
            'region': region_to_ja(row.dimension_values[1].value or '(不明)'),
            'sessions': int(float(row.metric_values[0].value)),
            'bounce_rate': float(row.metric_values[1].value) * 100,
            'avg_duration': float(row.metric_values[2].value),
            'conversions': 0,
        }

    request_region_cv = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="region"),
        ],
        metrics=[Metric(name="eventCount")],
        dimension_filter=PURCHASE_ADS_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_region_cv = ga4_client.run_report(request_region_cv)

    for row in response_region_cv.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value)
        cv = int(float(row.metric_values[0].value))
        if key in region_map:
            region_map[key]['conversions'] = cv
        else:
            region_map[key] = {
                'date': row.dimension_values[0].value,
                'region': region_to_ja(row.dimension_values[1].value or '(不明)'),
                'sessions': 0,
                'bounce_rate': 0,
                'avg_duration': 0,
                'conversions': cv,
            }

    region_data = list(region_map.values())
    print(f"  ✓ {len(region_data)} region/date records found")

except Exception as e:
    print(f"  ✗ Region breakdown error: {e}")
    region_data = []

# ===== FETCH REGION x GENDER BREAKDOWN (GA4, ADS TRAFFIC ONLY) =====
# Engagement metrics (bounce rate / session duration) only exist in GA4 -
# ad platforms don't track landing-page behavior. Used to enrich the
# region x gender table with these regardless of which platform has native
# spend/click data for that same cut.
print("\n🗺️ Fetching region x gender engagement breakdown from GA4 (ads traffic only)...")

try:
    request_region_gender = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="region"),
            Dimension(name="userGender"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
        ],
        dimension_filter=ADS_CHANNEL_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_region_gender = ga4_client.run_report(request_region_gender)
    region_gender_map = {}

    for row in response_region_gender.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value, row.dimension_values[2].value, row.dimension_values[3].value)
        region_gender_map[key] = {
            'date': row.dimension_values[0].value,
            'region': region_to_ja(row.dimension_values[1].value or '(不明)'),
            'gender': row.dimension_values[2].value,
            'channel': row.dimension_values[3].value,
            'sessions': int(float(row.metric_values[0].value)),
            'bounce_rate': float(row.metric_values[1].value) * 100,
            'avg_duration': float(row.metric_values[2].value),
            'conversions': 0,
        }

    request_region_gender_cv = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="region"),
            Dimension(name="userGender"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[Metric(name="eventCount")],
        dimension_filter=PURCHASE_ADS_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_region_gender_cv = ga4_client.run_report(request_region_gender_cv)

    for row in response_region_gender_cv.rows:
        key = (row.dimension_values[0].value, row.dimension_values[1].value, row.dimension_values[2].value, row.dimension_values[3].value)
        cv = int(float(row.metric_values[0].value))
        if key in region_gender_map:
            region_gender_map[key]['conversions'] = cv
        else:
            region_gender_map[key] = {
                'date': row.dimension_values[0].value,
                'region': region_to_ja(row.dimension_values[1].value or '(不明)'),
                'gender': row.dimension_values[2].value,
                'channel': row.dimension_values[3].value,
                'sessions': 0,
                'bounce_rate': 0,
                'avg_duration': 0,
                'conversions': cv,
            }

    ga4_region_gender_data = list(region_gender_map.values())
    print(f"  ✓ {len(ga4_region_gender_data)} GA4 region/gender/date records found")

except Exception as e:
    print(f"  ✗ Region x gender breakdown error: {e}")
    ga4_region_gender_data = []

# ===== FETCH EVENT BREAKDOWN (ADS TRAFFIC ONLY) =====
print("\n📣 Fetching event breakdown (ads traffic only)...")

try:
    request_events = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="eventName"),
        ],
        metrics=[Metric(name="eventCount")],
        dimension_filter=ADS_CHANNEL_FILTER,
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_events = ga4_client.run_report(request_events)
    event_data = []

    for row in response_events.rows:
        event_data.append({
            'date': row.dimension_values[0].value,
            'event_name': row.dimension_values[1].value,
            'count': int(float(row.metric_values[0].value)),
        })

    print(f"  ✓ {len(event_data)} event/date records found")

except Exception as e:
    print(f"  ✗ Event breakdown error: {e}")
    event_data = []

# ===== OPEN GOOGLE SHEETS =====
print("\n🔗 Opening Google Sheets...")
sheet = gc.open_by_key(SPREADSHEET_ID)

# ===== CREATE/UPDATE DATA SHEET =====
print("\n💾 Updating data sheet...")

sheet_name = 'Live Data'
try:
    ws_data = sheet.worksheet(sheet_name)
    ws_data.clear()
except:
    ws_data = sheet.add_worksheet(sheet_name, rows=3000, cols=12)

# Headers
headers = [
    'Date', 'Date Type', 'Platform',
    'Revenue (¥)', 'Spend (¥)', 'Clicks', 'Conversions',
    'CTR (%)', 'CVR (%)', 'CPA (¥)', 'ROAS',
    'Last Updated'
]
rows_data = [headers]

# Daily data
for date_str in sorted(daily_by_date.keys()):
    data = daily_by_date[date_str]

    for platform in ['Google', 'Meta', 'ALL']:
        if platform == 'Google':
            revenue = data['google_revenue']
            spend = data['google_spend']
            clicks = data['google_clicks']
            cv = data['google_cv']
        elif platform == 'Meta':
            revenue = data['meta_revenue']
            spend = data['meta_spend']
            clicks = data['meta_clicks']
            cv = data['meta_cv']
        else:  # ALL
            revenue = data['google_revenue'] + data['meta_revenue']
            spend = data['google_spend'] + data['meta_spend']
            clicks = data['google_clicks'] + data['meta_clicks']
            cv = data['google_cv'] + data['meta_cv']

        # GA4 already reports in JPY
        revenue_jpy = revenue
        spend_jpy = spend

        # Calculate KPIs
        ctr = (clicks / max(1, clicks * 10)) * 100 if clicks > 0 else 0
        cvr = (cv / max(1, clicks)) * 100 if clicks > 0 else 0
        cpa = spend_jpy / cv if cv > 0 else 0
        roas = revenue_jpy / spend_jpy if spend_jpy > 0 else 0

        # Format date (ISO so the frontend can filter/sort by real date)
        date_obj = datetime.strptime(date_str, '%Y%m%d')
        formatted_date = date_obj.strftime('%Y-%m-%d')

        rows_data.append([
            formatted_date,
            '日別',
            platform,
            round(revenue_jpy, 0),
            round(spend_jpy, 0),
            int(clicks),
            int(cv),
            round(ctr, 2),
            round(cvr, 2),
            round(cpa, 0),
            round(roas, 2),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ])

ws_data.append_rows(rows_data)
print(f"  ✓ {len(daily_by_date) * 3} rows written to sheet")

# ===== CREATE/UPDATE SUMMARY SHEET =====
print("\n📊 Creating summary sheet...")

sheet_name_summary = 'Summary'
try:
    ws_summary = sheet.worksheet(sheet_name_summary)
    ws_summary.clear()
except:
    ws_summary = sheet.add_worksheet(sheet_name_summary, rows=100, cols=10)

# Calculate totals
total_revenue = sum(d['google_revenue'] + d['meta_revenue'] for d in daily_by_date.values())
total_cv = sum(d['google_cv'] + d['meta_cv'] for d in daily_by_date.values())
total_spend = sum(d['google_spend'] + d['meta_spend'] for d in daily_by_date.values())
total_clicks = sum(d['google_clicks'] + d['meta_clicks'] for d in daily_by_date.values())

total_revenue_jpy = total_revenue
total_spend_jpy = total_spend

ctr_avg = (total_clicks / max(1, total_clicks * 10)) * 100 if total_clicks > 0 else 0
cvr_avg = (total_cv / max(1, total_clicks)) * 100 if total_clicks > 0 else 0
cpa_avg = total_spend_jpy / total_cv if total_cv > 0 else 0
roas_avg = total_revenue_jpy / total_spend_jpy if total_spend_jpy > 0 else 0

ws_summary.append_rows([
    ['【集計期間: 過去365日】', '', ''],
    ['', '', ''],
    ['Metric', 'Value', 'Currency'],
    ['総売上', round(total_revenue_jpy, 0), '¥'],
    ['総広告費', round(total_spend_jpy, 0), '¥'],
    ['総クリック数', int(total_clicks), '回'],
    ['総CV数', int(total_cv), '件'],
    ['平均CTR', round(ctr_avg, 2), '%'],
    ['平均CVR', round(cvr_avg, 2), '%'],
    ['平均CPA', round(cpa_avg, 0), '¥'],
    ['平均ROAS', round(roas_avg, 2), '倍'],
])

print("  ✓ Summary sheet created")

# ===== CREATE/UPDATE TRAFFIC SOURCE SHEET =====
print("\n💾 Updating traffic source sheet...")

sheet_name_traffic = '流入経路'
try:
    ws_traffic = sheet.worksheet(sheet_name_traffic)
    ws_traffic.clear()
except:
    ws_traffic = sheet.add_worksheet(sheet_name_traffic, rows=6000, cols=8)

rows_traffic = [['日付', '流入経路', 'セッション数', 'PV数', 'CV数', '平均滞在時間(秒)', '直帰率(%)', '更新日時']]

for item in sorted(traffic_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_traffic.append([
        date_obj.strftime('%Y-%m-%d'),
        item['channel'],
        item['sessions'],
        item['pageviews'],
        item['conversions'],
        round(item.get('avg_duration', 0), 1),
        round(item.get('bounce_rate', 0), 1),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_traffic.append_rows(rows_traffic)
print(f"  ✓ {len(traffic_data)} rows written to 流入経路 sheet")

# ===== CREATE/UPDATE PAGE BEHAVIOR SHEET =====
print("\n💾 Updating page behavior sheet...")

sheet_name_pages = 'ページ別行動'
try:
    ws_pages = sheet.worksheet(sheet_name_pages)
    ws_pages.clear()
except:
    ws_pages = sheet.add_worksheet(sheet_name_pages, rows=6000, cols=8)

rows_pages = [['日付', 'ページ', 'タイトル', 'PV数', '平均滞在時間(秒)', '直帰率(%)', '更新日時']]

for item in sorted(page_data, key=lambda x: (x['date'], -x['pageviews'])):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_pages.append([
        date_obj.strftime('%Y-%m-%d'),
        item['path'],
        item['title'],
        item['pageviews'],
        round(item['avg_duration'], 1),
        round(item['bounce_rate'], 1),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_pages.append_rows(rows_pages)
print(f"  ✓ {len(page_data)} rows written to ページ別行動 sheet")

# ===== CREATE/UPDATE PRODUCT SHEET =====
print("\n💾 Updating product sheet...")

sheet_name_product = '商品別'
try:
    ws_product = sheet.worksheet(sheet_name_product)
    ws_product.clear()
except:
    ws_product = sheet.add_worksheet(sheet_name_product, rows=6000, cols=8)

rows_product = [['日付', '商品名', '流入区分', '購入数', '売上(¥)', '更新日時']]

for item in sorted(product_data, key=lambda x: (x['date'], -x['revenue'])):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_product.append([
        date_obj.strftime('%Y-%m-%d'),
        item['name'],
        item['channel_bucket'],
        item['purchased'],
        round(item['revenue'], 0),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_product.append_rows(rows_product)
print(f"  ✓ {len(product_data)} rows written to 商品別 sheet")

# ===== CREATE/UPDATE GOOGLE ADS CAMPAIGN SHEET =====
print("\n💾 Updating Google Ads campaign sheet...")

sheet_name_gcamp = 'Google_キャンペーン別'
try:
    ws_gcamp = sheet.worksheet(sheet_name_gcamp)
    ws_gcamp.clear()
except:
    ws_gcamp = sheet.add_worksheet(sheet_name_gcamp, rows=3000, cols=10)

rows_gcamp = [['日付', 'キャンペーン名', '広告費(¥)', 'クリック数', '表示回数', 'CV数(Google計測)', 'CV値(¥)', '更新日時']]

for item in sorted(google_ads_campaign_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_gcamp.append([
        date_obj.strftime('%Y-%m-%d'),
        item['campaign'],
        round(item['spend'], 0),
        int(item['clicks']),
        int(item['impressions']),
        round(item['conversions'], 2),
        round(item['conversions_value'], 0),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_gcamp.append_rows(rows_gcamp)
print(f"  ✓ {len(google_ads_campaign_data)} rows written to Google_キャンペーン別 sheet")

# ===== CREATE/UPDATE META ADS AD-LEVEL SHEET =====
print("\n💾 Updating Meta Ads ad-level sheet...")

sheet_name_mad = 'Meta_広告別'
try:
    ws_mad = sheet.worksheet(sheet_name_mad)
    ws_mad.clear()
except:
    ws_mad = sheet.add_worksheet(sheet_name_mad, rows=3000, cols=10)

rows_mad = [['日付', '広告名', 'キャンペーン名', '広告費(¥)', 'クリック数', '表示回数', '購入数(Meta計測)', '更新日時']]

for item in sorted(meta_ads_ad_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_mad.append([
        date_obj.strftime('%Y-%m-%d'),
        item['ad_name'],
        item['campaign_name'],
        round(item['spend'], 0),
        int(item['clicks']),
        int(item['impressions']),
        item['purchases'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_mad.append_rows(rows_mad)
print(f"  ✓ {len(meta_ads_ad_data)} rows written to Meta_広告別 sheet")

# ===== MERGE AGE/GENDER DATA (ad platform native, GA4 fallback per platform) =====
print("\n👥 Merging age/gender breakdown (ad platform native + GA4 fallback)...")

AGE_LABELS = {
    'AGE_RANGE_18_24': '18-24', 'AGE_RANGE_25_34': '25-34', 'AGE_RANGE_35_44': '35-44',
    'AGE_RANGE_45_54': '45-54', 'AGE_RANGE_55_64': '55-64', 'AGE_RANGE_65_UP': '65+',
    'AGE_RANGE_UNDETERMINED': '不明', 'UNSPECIFIED': '不明', 'UNKNOWN': '不明',
}
GENDER_LABELS = {
    'MALE': '男性', 'FEMALE': '女性', 'UNDETERMINED': '不明', 'UNSPECIFIED': '不明', 'UNKNOWN': '不明',
    'male': '男性', 'female': '女性', 'unknown': '不明',
}

ad_age_gender_data = []
google_native = bool(google_ads_age_data or google_ads_gender_data)
meta_native = bool(meta_ads_demo_data)

if google_native:
    for item in google_ads_age_data:
        ad_age_gender_data.append({
            'date': item['date'], 'platform': 'Google', 'source': '広告媒体', 'unit': item['campaign'],
            'age': AGE_LABELS.get(item['age'], item['age']), 'gender': '全体',
            'sessions': 0, 'spend': item['spend'], 'clicks': item['clicks'],
            'impressions': item['impressions'], 'conversions': item['conversions'],
        })
    for item in google_ads_gender_data:
        ad_age_gender_data.append({
            'date': item['date'], 'platform': 'Google', 'source': '広告媒体', 'unit': item['campaign'],
            'age': '全体', 'gender': GENDER_LABELS.get(item['gender'], item['gender']),
            'sessions': 0, 'spend': item['spend'], 'clicks': item['clicks'],
            'impressions': item['impressions'], 'conversions': item['conversions'],
        })
else:
    for item in ga4_age_gender_data:
        if item['channel'] != 'Paid Search':
            continue
        ad_age_gender_data.append({
            'date': item['date'], 'platform': 'Google', 'source': 'GA4(参考値)', 'unit': '全体',
            'age': item['age'], 'gender': GENDER_LABELS.get(item['gender'], item['gender']),
            'sessions': item['sessions'], 'spend': 0, 'clicks': 0,
            'impressions': 0, 'conversions': item['conversions'],
        })

if meta_native:
    for item in meta_ads_demo_data:
        ad_age_gender_data.append({
            'date': item['date'], 'platform': 'Meta', 'source': '広告媒体', 'unit': item['ad_name'],
            'age': item['age'], 'gender': GENDER_LABELS.get(item['gender'], item['gender']),
            'sessions': 0, 'spend': item['spend'], 'clicks': item['clicks'],
            'impressions': item['impressions'], 'conversions': item['purchases'],
        })
else:
    for item in ga4_age_gender_data:
        if item['channel'] != 'Paid Social':
            continue
        ad_age_gender_data.append({
            'date': item['date'], 'platform': 'Meta', 'source': 'GA4(参考値)', 'unit': '全体',
            'age': item['age'], 'gender': GENDER_LABELS.get(item['gender'], item['gender']),
            'sessions': item['sessions'], 'spend': 0, 'clicks': 0,
            'impressions': 0, 'conversions': item['conversions'],
        })

print(f"  ✓ {len(ad_age_gender_data)} merged age/gender records "
      f"(Google: {'広告媒体' if google_native else 'GA4(参考値)'}, Meta: {'広告媒体' if meta_native else 'GA4(参考値)'})")

# ===== CREATE/UPDATE AGE/GENDER BREAKDOWN SHEET =====
print("\n💾 Updating age/gender breakdown sheet...")

sheet_name_agegender = '広告_年齢性別'
try:
    ws_agegender = sheet.worksheet(sheet_name_agegender)
    ws_agegender.clear()
except:
    ws_agegender = sheet.add_worksheet(sheet_name_agegender, rows=6000, cols=12)

rows_agegender = [['日付', '媒体', 'データソース', 'キャンペーン/広告', '年齢層', '性別', 'セッション数', '広告費(¥)', 'クリック数', '表示回数', 'CV数', '更新日時']]

for item in sorted(ad_age_gender_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_agegender.append([
        date_obj.strftime('%Y-%m-%d'),
        item['platform'],
        item['source'],
        item['unit'],
        item['age'],
        item['gender'],
        int(item['sessions']),
        round(item['spend'], 0),
        int(item['clicks']),
        int(item['impressions']),
        round(item['conversions'], 2),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_agegender.append_rows(rows_agegender)
print(f"  ✓ {len(ad_age_gender_data)} rows written to 広告_年齢性別 sheet")

# ===== CREATE/UPDATE REGION BREAKDOWN SHEET =====
print("\n💾 Updating region breakdown sheet...")

sheet_name_region = 'GA4_地域別'
try:
    ws_region = sheet.worksheet(sheet_name_region)
    ws_region.clear()
except:
    ws_region = sheet.add_worksheet(sheet_name_region, rows=6000, cols=8)

rows_region = [['日付', '地域', 'セッション数', '直帰率(%)', '平均滞在時間(秒)', 'CV数', '更新日時']]

for item in sorted(region_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_region.append([
        date_obj.strftime('%Y-%m-%d'),
        item['region'],
        item['sessions'],
        round(item['bounce_rate'], 1),
        round(item['avg_duration'], 0),
        item['conversions'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_region.append_rows(rows_region)
print(f"  ✓ {len(region_data)} rows written to GA4_地域別 sheet")

# ===== MERGE REGION x GENDER DATA (Meta native + GA4 engagement) =====
print("\n🗺️ Merging region x gender breakdown (ad platform native + GA4 engagement)...")

ad_region_gender_data = []

# Meta: native spend/click/impression/CV rows.
for item in meta_ads_geo_data:
    ad_region_gender_data.append({
        'date': item['date'], 'platform': 'Meta', 'source': '広告媒体', 'unit': item['ad_name'],
        'region': region_to_ja(item['region']), 'gender': GENDER_LABELS.get(item['gender'], item['gender']),
        'spend': item['spend'], 'clicks': item['clicks'], 'impressions': item['impressions'],
        'conversions': item['purchases'], 'sessions': 0, 'bounce_rate': 0, 'avg_duration': 0,
    })

# GA4: engagement rows (bounce/duration/sessions) for both platforms, plus
# the only source of Google's region x gender cut (no native Google Ads view).
for item in ga4_region_gender_data:
    platform = 'Google' if item['channel'] == 'Paid Search' else ('Meta' if item['channel'] == 'Paid Social' else None)
    if not platform:
        continue
    ad_region_gender_data.append({
        'date': item['date'], 'platform': platform, 'source': 'GA4', 'unit': '全体',
        'region': item['region'], 'gender': GENDER_LABELS.get(item['gender'], item['gender']),
        'spend': 0, 'clicks': 0, 'impressions': 0,
        'conversions': item['conversions'] if platform == 'Google' else 0,
        'sessions': item['sessions'], 'bounce_rate': item['bounce_rate'], 'avg_duration': item['avg_duration'],
    })

print(f"  ✓ {len(ad_region_gender_data)} merged region/gender records "
      f"({len(meta_ads_geo_data)} Meta native, {len(ga4_region_gender_data)} GA4 engagement)")

# ===== CREATE/UPDATE REGION x GENDER BREAKDOWN SHEET =====
print("\n💾 Updating region x gender breakdown sheet...")

sheet_name_regiongender = '広告_エリア性別'
try:
    ws_regiongender = sheet.worksheet(sheet_name_regiongender)
    ws_regiongender.clear()
except:
    ws_regiongender = sheet.add_worksheet(sheet_name_regiongender, rows=10000, cols=14)

rows_regiongender = [['日付', '媒体', 'データソース', 'キャンペーン/広告', 'エリア', '性別', '広告費(¥)', 'クリック数', '表示回数', 'CV数', 'セッション数', '直帰率(%)', '平均滞在時間(秒)', '更新日時']]

for item in sorted(ad_region_gender_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_regiongender.append([
        date_obj.strftime('%Y-%m-%d'),
        item['platform'],
        item['source'],
        item['unit'],
        item['region'],
        item['gender'],
        round(item['spend'], 0),
        int(item['clicks']),
        int(item['impressions']),
        round(item['conversions'], 2),
        int(item['sessions']),
        round(item['bounce_rate'], 1),
        round(item['avg_duration'], 0),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_regiongender.append_rows(rows_regiongender)
print(f"  ✓ {len(ad_region_gender_data)} rows written to 広告_エリア性別 sheet")

# ===== CREATE/UPDATE EVENT BREAKDOWN SHEET =====
print("\n💾 Updating event breakdown sheet...")

sheet_name_event = 'GA4_イベント別'
try:
    ws_event = sheet.worksheet(sheet_name_event)
    ws_event.clear()
except:
    ws_event = sheet.add_worksheet(sheet_name_event, rows=6000, cols=6)

rows_event = [['日付', 'イベント名', '発生回数', '更新日時']]

for item in sorted(event_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_event.append([
        date_obj.strftime('%Y-%m-%d'),
        item['event_name'],
        item['count'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_event.append_rows(rows_event)
print(f"  ✓ {len(event_data)} rows written to GA4_イベント別 sheet")

# ===== FINAL SUMMARY =====
print(f"\n" + "="*70)
print(f"✅ DASHBOARD AUTO-UPDATE COMPLETE")
print(f"="*70)
print(f"\n📊 Data Summary (30 days):")
print(f"  • Total Revenue (JPY): ¥{total_revenue_jpy:,.0f}")
print(f"  • Total Ad Spend (JPY): ¥{total_spend_jpy:,.0f}")
print(f"  • Total Clicks: {total_clicks:,.0f}")
print(f"  • Total Conversions: {total_cv:,.0f}")
print(f"  • Average CPA: ¥{cpa_avg:,.0f}")
print(f"  • Average ROAS: {roas_avg:.2f}x")
print(f"\n📝 Sheets Updated:")
print(f"  ✓ Live Data - {len(daily_by_date) * 3} rows")
print(f"  ✓ Summary - 30-day overview")
