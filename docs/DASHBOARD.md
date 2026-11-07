# OUCA 広告効果ダッシュボード 仕組み説明書

最終更新: 2026-11-07

OUCA supplement（ouca.today / EC-Force）の広告成果を、Google 広告・Meta 広告・GA4・EC の数字から自動で集めて、1枚の画面で見るための仕組みです。

- 画面（GitHub Pages）: https://shibuyallc-hub.github.io/ouca/
- データの置き場（Google スプレッドシート）: `OUCA ROI Dashboard`（ID: `1eQb2soZQkat4jVhcUMyWx6hOCEZC8uOCdQc6UHcm-vM`）
- リポジトリ: https://github.com/shibuyallc-hub/ouca

---

## 1. 全体の流れ

```
 Google 広告 API ─┐
 Meta Marketing API ─┼─→ scripts/auto_update_dashboard.py ─→ Google スプレッドシート ─→ docs/index.html（画面）
 GA4 Data API ───┘        （GitHub Actions・3時間ごと）          （各タブにデータを書く）       （CSVを読んで表示）
                                   │
                                   └→ scripts/weekly_report.py（週次レポート／途中経過をシートに書く）
```

- **画面にはサーバーがありません。** `docs/index.html` が、ブラウザから、スプレッドシートの各タブを CSV として直接読んで描画します（`https://docs.google.com/spreadsheets/d/<ID>/gviz/tq?tqx=out:csv&sheet=<タブ名>`）。
- そのため、**スプレッドシートが「リンクを知っている全員が閲覧可」になっている必要**があります。非公開にすると、画面が空になります。
- 数字を更新するのは、GitHub Actions だけです。人が手でシートを書き換えるのは、`改善メモ`（コメント）と `変更履歴` だけです。

## 2. ファイルの役割

| パス | 役割 |
|---|---|
| `docs/index.html` | **本番の画面**（7タブ）。GitHub Pages がこのファイルを配信します |
| `index.html`（ルート） | 初期版の簡易画面（スプレッドシートを読む処理を持たない）。本番の確認には、`docs/index.html` を使います |
| `scripts/auto_update_dashboard.py` | GA4・Google 広告・Meta からデータを取り、スプレッドシートに書き込む本体 |
| `scripts/weekly_report.py` | シートのデータから、週次レポート（先週との比較・良い点・悪い点）を作る |
| `scripts/add_negative_keywords.py` | Google 広告の除外キーワードを、全キャンペーンに一括登録する（手動実行） |
| `.github/workflows/update-dashboard.yml` | 3時間ごとの自動更新 |
| `.github/workflows/weekly-report.yml` | 毎週月曜の週次レポート |
| `.github/workflows/add-negative-keywords.yml` | 除外キーワードの登録（手動実行・確認用の dry run あり） |

## 3. 自動更新（`update-dashboard.yml`）

- **実行タイミング**: 3時間ごと（UTC 0,3,6,…時 = 日本時間 9,12,15,18,21,0,3,6時）。手動でも実行できます。
- **手動で実行する**:
  ```bash
  gh workflow run update-dashboard.yml --repo shibuyallc-hub/ouca --ref main
  ```
- **中身**: ①`auto_update_dashboard.py` → ②`weekly_report.py`（今週の途中経過のみ）→ ③変更があればコミットして push。
- **取得期間**: 過去365日分を、毎回、取り直します。自動更新される17タブは、**消して全件を書き直す方式**です（差分追記ではありません）。過去の数字が、遅れて確定した分も、自動で直ります。`週次レポート_アーカイブ` だけは、週ごとの1行を、上書き（upsert）します。

### 3.1 必要な Secrets（GitHub の Settings → Secrets and variables → Actions）

| 名前 | 用途 |
|---|---|
| `SERVICE_ACCOUNT_JSON` | スプレッドシートへの書き込み・GA4 の読み取り（サービスアカウントの JSON 全文） |
| `GOOGLE_ADS_DEVELOPER_TOKEN` / `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET` / `GOOGLE_ADS_REFRESH_TOKEN` / `GOOGLE_ADS_CUSTOMER_ID` | Google 広告 API |
| `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` | Meta Marketing API（現在のトークンは**閲覧権限のみ**。広告の作成・編集はできません） |

トークンや JSON は、**リポジトリにコミットしないでください。** ワークフローが、実行中だけ `service_account.json` を作り、終了時に削除します。

### 3.2 データの出どころと数え方（数字がずれたときの確認ポイント）

| 指標 | どこから | 補足 |
|---|---|---|
| 広告費・クリック | Google 広告 API／Meta API | 日別。Google は、アカウント全体の日別 |
| 購入数・売上（`Live Data` など） | **GA4 の `purchase` イベントのみ** | GA4 側で「キーイベント」に何を登録していても、購入だけを数えます |
| 媒体への割り当て | GA4 の流入チャネル | Paid Search → Google、Paid Social → Meta。**自然検索・直接・参照などは、どちらにも入れません** |
| `Google_キャンペーン別` の CV | Google 広告 API（Google が計測した CV） | GA4 の数字とは、一致しないことがあります |
| `Meta_広告別` の購入数 | Meta API | Meta は、同じ購入を `purchase` と `omni_purchase` の両方で返すため、`omni_purchase` を優先して数えます（足すと2倍になるため） |

