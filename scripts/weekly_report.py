#!/usr/bin/env python3
"""
OUCA ROI Dashboard - Weekly Report Generator

Summarizes Mon-Sun weeks vs the week before them and upserts one row per week
into the 週次レポート_アーカイブ sheet.

REPORT_MODE:
  weekly   (default, Monday cron) previous completed week (確定) + current week-to-date (途中経過)
  current  current week-to-date only (run every few hours by the dashboard update)
  backfill every completed week since the first day with data (確定) + current week-to-date

Reads from sheets already populated by auto_update_dashboard.py (Live Data,
Google_キャンペーン別, Meta_広告別) plus a manually/agent-maintained 変更履歴
sheet. Does not call any ad platform API directly.
"""

import json
import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
import gspread
from gspread.utils import rowcol_to_a1

SERVICE_ACCOUNT_JSON_PATH = os.getenv('SERVICE_ACCOUNT_JSON_PATH', 'service_account.json')
SPREADSHEET_ID = '1eQb2soZQkat4jVhcUMyWx6hOCEZC8uOCdQc6UHcm-vM'
MODE = os.getenv('REPORT_MODE', 'weekly').strip().lower()

# Thresholds for rule-based GOOD/BAD detection.
ROAS_GOOD_DELTA = 0.2          # WoW ROAS improvement to call out as GOOD
ROAS_BAD_DELTA = -0.2          # WoW ROAS decline to call out as BAD
CPA_GOOD_RATIO = 0.9           # this week's CPA <= 90% of last week's -> GOOD
CPA_BAD_RATIO = 1.2            # this week's CPA >= 120% of last week's -> BAD
WASTE_MIN_CLICKS = 30
WASTE_MIN_SPEND = 3000

SHEET_NAME_REPORT = '週次レポート_アーカイブ'
# 新しい列は末尾に追加（既存行・既存のフロント表示を壊さない）
HEADERS = [
    '週開始日', '週終了日', '総広告費(¥)', '総売上(¥)', '総CV数', 'ROAS', 'CPA(¥)',
    'Google広告費(¥)', 'Google CV数', 'Meta広告費(¥)', 'Meta CV数',
    'GOOD', 'BAD', '改善ポイント', '運用変更履歴', '生成日時',
    'ステータス', '総表示回数', '総クリック数',
    'Google売上(¥)', 'Google表示回数', 'Googleクリック数',
    'Meta売上(¥)', 'Meta表示回数', 'Metaクリック数',
    'Meta広告別', 'Googleキャンペーン別',
]

with open(SERVICE_ACCOUNT_JSON_PATH) as f:
    service_account_info = json.load(f)

sheets_credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
gc = gspread.authorize(sheets_credentials)
sheet = gc.open_by_key(SPREADSHEET_ID)

print("=" * 70)
print(f"OUCA WEEKLY REPORT GENERATOR (mode={MODE})")
print("=" * 70)


