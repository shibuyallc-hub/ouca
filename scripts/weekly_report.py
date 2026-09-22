#!/usr/bin/env python3
"""
OUCA ROI Dashboard - Weekly Report Generator
Runs once a week (Monday), summarizes the previous Mon-Sun week vs the
week before it, and appends one row to the 週次レポート_アーカイブ sheet.

Reads from sheets already populated by auto_update_dashboard.py (Live Data,
Google_キャンペーン別, Meta_広告別) plus a manually/agent-maintained 変更履歴
sheet. Does not call any ad platform API directly.
"""

import json
import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
import gspread

SERVICE_ACCOUNT_JSON_PATH = os.getenv('SERVICE_ACCOUNT_JSON_PATH', 'service_account.json')
SPREADSHEET_ID = '1eQb2soZQkat4jVhcUMyWx6hOCEZC8uOCdQc6UHcm-vM'

# Thresholds for rule-based GOOD/BAD detection.
ROAS_GOOD_DELTA = 0.2          # WoW ROAS improvement to call out as GOOD
ROAS_BAD_DELTA = -0.2          # WoW ROAS decline to call out as BAD
CPA_GOOD_RATIO = 0.9           # this week's CPA <= 90% of last week's -> GOOD
CPA_BAD_RATIO = 1.2            # this week's CPA >= 120% of last week's -> BAD
WASTE_MIN_CLICKS = 30
WASTE_MIN_SPEND = 3000

with open(SERVICE_ACCOUNT_JSON_PATH) as f:
    service_account_info = json.load(f)

sheets_credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
gc = gspread.authorize(sheets_credentials)
sheet = gc.open_by_key(SPREADSHEET_ID)

print("=" * 70)
print("OUCA WEEKLY REPORT GENERATOR")
print("=" * 70)