> **注意**: GA4 の流入チャネルの割り当ては、集計後に、1日ほどかけて変わることがあります。購入の日と、割り当てがずれて見えるときは、翌日に、もう一度見てください。
> **注意**: 動作確認のためのテスト注文も、GA4 の `purchase` に入ります。除外する仕組みは、ありません。

## 4. スプレッドシートのタブ一覧

| タブ名 | 中身 | 主な利用先 |
|---|---|---|
| `Summary` | 過去365日の合計（売上・広告費・クリック・CV・CPA・ROAS） | サマリー |
| `Live Data` | 日別 × 媒体（Google／Meta／ALL）の売上・広告費・クリック・CV・CPA・ROAS | 広告効果 |
| `流入経路` | 日別 × チャネルのセッション・PV・CV・滞在時間・直帰率（GA4） | 流入・PV |
| `ページ別行動` | ページごとの PV・滞在時間・直帰率 | 流入・PV |
| `商品別` | 日別 × 商品の購入数・売上（流入区分つき） | 商品別 |
| `LP別` | 日別 × LP × 流入区分の訪問・PV・購入・エンゲージ | LP別 |
| `LP別_広告費` | LP ごとの広告費・クリック・表示（広告の遷移先 URL から自動で振り分け） | LP別 |
| `着地LP別` | **そのLPに最初に着地した訪問だけ**の訪問数・エンゲージ訪問・時間（LP単体の直帰率は、こちらが正確） | LP別 |
| `Amazonクリック` | LP の Amazon ボタンのクリック数（GA4 イベント `amazon_click`） | LP別 |
| `Google_キャンペーン別` | 日別 × キャンペーンの広告費・クリック・表示・CV・CV値 | 広告効果・詳細分析 |
| `Google_検索キーワード別` | 日別 × キーワード（検索キャンペーン） | 詳細分析 |
| `Google_アセット評価` | 広告文・アセットの Google 評価 | 詳細分析 |
| `Meta_広告別` | 日別 × 広告（クリエイティブ）の広告費・クリック・表示・購入 | 広告効果・詳細分析 |
| `広告_年齢性別` | 年齢・性別ごとの広告費・クリック・CV（媒体のネイティブ値。取れない媒体は GA4 で補う） | 詳細分析 |
| `広告_エリア性別` / `GA4_地域別` | 地域 × 性別・直帰率 | 詳細分析 |
| `GA4_イベント別` | 広告流入のイベント発生数（begin_checkout, purchase など） | 詳細分析 |
| `週次レポート_アーカイブ` | 週ごとの比較レポート（1週 = 1行） | 週次レポート |
| `改善メモ` | **人が書く**メモ（施策の記録） | 週次レポート |
| `変更履歴` | **人（またはエージェント）が書く**変更の記録 | 週次レポート |

### 画面のタブ（`docs/index.html`）

📊 広告効果 / 📈 サマリー / 🌐 流入・PV / 🛍️ 商品別 / 🧭 LP別 / 🔎 詳細分析 / 📅 週次レポート。画面右上の期間（今日・昨日・今週・過去7日・過去30日など）で、すべてのタブを絞り込みます。

## 5. LP の判定ルール（LP別・LP別_広告費）

- **広告の遷移先 URL** が `https://ouca.today/lp?u=<LP名>` の形なら、その `<LP名>`（`lp-supplement` = LP1、`lp-executive` = LP2）に振り分けます。
- `https://ouca.today/shop/...` は「**ショップ**」です。URL から読み取れない広告は「**URL不明**」とし、広告費を黙って他に混ぜません。
- GA4 側は、GTM の `content_group` 変数で、LP なら `LP: lp-xxx`、`/shop` なら「ショップ」を付けています。**計測の開始日は 2026-10-05**（`LP_TRACKING_START`）。それ以前の `(not set)` は「ショップ」にまとめ、以後の `(not set)` は「未分類」にします。
- **直帰率の暫定扱い**: GA4 のエンゲージ集計は、1〜2日遅れます。日本時間の「今日・昨日」は、空欄にして、画面側で直帰率の計算から除外します（空欄の日を 100% と誤表示しないため）。

## 6. 週次レポート（`weekly_report.py`）

- シートの `Live Data` / `Google_キャンペーン別` / `Meta_広告別` を読み、月〜日の週ごとに、前の週と比べた1行を `週次レポート_アーカイブ` に書きます。広告 API は、直接呼びません。
- **モード**（`REPORT_MODE`）: `weekly`（月曜朝に、前週の確定＋今週の途中経過）／`current`（今週の途中経過のみ。3時間ごとの更新から呼ばれる）／`backfill`（全週を作り直す）。
- 良い点・悪い点は、ルールで判定します（ROAS が前週より ±0.2 以上、CPA が前週比 90% 以下／120% 以上、30クリック・3,000円以上でCV 0 の無駄遣い、など）。しきい値は、スクリプト冒頭の定数です。
- 手動実行:
  ```bash
  gh workflow run weekly-report.yml --repo shibuyallc-hub/ouca --ref main -f mode=backfill
  ```