def get_records(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        return ws.get_all_records()
    except Exception as e:
        print(f"  ⚠ Could not read sheet '{sheet_name}': {e}")
        return []


def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date()


def in_week(date_str, start, end):
    try:
        d = parse_date(date_str)
    except (ValueError, TypeError):
        return False
    return start <= d <= end


def num(v):
    try:
        return float(v or 0)
    except (ValueError, TypeError):
        return 0.0


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


def aggregate_live(rows, start, end, platform):
    spend = revenue = clicks = cv = 0
    for row in rows:
        if row.get('Platform') != platform:
            continue
        if not in_week(str(row.get('Date', '')), start, end):
            continue
        spend += num(row.get('Spend (¥)'))
        revenue += num(row.get('Revenue (¥)'))
        clicks += num(row.get('Clicks'))
        cv += num(row.get('Conversions'))
    cpa = spend / cv if cv > 0 else 0
    roas = revenue / spend if spend > 0 else 0
    return {'spend': spend, 'revenue': revenue, 'clicks': clicks, 'cv': cv, 'cpa': cpa, 'roas': roas}


def sum_field(rows, field, start, end):
    return sum(num(r.get(field)) for r in rows if in_week(str(r.get('日付', '')), start, end))


def breakdown(rows, name_field, spend_f, clicks_f, impr_f, cv_f, cv_label, start, end):
    """広告（キャンペーン）別の1行テキスト一覧。広告費の多い順。"""
    agg = {}
    for r in rows:
        if not in_week(str(r.get('日付', '')), start, end):
            continue
        name = r.get(name_field) or '(不明)'
        v = agg.setdefault(name, {'spend': 0, 'clicks': 0, 'impr': 0, 'cv': 0})
        v['spend'] += num(r.get(spend_f))
        v['clicks'] += num(r.get(clicks_f))
        v['impr'] += num(r.get(impr_f))
        v['cv'] += num(r.get(cv_f))
    lines = []
    for name, v in sorted(agg.items(), key=lambda x: -x[1]['spend']):
        ctr = v['clicks'] / v['impr'] * 100 if v['impr'] else 0
        cpc = v['spend'] / v['clicks'] if v['clicks'] else 0
        lines.append(f"{name}: 広告費¥{v['spend']:,.0f} / 表示{v['impr']:,.0f} / クリック{v['clicks']:,.0f} / "
                     f"CTR{ctr:.2f}% / CPC¥{cpc:,.0f} / {cv_label}{v['cv']:,.0f}")
    return lines


def find_wasted(rows, name_field, spend_field, clicks_field, cv_field, start, end):
    agg = {}
    for row in rows:
        if not in_week(str(row.get('日付', '')), start, end):
            continue
        name = row.get(name_field, '(不明)')
        if name not in agg:
            agg[name] = {'spend': 0, 'clicks': 0, 'cv': 0}
        agg[name]['spend'] += num(row.get(spend_field))
        agg[name]['clicks'] += num(row.get(clicks_field))
        agg[name]['cv'] += num(row.get(cv_field))

    wasted = []
    for name, v in agg.items():
        if v['clicks'] >= WASTE_MIN_CLICKS and v['spend'] >= WASTE_MIN_SPEND and v['cv'] == 0:
            wasted.append((name, v['spend'], v['clicks']))
    return wasted


def build_row(start, end, status):
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    label = f"{start} 〜 {end}（{status}）"
    print(f"\n📅 {label}  /  比較週: {prev_start} 〜 {prev_end}")

    this_all = aggregate_live(live_data, start, end, 'ALL')
    prev_all = aggregate_live(live_data, prev_start, prev_end, 'ALL')
    this_google = aggregate_live(live_data, start, end, 'Google')
    this_meta = aggregate_live(live_data, start, end, 'Meta')

    google_impr = sum_field(google_campaign_data, '表示回数', start, end)
    meta_impr = sum_field(meta_ad_data, '表示回数', start, end)

    print(f"📊 今週(ALL): spend=¥{this_all['spend']:.0f} revenue=¥{this_all['revenue']:.0f} "
          f"cv={this_all['cv']:.0f} roas={this_all['roas']:.2f} cpa=¥{this_all['cpa']:.0f}")
    print(f"📊 Meta: spend=¥{this_meta['spend']:.0f} impr={meta_impr:.0f} clicks={this_meta['clicks']:.0f} cv={this_meta['cv']:.0f}")

    wasted_google = find_wasted(google_campaign_data, 'キャンペーン名', '広告費(¥)', 'クリック数', 'CV数(Google計測)', start, end)
    wasted_meta = find_wasted(meta_ad_data, '広告名', '広告費(¥)', 'クリック数', '購入数(Meta計測)', start, end)

    good, bad, improve = [], [], []

    # データ欠落の検知（Meta APIトークン切れ等で取得できていない場合に気づけるように）
    if this_meta['spend'] == 0 and not meta_ad_data:
        bad.append("Meta広告のデータが取得できていません（Meta_広告別が空です）。API連携（アクセストークン）を確認してください。")
        improve.append("Meta Ads APIのアクセストークンの期限切れ・権限を確認し、更新してください。")

    if this_all['spend'] > 0:
        if this_all['roas'] >= 1:
            good.append(f"広告費に対して黒字（ROAS {this_all['roas']:.2f}倍）を達成しています。")
        else:
            bad.append(f"広告費に対して赤字（ROAS {this_all['roas']:.2f}倍）です。")
            improve.append("クリエイティブやランディングページの訴求内容の見直しを検討してください。")

    if status == '確定' and (prev_all['roas'] > 0 or this_all['roas'] > 0):
        roas_delta = this_all['roas'] - prev_all['roas']
        if roas_delta >= ROAS_GOOD_DELTA:
            good.append(f"ROASが前週比+{roas_delta:.2f}pt改善しました（{prev_all['roas']:.2f}倍→{this_all['roas']:.2f}倍）。")
        elif roas_delta <= ROAS_BAD_DELTA:
            bad.append(f"ROASが前週比{roas_delta:.2f}pt悪化しました（{prev_all['roas']:.2f}倍→{this_all['roas']:.2f}倍）。")

    if status == '確定' and prev_all['cpa'] > 0 and this_all['cpa'] > 0:
        if this_all['cpa'] <= prev_all['cpa'] * CPA_GOOD_RATIO:
            good.append(f"CPAが改善しました（前週¥{prev_all['cpa']:.0f}→今週¥{this_all['cpa']:.0f}）。")
        elif this_all['cpa'] >= prev_all['cpa'] * CPA_BAD_RATIO:
            bad.append(f"CPAが悪化しました（前週¥{prev_all['cpa']:.0f}→今週¥{this_all['cpa']:.0f}）。")
            improve.append("入札戦略・ターゲティングの見直しを検討してください。")

    if status == '確定':
        if this_all['cv'] > prev_all['cv']:
            good.append(f"CV数が前週の{prev_all['cv']:.0f}件から{this_all['cv']:.0f}件に増加しました。")
        elif this_all['spend'] > 0 and this_all['cv'] == 0:
            bad.append("今週はCV（購入）が0件でした。")
            improve.append("配信ボリュームを維持しつつ、コンバージョン導線（LP・カート離脱率など）を確認してください。")
    elif this_all['spend'] > 0 and this_all['cv'] == 0:
        bad.append("ここまでのCV（購入）は0件です（途中経過）。")

    for name, spend, clicks in wasted_google:
        bad.append(f"Google広告「{name}」はクリック{clicks:.0f}件・広告費¥{spend:.0f}に対してCVが0件です。")
        improve.append(f"Google広告「{name}」は配信停止または除外設定の見直しを検討してください。")

    for name, spend, clicks in wasted_meta:
        bad.append(f"Meta広告「{name}」はクリック{clicks:.0f}件・広告費¥{spend:.0f}に対して購入が0件です。")
        improve.append(f"Meta広告「{name}」はクリエイティブの差し替えや配信停止を検討してください。")

    if not good:
        good.append("目立った改善点は検出されませんでした。")
    if not bad:
        bad.append("目立った問題点は検出されませんでした。")
    if not improve:
        improve.append("現状の運用を継続してください。")

    changes = []
    for r in change_log:
        if in_week(str(r.get('日付', '')), start, end):
            changes.append(f"[{r.get('カテゴリ', '')}] {r.get('内容', '')}")
    if not changes:
        changes.append("この期間の運用変更の記録はありません。")

    meta_lines = breakdown(meta_ad_data, '広告名', '広告費(¥)', 'クリック数', '表示回数', '購入数(Meta計測)', '購入', start, end)
    google_lines = breakdown(google_campaign_data, 'キャンペーン名', '広告費(¥)', 'クリック数', '表示回数', 'CV数(Google計測)', 'CV', start, end)

    # Joined with a fullwidth pipe rather than a real newline: the dashboard's CSV
    # parser splits on '\n' before doing quote-aware parsing.
    row = {
        '週開始日': start.strftime('%Y-%m-%d'),
        '週終了日': end.strftime('%Y-%m-%d'),
        '総広告費(¥)': round(this_all['spend'], 0),
        '総売上(¥)': round(this_all['revenue'], 0),
        '総CV数': round(this_all['cv'], 0),
        'ROAS': round(this_all['roas'], 2),
        'CPA(¥)': round(this_all['cpa'], 0),
        'Google広告費(¥)': round(this_google['spend'], 0),
        'Google CV数': round(this_google['cv'], 0),
        'Meta広告費(¥)': round(this_meta['spend'], 0),
        'Meta CV数': round(this_meta['cv'], 0),
        'GOOD': ' ｜ '.join(good),
        'BAD': ' ｜ '.join(bad),
        '改善ポイント': ' ｜ '.join(improve),
        '運用変更履歴': ' ｜ '.join(changes),
        '生成日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ステータス': status,
        '総表示回数': round(google_impr + meta_impr, 0),
        '総クリック数': round(this_all['clicks'], 0),
        'Google売上(¥)': round(this_google['revenue'], 0),
        'Google表示回数': round(google_impr, 0),
        'Googleクリック数': round(this_google['clicks'], 0),
        'Meta売上(¥)': round(this_meta['revenue'], 0),
        'Meta表示回数': round(meta_impr, 0),
        'Metaクリック数': round(this_meta['clicks'], 0),
        'Meta広告別': ' ｜ '.join(meta_lines),
        'Googleキャンペーン別': ' ｜ '.join(google_lines),
    }
    return row


# ===== DETERMINE TARGET WEEKS =====
today = datetime.now().date()
this_week_start = today - timedelta(days=today.weekday())
last_week_end = this_week_start - timedelta(days=1)
last_week_start = last_week_end - timedelta(days=6)

targets = []  # (start, end, status)
if MODE == 'backfill':
    dates = []
    for r in live_data:
        try:
            dates.append(parse_date(str(r.get('Date', ''))))
        except (ValueError, TypeError):
            pass
    first = min(dates) if dates else last_week_start
    s = first - timedelta(days=first.weekday())
    while s <= last_week_start:
        targets.append((s, s + timedelta(days=6), '確定'))
        s += timedelta(days=7)
    targets.append((this_week_start, today, '途中経過'))
elif MODE == 'current':
    targets.append((this_week_start, today, '途中経過'))
else:
    targets.append((last_week_start, last_week_end, '確定'))
    targets.append((this_week_start, today, '途中経過'))

rows = [build_row(s, e, st) for s, e, st in targets]


# ===== WRITE TO ARCHIVE SHEET =====
print("\n💾 Writing to 週次レポート_アーカイブ sheet...")
end_a1 = rowcol_to_a1(1, len(HEADERS)).rstrip('1')

try:
    ws_report = sheet.worksheet(SHEET_NAME_REPORT)
except Exception:
    ws_report = sheet.add_worksheet(SHEET_NAME_REPORT, rows=1000, cols=len(HEADERS))

if ws_report.col_count < len(HEADERS):
    ws_report.resize(cols=len(HEADERS))
existing = ws_report.get_all_values()
if not existing or existing[0][:len(HEADERS)] != HEADERS:
    ws_report.update(values=[HEADERS], range_name=f'A1:{end_a1}1')
    print("  ✓ ヘッダーを更新しました")
    existing = ws_report.get_all_values()

start_to_index = {r[0]: i + 1 for i, r in enumerate(existing) if i > 0 and r}
meta_idx = HEADERS.index('Meta広告費(¥)')

for row in rows:
    values = [row[h] for h in HEADERS]
    key = row['週開始日']
    if key in start_to_index:
        idx = start_to_index[key]
        old = existing[idx - 1]
        old_meta = num(old[meta_idx]) if len(old) > meta_idx else 0
        # 確定済みの過去週のMeta数値を、取得失敗による0で上書きしない
        if row['ステータス'] == '確定' and row['Meta広告費(¥)'] == 0 and old_meta > 0:
            print(f"  ⚠ {key}: 既存のMeta広告費¥{old_meta:.0f}を保護するため更新をスキップ（今回のMetaデータが0）")
            continue
        ws_report.update(values=[values], range_name=f'A{idx}:{end_a1}{idx}')
        print(f"  ✓ Updated {key}（{row['ステータス']}）")
    else:
        ws_report.append_row(values)
        existing.append(values)
        start_to_index[key] = len(existing)
        print(f"  ✓ Appended {key}（{row['ステータス']}）")

print("\n" + "=" * 70)
print("✅ WEEKLY REPORT COMPLETE")
print("=" * 70)
