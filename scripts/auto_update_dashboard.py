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
from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
from collections import defaultdict

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
            Metric(name="conversions"),
        ],
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

    except Exception as e:
        print(f"  ✗ Google Ads API error: {e}")
else:
    print("  ⚠ Google Ads credentials not fully configured — spend will be 0")

# ===== FETCH REAL META ADS SPEND/CLICKS =====
print("\n💰 Fetching Meta Ads spend data...")

meta_ads_daily = {}

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
    request_traffic = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="conversions"),
        ],
        date_ranges=[DateRange(start_date="365daysAgo", end_date="today")],
    )
    response_traffic = ga4_client.run_report(request_traffic)
    traffic_data = []

    for row in response_traffic.rows:
        traffic_data.append({
            'date': row.dimension_values[0].value,
            'channel': row.dimension_values[1].value,
            'sessions': int(float(row.metric_values[0].value)),
            'pageviews': int(float(row.metric_values[1].value)),
            'conversions': int(float(row.metric_values[2].value)),
        })

    print(f"  ✓ {len(traffic_data)} traffic source records found")

except Exception as e:
    print(f"  ✗ Traffic source error: {e}")
    traffic_data = []

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

rows_traffic = [['日付', '流入経路', 'セッション数', 'PV数', 'CV数', '更新日時']]

for item in sorted(traffic_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_traffic.append([
        date_obj.strftime('%Y-%m-%d'),
        item['channel'],
        item['sessions'],
        item['pageviews'],
        item['conversions'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ])

ws_traffic.append_rows(rows_traffic)
print(f"  ✓ {len(traffic_data)} rows written to 流入経路 sheet")

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