## 7. 除外キーワードの一括登録（`add-negative-keywords.yml`）

- 全検索・P-Max キャンペーンに、キャンペーン単位の除外キーワード（フレーズ一致）を登録します。
- `dry_run=true`（既定）は、確認のみで、登録しません。`false` で本登録です。
- 他社から、除外の依頼が来たときは、`ads-setup` ブランチの運用（次の 8.）のほうを使っています。

## 8. 広告の運用用ワークフロー（`ads-setup` ブランチ）

ダッシュボードとは別に、広告の変更・調査用のワークフローが、`ads-setup` ブランチにあります。`main` には、入っていません。

| ファイル | 役割 |
|---|---|
| `.github/workflows/ads-setup.yml` | `scripts/ads_setup.py` を、`ads_setup/mode.txt` の**モード**で実行する（`ads_setup/` か `scripts/ads_setup.py` への **push で起動**） |
| `ads_setup/mode.txt` | 実行するモード名（**1行だけ**。コメントや改行を足すと `unknown mode` になります） |
| `ads_setup/config.json` | キーワード・広告文・除外キーワード（`NEG` = フレーズ、`NEG_EXACT` = 完全一致、`NEG_BROAD` = 部分一致）の定義 |
| `.github/workflows/meta-inspect.yml` / `meta-build.yml` | Meta の広告文の読み取り／（権限があれば）作成 |

### 8.1 使い方

1. `ads_setup/mode.txt` にモード名を書いて push（例: `neg_all`）。
2. Actions の結果を、ログで確認する: `gh run view <run-id> --repo shibuyallc-hub/ouca --log`
3. **実行後は、必ず `ads_setup/mode.txt` を `verify`（読み取りのみ）に戻して push する**（誤って変更系のモードが、再実行されないようにするため）。

### 8.2 主なモード

| モード | 内容 | 変更の有無 |
|---|---|---|
| `verify` / `inspect` | 現状の確認 | なし（読み取り） |
| `perf_diag` | 成果が出ない原因の診断（検索語句・設定・デバイス・IS・年齢・着地ページ・CV設定・広告強度・品質スコア） | なし（読み取り） |
| `sl_scan` / `pmax_url_src` | サイトリンク・P-Max の飛び先の確認 | なし（読み取り） |
| `neg_all` | `config.json` の `NEG` を全キャンペーンに、フレーズ一致で差分登録 | あり |
| `neg_extra` | `NEG`（フレーズ）・`NEG_EXACT`（完全一致）・`NEG_BROAD`（部分一致）を差分登録 | あり |
| `age65_excl` | 65歳以上をキャンペーン単位で除外 | あり |
| `sl_fix` / `copy_update` | サイトリンク・広告文の旧文言を、新しいものに差し替え | あり |
| `worry_kw` | 腸のお悩み系キーワードを、検索の LP1 広告グループに追加 | あり |

### 8.3 注意（ハマりどころ）

- Google 広告 API の **P-Max「最終URL拡張」をオフにするフィールドは、現行 API にありません**（`campaign.url_expansion_opt_out` は廃止）。代わりに、アセット自動化の `FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION` を `OPTED_OUT` にしています。
- 検索語句のレポートで、`segments.date` は `BETWEEN` で範囲指定が必要です。`campaign.status` などの、絞り込みに使う項目は、SELECT に含める必要があります。
- サイトリンク・コールアウトは、文言を、直接編集できません。**新しいアセットを作り、紐づけを入れ替えます。**
- Meta のトークンは、閲覧のみです。広告文の変更は、広告マネージャで、手動です。

## 9. よくあるトラブル

| 症状 | 確認すること |
|---|---|
| 画面が空・古い | ①Actions の `Auto Update Dashboard` が成功しているか ②スプレッドシートが「リンクを知っている全員が閲覧可」か ③ブラウザのキャッシュ |
| 更新が止まった | Actions の失敗ログ（Secrets の期限切れ、特に `GOOGLE_ADS_REFRESH_TOKEN`・`META_ACCESS_TOKEN`） |
| Meta の購入が、実際の2倍に見える | `omni_purchase` を優先する処理が入っているか（3.2） |
| Google の CV と GA4 の購入が合わない | 数え方が違います（3.2）。EC-Force の注文一覧と、日付・金額で突き合わせる |
| 購入の日付がずれる | GA4 の割り当ての遅れ（1日ほど）。翌日に再確認 |
| 直近の直帰率が 100% や 0% | 暫定値（5.）。2日たてば、確定します |
| 新しいタブを追加したい | `auto_update_dashboard.py` に、`sheet.worksheet(...)` → `clear()` → `append_rows()` の流れで追加し、`docs/index.html` の `fetch(sheetCsvUrl('タブ名'))` と、描画処理を追加する |

## 10. 更新履歴

- 2026-11-07: 初版（仕組み・タブ・ワークフロー・運用上の注意）
