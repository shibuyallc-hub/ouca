"""Add campaign-level negative keywords (phrase match) to all Search and Performance Max campaigns.

DRY_RUN=true (default) only prints what would be added.
"""
import os
import sys

from google.ads.googleads.client import GoogleAdsClient

DRY_RUN = os.getenv('DRY_RUN', 'true').lower() != 'false'

# 全て「フレーズ一致」で登録（グリナ〜青魚生活は依頼で明示、他も同じ方針に統一）
NEGATIVE_KEYWORDS = [
    # 競合・他社商品
    'ラフィーネエパゴールド', 'エパゴールド',
    # キレイ・デ・ラボ / ウエルネスラボ系
    'キレイデラボ', 'ウエルネスラボ', 'キレイ デ ラボ', 'ウエルネス ラボ',
    'kireidelab', 'wellnesslab',
    'キレイ・デ・プラセンタ', 'キレイ・デ・ナノプラセンタ', 'キレイ・デ・ナノプラセンタルナ',
    'キレイ・デ・ナノプラセンタLUNA', 'キレイデプラセンタ', 'キレイデナノプラセンタ',
    'キレイデナノプラセンタルナ', 'キレイデナノプラセンタLUNA',
    'キレイデエクオール', 'キレイデゲニステイン', 'キレイ デ エクオール', 'キレイ デ ゲニステイン',
    'ミューズエクオール', 'ミューズプラセンタ', 'ミューズゲニステインN', 'ミューズゲニステイン',
    # ボディア / 美爽煌茶 / リフリーラ ほか
    'HMBプレミアムマッスル ボディア', 'hmbプレミアムマッスル ボディア', 'プレミアムマッスル ボディア',
    'ボディア', 'bodia',
    '美爽煌茶', '美装紅茶', 'びそうこうちゃ',
    'リフリーラ', '塗るプロテオグリカン リフリーラ', '飲むプロテオグリカン リフリーラ',
    'プロテオグリカン青汁 リフリーラ', '飲むルテオリン リフリーラ', '飲むグアーガム リフリーラ',
    'ロダンBB', 'ハーリス', 'モイストパッチ', 'ハーリス モイストパッチ', 'MOIST PATCH',
    'ラップリフト', 'バランシングナノ',
    # グリナ / 味の素 / 青魚生活
    'グリナ', 'ぐりな', 'glyna', 'gurina', 'gulina',
    '味の素', 'あじのもと', 'ajinomoto', '青魚生活',
]

client = GoogleAdsClient.load_from_dict({
    "developer_token": os.environ['GOOGLE_ADS_DEVELOPER_TOKEN'],
    "client_id": os.environ['GOOGLE_ADS_CLIENT_ID'],
    "client_secret": os.environ['GOOGLE_ADS_CLIENT_SECRET'],
    "refresh_token": os.environ['GOOGLE_ADS_REFRESH_TOKEN'],
    "login_customer_id": os.environ['GOOGLE_ADS_CUSTOMER_ID'],
    "use_proto_plus": True,
})
customer_id = os.environ['GOOGLE_ADS_CUSTOMER_ID']
ga = client.get_service("GoogleAdsService")
criterion_svc = client.get_service("CampaignCriterionService")
campaign_svc = client.get_service("CampaignService")

# 入力の重複を除去（大文字小文字は同一扱い。元の表記は保持）
seen, keywords = set(), []
for kw in NEGATIVE_KEYWORDS:
    key = kw.lower()
    if key not in seen:
        seen.add(key)
        keywords.append(kw)
print(f"入力キーワード: {len(NEGATIVE_KEYWORDS)}件 → 重複除去後 {len(keywords)}件 / DRY_RUN={DRY_RUN}")

campaigns = []
for row in ga.search(customer_id=customer_id, query="""
    SELECT campaign.id, campaign.name, campaign.advertising_channel_type, campaign.status
    FROM campaign
    WHERE campaign.status != 'REMOVED'
"""):
    ch = row.campaign.advertising_channel_type.name
    if ch in ('SEARCH', 'PERFORMANCE_MAX'):
        campaigns.append((row.campaign.id, row.campaign.name, ch, row.campaign.status.name))
print("対象キャンペーン:")
for c in campaigns:
    print(f"  - {c[1]} (id={c[0]}, {c[2]}, {c[3]})")
if not campaigns:
    sys.exit("対象キャンペーンが見つかりません")

existing = {}
for row in ga.search(customer_id=customer_id, query="""
    SELECT campaign.id, campaign_criterion.keyword.text, campaign_criterion.keyword.match_type
    FROM campaign_criterion
    WHERE campaign_criterion.type = 'KEYWORD' AND campaign_criterion.negative = TRUE
"""):
    existing.setdefault(row.campaign.id, set()).add(
        (row.campaign_criterion.keyword.text.lower(), row.campaign_criterion.keyword.match_type.name))

total_added = total_skipped = total_failed = 0
for camp_id, camp_name, ch, _ in campaigns:
    have = existing.get(camp_id, set())
    ops, skipped = [], 0
    for kw in keywords:
        if (kw.lower(), 'PHRASE') in have:
            skipped += 1
            continue
        op = client.get_type("CampaignCriterionOperation")
        c = op.create
        c.campaign = campaign_svc.campaign_path(customer_id, camp_id)
        c.negative = True
        c.keyword.text = kw
        c.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
        ops.append(op)
    print(f"\n[{camp_name}] 追加予定 {len(ops)}件 / 既に登録済みでスキップ {skipped}件")
    total_skipped += skipped
    if DRY_RUN or not ops:
        continue
    failed = 0
    for i in range(0, len(ops), 100):
        chunk = ops[i:i + 100]
        request = client.get_type("MutateCampaignCriteriaRequest")
        request.customer_id = customer_id
        request.operations.extend(chunk)
        request.partial_failure = True
        resp = criterion_svc.mutate_campaign_criteria(request=request)
        pf = resp.partial_failure_error
        if pf.code != 0:
            failure_cls = type(client.get_type("GoogleAdsFailure"))
            for detail in pf.details:
                for e in failure_cls.deserialize(detail.value).errors:
                    idx = e.location.field_path_elements[0].index
                    print(f"  ✗ {chunk[idx].create.keyword.text}: {e.error_code} / {e.message}")
                    failed += 1
    added = len(ops) - failed
    print(f"  → 登録成功 {added}件 / 失敗 {failed}件")
    total_added += added
    total_failed += failed

print(f"\n合計: 追加 {total_added}件 / スキップ {total_skipped}件 / 失敗 {total_failed}件")