def get_records(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        return ws.get_all_records()
    except Exception as e:
        print(f"  ⚠ Could not read sheet '{sheet_name}': {e}")
        return []


def week_bounds(reference_date):
    """Mon-Sun week containing reference_date, as (start, end) date objects."""
    start = reference_date - timedelta(days=reference_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date()


# ===== DETERMINE REPORT WEEK (the most recently completed Mon-Sun week) =====
today = datetime.now().date()
this_week_start, _ = week_bounds(today)
report_end = this_week_start - timedelta(days=1)          # last Sunday
report_start = report_end - timedelta(days=6)              # the Monday before that
prev_end = report_start - timedelta(days=1)
prev_start = prev_end - timedelta(days=6)

print(f"\n📅 Report week: {report_start} 〜 {report_end}")
print(f"📅 Comparison week: {prev_start} 〜 {prev_end}")


# ===== LOAD DATA =====
print("\n📥 Loading source sheets...")
live_data = get_records('Live Data')
google_campaign_data = get_records('Google_キャンペーン別')
meta_ad_data = get_records('Meta_広告別')

try:
    ws_changelog = sheet.worksheet('変更履歴')
except Exception:
    ws_changelog = sheet.add_worksheet('変更履歴', rows=1000, cols=6)
    ws_changelog.append_row(['日付', 'カテゴリ', '内容', '記録者'])
    print("  ✓ Created 変更履歴 sheet (was missing)")
change_log = ws_changelog.get_all_records()
print(f"  ✓ Live Data: {len(live_data)} rows, Google_キャンペーン別: {len(google_campaign_data)} rows, "
      f"Meta_広告別: {len(meta_ad_data)} rows, 変更履歴: {len(change_log)} rows")


def in_week(date_str, start, end):
    try:
        d = parse_date(date_str)
    except (ValueError, TypeError):
        return False
    return start <= d <= end


def aggregate_live(rows, start, end, platform):
    spend = revenue = clicks = cv = 0
    for row in rows:
        if row.get('Platform') != platform:
            continue
        if not in_week(str(row.get('Date', '')), start, end):
            continue
        spend += float(row.get('Spend (¥)') or 0)
        revenue += float(row.get('Revenue (¥)') or 0)
        clicks += float(row.get('Clicks') or 0)
        cv += float(row.get('Conversions') or 0)
    cpa = spend / cv if cv > 0 else 0
    roas = revenue / spend if spend > 0 else 0
    return {'spend': spend, 'revenue': revenue, 'clicks': clicks, 'cv': cv, 'cpa': cpa, 'roas': roas}


this_all = aggregate_live(live_data, report_start, report_end, 'ALL')
prev_all = aggregate_live(live_data, prev_start, prev_end, 'ALL')
this_google = aggregate_live(live_data, report_start, report_end, 'Google')
this_meta = aggregate_live(live_data, report_start, report_end, 'Meta')

print(f"\n📊 This week (ALL): spend=¥{this_all['spend']:.0f} revenue=¥{this_all['revenue']:.0f} "
      f"cv={this_all['cv']:.0f} roas={this_all['roas']:.2f} cpa=¥{this_all['cpa']:.0f}")
print(f"📊 Prev week (ALL): spend=¥{prev_all['spend']:.0f} revenue=¥{prev_all['revenue']:.0f} "
      f"cv={prev_all['cv']:.0f} roas={prev_all['roas']:.2f} cpa=¥{prev_all['cpa']:.0f}")


# ===== WASTE DETECTION (campaigns/ads with spend+clicks but 0 conversions) =====
def find_wasted(rows, name_field, spend_field, clicks_field, cv_field, start, end):
    agg = {}
    for row in rows:
        if not in_week(str(row.get('日付', '')), start, end):
            continue
        name = row.get(name_field, '(不明)')
        if name not in agg:
            agg[name] = {'spend': 0, 'clicks': 0, 'cv': 0}
        agg[name]['spend'] += float(row.get(spend_field) or 0)
        agg[name]['clicks'] += float(row.get(clicks_field) or 0)
        agg[name]['cv'] += float(row.get(cv_field) or 0)

    wasted = []
    for name, v in agg.items():
        if v['clicks'] >= WASTE_MIN_CLICKS and v['spend'] >= WASTE_MIN_SPEND and v['cv'] == 0:
            wasted.append((name, v['spend'], v['clicks']))
    return wasted


wasted_google = find_wasted(google_campaign_data, 'キャンペーン名', '広告費(¥)', 'クリック数', 'CV数(Google計測)', report_start, report_end)
wasted_meta = find_wasted(meta_ad_data, '広告名', '広告費(¥)', 'クリック数', '購入数(Meta計測)', report_start, report_end)

print(f"\n🔍 Wasted spend candidates - Google: {len(wasted_google)}, Meta: {len(wasted_meta)}")


# ===== RULE-BASED GOOD / BAD / IMPROVEMENT POINTS =====
good = []
bad = []
improve = []

if this_all['spend'] > 0:
    if this_all['roas'] >= 1:
        good.append(f"広告費に対して黒字（ROAS {this_all['roas']:.2f}倍）を達成しています。")
    else:
        bad.append(f"広告費に対して赤字（ROAS {this_all['roas']:.2f}倍）です。")
        improve.append("クリエイティブやランディングページの訴求内容の見直しを検討してください。")

if prev_all['roas'] > 0 or this_all['roas'] > 0:
    roas_delta = this_all['roas'] - prev_all['roas']
    if roas_delta >= ROAS_GOOD_DELTA:
        good.append(f"ROASが前週比+{roas_delta:.2f}pt改善しました（{prev_all['roas']:.2f}倍→{this_all['roas']:.2f}倍）。")
    elif roas_delta <= ROAS_BAD_DELTA:
        bad.append(f"ROASが前週比{roas_delta:.2f}pt悪化しました（{prev_all['roas']:.2f}倍→{this_all['roas']:.2f}倍）。")

if prev_all['cpa'] > 0 and this_all['cpa'] > 0:
    if this_all['cpa'] <= prev_all['cpa'] * CPA_GOOD_RATIO:
        good.append(f"CPAが改善しました（前週¥{prev_all['cpa']:.0f}→今週¥{this_all['cpa']:.0f}）。")
    elif this_all['cpa'] >= prev_all['cpa'] * CPA_BAD_RATIO:
        bad.append(f"CPAが悪化しました（前週¥{prev_all['cpa']:.0f}→今週¥{this_all['cpa']:.0f}）。")
        improve.append("入札戦略・ターゲティングの見直しを検討してください。")

if this_all['cv'] > prev_all['cv']:
    good.append(f"CV数が前週の{prev_all['cv']:.0f}件から{this_all['cv']:.0f}件に増加しました。")
elif this_all['spend'] > 0 and this_all['cv'] == 0:
    bad.append("今週はCV（購入）が0件でした。")
    improve.append("配信ボリュームを維持しつつ、コンバージョン導線（LP・カート離脱率など）を確認してください。")

for name, spend, clicks in wasted_google:
    bad.append(f"Google広告「{name}」はクリック{clicks:.0f}件・広告費¥{spend:.0f}に対してCVが0件です。")
    improve.append(f"Google広告「{name}」は配信停止または除外設定の見直しを検討してください。")

for name, spend, clicks in wasted_meta:
    bad.append(f"Meta広告「{name}」はクリック{clicks:.0f}件・広告費¥{spend:.0f}に対して購入が0件です。")
    improve.append(f"Meta広告「{name}」はクリエイティブの差し替えや配信停止を検討してください。")

if not good:
    good.append("今週は目立った改善点は検出されませんでした。")
if not bad:
    bad.append("今週は目立った問題点は検出されませんでした。")
if not improve:
    improve.append("現状の運用を継続してください。")

print(f"\n✅ GOOD ({len(good)}): {good}")
print(f"⚠️ BAD ({len(bad)}): {bad}")
print(f"💡 改善点 ({len(improve)}): {improve}")


# ===== CHANGE LOG WITHIN THIS WEEK =====
changes_this_week = []
for row in change_log:
    if in_week(str(row.get('日付', '')), report_start, report_end):
        category = row.get('カテゴリ', '')
        content = row.get('内容', '')
        changes_this_week.append(f"[{category}] {content}")

if not changes_this_week:
    changes_this_week.append("今週の運用変更の記録はありません。")

print(f"\n📝 運用変更履歴 ({len(changes_this_week)}): {changes_this_week}")


# ===== WRITE TO ARCHIVE SHEET =====
print("\n💾 Writing to 週次レポート_アーカイブ sheet...")

sheet_name_report = '週次レポート_アーカイブ'
try:
    ws_report = sheet.worksheet(sheet_name_report)
except Exception:
    ws_report = sheet.add_worksheet(sheet_name_report, rows=1000, cols=16)
    ws_report.append_row([
        '週開始日', '週終了日', '総広告費(¥)', '総売上(¥)', '総CV数', 'ROAS', 'CPA(¥)',
        'Google広告費(¥)', 'Google CV数', 'Meta広告費(¥)', 'Meta CV数',
        'GOOD', 'BAD', '改善ポイント', '運用変更履歴', '生成日時'
    ])

row = [
    report_start.strftime('%Y-%m-%d'),
    report_end.strftime('%Y-%m-%d'),
    round(this_all['spend'], 0),
    round(this_all['revenue'], 0),
    round(this_all['cv'], 0),
    round(this_all['roas'], 2),
    round(this_all['cpa'], 0),
    round(this_google['spend'], 0),
    round(this_google['cv'], 0),
    round(this_meta['spend'], 0),
    round(this_meta['cv'], 0),
    # Joined with a fullwidth pipe rather than a real newline: the
    # dashboard's CSV parser splits on '\n' before doing quote-aware
    # parsing, so an embedded newline inside a quoted cell would corrupt
    # the whole row.
    ' ｜ '.join(good),
    ' ｜ '.join(bad),
    ' ｜ '.join(improve),
    ' ｜ '.join(changes_this_week),
    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
]

# Avoid duplicate rows if the workflow is re-run for the same week.
existing = ws_report.get_all_values()
existing_starts = [r[0] for r in existing[1:]] if len(existing) > 1 else []
target_start_str = report_start.strftime('%Y-%m-%d')
if target_start_str in existing_starts:
    row_index = existing_starts.index(target_start_str) + 2  # +1 header, +1 1-indexed
    ws_report.update(f'A{row_index}:P{row_index}', [row])
    print(f"  ✓ Updated existing row for week starting {target_start_str}")
else:
    ws_report.append_row(row)
    print(f"  ✓ Appended new row for week starting {target_start_str}")

print("\n" + "=" * 70)
print("✅ WEEKLY REPORT COMPLETE")
print("=" * 70)
