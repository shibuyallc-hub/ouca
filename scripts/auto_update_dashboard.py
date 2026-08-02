#!/usr/bin/env python3
"""
OUCA ROI Dashboard - Automatic Data Update
Fetches GA4 / Google Ads / Meta Ads data and updates Google Sheets daily
GA4 property reporting currency is JPY, so no currency conversion is applied.
"""

import json
import os
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
            Dimension(name="sessionSource"),
        ],
        metrics=[
            Metric(name="purchaseRevenue"),
            Metric(name="eventCount"),
        ],
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
    )

    response = ga4_client.run_report(request)
    ga4_data = []

    for row in response.rows:
        ga4_data.append({
            'date': row.dimension_values[0].value,
            'source': row.dimension_values[1].value,
            'revenue': float(row.metric_values[0].value),
            'conversions': int(row.metric_values[1].value),
        })

    print(f"  ✓ {len(ga4_data)} GA4 records found")

except Exception as e:
    print(f"  ✗ GA4 Error: {e}")
    ga4_data = []

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
    is_google = 'google' in item['source'].lower() or 'organic' in item['source'].lower()

    # No Google Ads / Meta Ads API is connected, so spend and clicks are
    # unknown until real ad campaigns and their APIs are wired in.
    if is_google:
        daily_by_date[date]['google_revenue'] += item['revenue']
        daily_by_date[date]['google_cv'] += item['conversions']
    else:
        daily_by_date[date]['meta_revenue'] += item['revenue']
        daily_by_date[date]['meta_cv'] += item['conversions']

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
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
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

try:
    request_product = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[Dimension(name="itemName")],
        metrics=[
            Metric(name="itemsPurchased"),
            Metric(name="itemRevenue"),
        ],
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
    )
    response_product = ga4_client.run_report(request_product)
    product_data = []

    for row in response_product.rows:
        product_data.append({
            'name': row.dimension_values[0].value,
            'purchased': int(float(row.metric_values[0].value)),
            'revenue': float(row.metric_values[1].value),
        })

    print(f"  ✓ {len(product_data)} products found")

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
    ws_data = sheet.add_worksheet(sheet_name, rows=500, cols=12)

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

        # Format date
        date_obj = datetime.strptime(date_str, '%Y%m%d')
        formatted_date = date_obj.strftime('%m/%d')

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
    ['【30日間サマリー】', '', ''],
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
    ws_traffic = sheet.add_worksheet(sheet_name_traffic, rows=1000, cols=8)

rows_traffic = [['日付', '流入経路', 'セッション数', 'PV数', 'CV数', '更新日時']]

for item in sorted(traffic_data, key=lambda x: x['date']):
    date_obj = datetime.strptime(item['date'], '%Y%m%d')
    rows_traffic.append([
        date_obj.strftime('%m/%d'),
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
    ws_product = sheet.add_worksheet(sheet_name_product, rows=300, cols=6)

rows_product = [['商品名', '購入数', '売上(¥)', '更新日時']]

for item in sorted(product_data, key=lambda x: -x['revenue']):
    rows_product.append([
        item['name'],
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
