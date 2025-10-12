# Twitter API 新実装 設計ドキュメント

## 1. 目的
- 旧実装（2025-10-11 時点で削除済みの `oldsrc/` 配下コード）を置き換え、Twitter(X) API を汎用的に扱えるクライアントライブラリを提供する。
- Python プログラムから直接利用可能で、将来的には MCP (Model Context Protocol) からもラップして利用できる構造を目指す。
- 投稿/取得/削除などツイート操作に加え、メディアアップロードやユーザー操作（いいね、フォロー）などへの拡張を見据えた設計とする。

## 2. 非機能要件
- **再利用性**: ライブラリとして単独利用、もしくは CLI/サーバーアプリから import 可能。
- **拡張性**: 新しい API エンドポイント追加が最小限のコード変更で済むモジュール構造。
- **信頼性**: レートリミットや API エラーに強い。明確な例外体系。
- **テスタビリティ**: 依存注入を可能にし、HTTP クライアントのモックが容易。
- **セキュリティ**: 認証情報管理を責務分離し、ハードコードを避ける。
- **可観測性**: ログとメトリクスを適切に出力するフックを提供。

## 3. パッケージ構成 (案)
```
twitter_client/
  __init__.py
  config.py             # 設定と Credential の読み書き責務
  auth.py               # OAuth 1.0a/2.0 フローおよびトークン管理
  clients/
    __init__.py
    tweepy_client.py    # tweepy.Client(v2) + tweepy.API(v1.1) のデュアルラッパー
    rest_client.py      # requests/httpx ベースのフォールバック (必要時)
  exceptions.py         # ドメイン固有例外定義
  rate_limit.py         # レート制限情報のパースとバックオフ戦略
  models.py             # リクエスト/レスポンスの型 (`pydantic` v2 BaseModel)
  services/
    __init__.py
    tweet_service.py    # 投稿・取得・削除・検索などツイート操作
    media_service.py    # メディアアップロード
    user_service.py     # ユーザー操作 (フォロー、プロフィール取得など)
    stream_service.py   # ストリーミング API (将来拡張)
    academic_service.py # Academic 収集向け拡張ポイント
  integrations/
    __init__.py
    mcp_adapter.py      # MCP 用アダプタ (将来実装)

examples/
  post_tweet.py        # Python からの利用例
  fetch_timeline.py

tests/
  unit/
    test_tweet_service.py
    test_auth.py
  integration/
    ...
```

## 4. 核となるクラス設計
### 4.1 ConfigManager (`config.py`)
- 役割: `.env` / 環境変数から設定を読み込み、OAuth フローで取得した資格情報を `.env` に保存。
- インタフェース: `load_credentials()`, `save_credentials()`
- 将来: OS の秘密管理（Keyring 等）にも対応可能な抽象クラス化を検討。

### 4.2 OAuthManager (`auth.py`)
- 役割: OAuth 1.0a 認証フロー、アクセストークン検証、トークン更新。
- API: `ensure_oauth1_token()`, `start_oauth1_flow(callback_handler)`, `refresh_token()`
- `callback_handler` により CLI/GUI/MCP など異なる UX に対応。

### 4.3 TweepyClient (`clients/tweepy_client.py`)
- 役割: ツイート操作は `tweepy.Client` (v2) を利用し、メディアアップロードは `tweepy.API` (v1.1) の `media_upload` フローを利用するデュアルクライアントを提供する。サービス層からは単一インターフェースで扱えるよう共通ラッパーを実装する。
- API: `create_tweet(...)`, `delete_tweet(...)`, `upload_media(file_path, media_category, chunked=True)` などを提供し、内部で v2/v1.1 の適切な呼び出しへ委譲した上で、例外をドメイン例外に変換。
- メディアアップロードは v1.1 の 3 段階（初期化→チャンク追加→最終化/ステータス確認）をサポートし、レスポンスの `processing_info` を監視して完了を待機する。今後 v2 側に正式エンドポイントが追加された場合に差し替え可能な抽象化を維持する。
- レート制限・リトライは `rate_limit.py` に委譲し、必要に応じて指数バックオフを適用。

### 4.4 RestClient (`clients/rest_client.py`)
- 役割: tweepy で未サポートまたは制御しづらいエンドポイント（将来の Ads / Premium / GraphQL 等）に備えた低レベル HTTP 実装。
- 初期リリースでは未実装とし、必要になった段階で `httpx` ベースで提供。
- `send(request: HttpRequest) -> HttpResponse` を標準化し、サービス層がクライアント差し替えできるようにする。

### 4.5 TwitterService (`services/tweet_service.py` 等)
- `TweetService`
  - `create_tweet(text, media_ids=None, in_reply_to=None, visibility=None)`
  - `get_tweet(tweet_id)`
  - `delete_tweet(tweet_id)`
  - `search_recent(query, max_results=10)`
  - 内部で `TweepyClient` を利用し、レスポンスを `Tweet` モデル (`pydantic` BaseModel) に変換。
- `MediaService`
  - `upload_image(path, media_category="tweet_image")`
  - `upload_video(path, media_category="tweet_video")`
  - 内部でサイズ・ MIME を検証し、`TweepyClient` を介した初期化→チャンクアップロード→最終化→処理完了待機を実行。
  - 動画や大容量メディアでは `processing_info` の `state` と `check_after_secs` を用いたポーリングと指数バックオフで完了を待ち、タイムアウト時は `MediaProcessingTimeout` を送出。
- `UserService`
  - `get_authenticated_user()`, `follow_user(user_id)`, `list_followers()`

### 4.6 例外 (`exceptions.py`)
- `TwitterClientError` (基底)
- `AuthenticationError`
- `RateLimitExceeded`
- `ValidationError`
- `ApiResponseError` (status code・エラーメッセージ保持)
- `MediaProcessingTimeout`
- `MediaProcessingFailed`

## 5. フロー概要
1. 利用者は `TwitterClientFactory` (例: `twitter_client.__init__`) でクライアントを生成。
2. `ConfigManager` が認証情報を読み込む。存在しなければ `OAuthManager` がフロー開始。
3. `TweepyClient` が OAuth トークンを利用して API 呼び出しを実行。メディア投稿時は初期化→チャンク送信→最終化→処理待機を内部で制御。
4. レスポンスは `models.py` の型にマッピング。
5. エラー発生時は `RateLimitExceeded` や `AuthenticationError` 等で通知。
6. MCP から利用する場合は `integrations/mcp_adapter.py` が `TweetService` を呼び出し、プロトコル用フォーマットに変換。

## 6. MCP 連携方針
- MCP では操作を「ツール」として export。
- `mcp_adapter.py` で `@tool` デコレータ（仮）を使い、`post_tweet_tool`, `get_tweet_tool` などを定義。
- リクエスト/レスポンスは JSON Schema 化し、バリデーションを `pydantic` で行う。
- 認証情報は MCP ホストから渡せるよう、環境変数またはセッション設定を注入可能に。

## 7. ロギング・メトリクス
- Python の `logging` を使用し、`TwitterClient` レベルで Logger を DI。
- レート制限情報・エラー情報を構造化ログとして出力。
- MCP 統合時はログをホストへ転送できるようハンドラを差し替え可能に。

## 8. テスト戦略
- `pytest` ベース。HTTP 通信は `responses`/`pytest-httpx` でモック。
- OAuth フローはコールバック入力をスタブし、トークン保存の副作用を検証。
- レート制限発生時のリトライロジックをユニットテスト。
- 将来的に VCR 方式で統合テストを追加し、実 API へのアクセスを限定的に確認。

## 9. 今後のロードマップ
1. **フェーズ1**: 新パッケージのスキャフォールド、Config/OAuth/TweepyClient の実装、チャンク型メディアアップロード（画像・動画）の基本機能まで実装。
2. **フェーズ2**: UserService と検索 API の追加、例外とロギング強化。
3. **フェーズ3**: MCP アダプタ PoC。MCP 経由で投稿/取得できる最小機能を実装。
4. **フェーズ4**: ドキュメント、サンプルコード整備。CI/CD で lint/test 自動化。

 ---
- 備考: 旧実装は 2025-10-11 に削除済み。必要に応じて Git 履歴（例: `git show <削除前のコミット>`）で参照すること。
- この設計のレビュー結果に応じてクラス名・モジュール構成は適宜調整する。

## 10. 設計レビュー結果（初回）
- **パッケージ命名**: `twitter_client` で統一。将来公式 SDK と衝突しないか確認するため、PyPI 公開時には `xclient-twitter` など代替名を検討。
- **Config 管理**: 環境変数→`.env` の順で参照し、`.env` への保存も行う二段構成へ整理。`ConfigManager` は `load_credentials(priority=('env', 'dotenv'))` を公開。
- **認証フロー**: OAuth 1.0a は従来通りブラウザリダイレクト、MCP 連携時は `callback_handler` としてコマンドライン／対話 UI／MCP セッション情報を差し替え可能にする。
- **クライアント実装**: tweepy を一次選択とし、`clients/tweepy_client.py` で v2 のツイート操作 (`tweepy.Client`) と v1.1 のメディアアップロード (`tweepy.API.media_upload`) をデュアルクライアント構成で統合管理。細かな制御が必要になった場合に備えて `rest_client.py` を後日追加できるようインタフェースを整備。
- **サービス分割**: `TweetService` と `MediaService` を最優先で実装。`UserService` と検索機能はフェーズ2で追加する。共通 `BaseService` を用意し、エンドポイントパスとレスポンス変換を一元化。
- **例外設計**: API 応答に含まれるエラーコードを `ApiResponseError` の `code` フィールドへ格納。`RateLimitExceeded` にはリセット時刻を保持し、上位で待機ロジックに利用。
- **メディア処理**: 画像・動画とも v1.1 の `media_upload` チャンクアップロードフローを前提にし、`MediaProcessingTimeout` / `MediaProcessingFailed` でユーザー通知と再試行判断を行う。
- **モデル層**: 全て `pydantic` v2 BaseModel で定義し、型検証・シリアライズを統一。MCP 連携向けの JSON Schema も `model.model_json_schema()` から生成する。
- **ロギング**: `logging` module を使用し、`TwitterClient` 初期化時に外部から Logger を渡せるようにする。デフォルトは WARNING レベル。
- **テスト方針**: `pytest` ＋ `pytest-httpx` を採用し、HTTP モックを標準化。OAuth フローのユニットテストでは `callback_handler` をダミー化し、トークン保存を temp ディレクトリで検証。
- **未決事項**: Streaming API への対応有無、v2 エンドポイントのスコープ設定、MCP 側のスキーマ仕様詳細。フェーズ1完了時点で再レビュー。

## 11. 外部ライブラリ比較まとめ
- **tweepy**: 認証～投稿/取得を担う `tweepy.Client` (v2) と、メディアアップロードを担う `tweepy.API.media_upload` (v1.1) を併用する構成で採用。コミュニティと更新頻度が高く、コアクライアントに適する。
- **twarc**: JSON 収集に強く、Academic 目的での全量取得や再水和に最適。バルク収集機能を将来追加する際の拡張候補として保持。
- **TwitterAPI (geduldig)**: 低レベル制御が可能な薄いラッパー。Premium/Ads、細かなリクエストチューニングが必要になった場合に `rest_client.py` の実装参考とする。
- **python-twitter / PyTweet など**: メンテナンス停止または更新頻度低下により採用優先度は低い。特定ユースケースでのみスポット利用を検討。
- **tweetkit / tweetple / 2wttr**: Academic Research 向け機能に特化。必要に応じ `academic_service.py` でアダプタを実装し段階的に統合。
- **twitivity / twitter-stream.py**: Account Activity や v2 ストリーム用。イベント駆動連携が優先された段階で `stream_service.py` と連携させる。

## 12. メディア処理要件
- 画像は `image/jpeg`, `image/png`, `image/webp`, `image/gif` を対象とし、v1.1 メディアアップロード (`media_category=tweet_image`) の 5MB 制限に収まるか事前検証する。
- 動画は `video/mp4` (H.264/AAC) を前提にし、v1.1 の chunked upload API で最大 512MB までのチャンクアップロードと処理完了待機を実装する。
- `MediaService` では MIME 判定・サイズチェック・適切な `media_category` (`tweet_image`, `tweet_gif`, `tweet_video`) の自動設定を行う。
- アップロード後の `processing_info` を監視し、`pending`/`in_progress` の場合は `check_after_secs` に従いポーリング。最大待機時間を超えた場合は `MediaProcessingTimeout` を送出し、ユーザーに再試行を促す。
- 失敗 (`failed`) 時は `error.code` と `message` を含む `MediaProcessingFailed` 例外を用意し、再アップロードや再エンコード判断に活かせるようにする。

### 12.1 手動検証ポリシー（暫定対応）
- v1.1 チャンクアップロードの統合テストは Tweepy 側の内部仕様変更により `responses` モックが破綻しているため、2025-10-11 時点では CI 実行を停止し、実アカウントを用いた手動テストに切り替える。
- 手動テスト手順:
  1. `.env` に有効な `TWITTER_API_*` / OAuth1 トークンを投入し、`ConfigManager` 経由で読み込ませる。
  2. `python examples/post_tweet.py --video <path>` などの実行で動画アップロード→ツイート投稿を確認し、レスポンス内 `processing_info` の状態を記録。
  3. タイムアウト／失敗分岐を確認する場合は意図的に大容量ファイルや壊れた動画を使用し、`MediaProcessingTimeout` / `MediaProcessingFailed` が発生することをログ化。
- 手動検証結果は `docs/manual_test_reports/`（予定）に日付付きで記録し、CI 復帰の方針が固まり次第、テストコードへ反映する。

## 13. 旧実装の参照方法
- 旧来の tweepy ベース実装（`create_tweet.py`, `handlers.py`, `twitter_api_tweepy.py`）は 2025-10-11 時点で削除済み。
- 移行前後の挙動比較が必要な場合は Git 履歴から復元する。`57963d0a1802be367b02958c2e8732d1dfe2ec40` 時点ではプロジェクトルート直下に存在していた。
- 旧実装は v1.1 メディアエンドポイント依存のため、最新 API では動作しない点に注意。

## 14. 今後の実装計画（2025-10-12 時点）
### 14.1 完了済み（Sprint 1）
- `pyproject.toml` の依存整理と `uv` ベース開発フローの確立
- TweepyClient のデュアルクライアント化／MediaService の GIF ルーティング
- `tests/unit/*` と HTTP モック統合テスト（動画系は保留）の整備
- README / CLI サンプルの更新

### 14.2 次スプリント（2025-10-19 ～ 2025-10-31）— MCP アダプタ優先
- **MCP エンドポイント設計**: ツイート投稿、メディアアップロード、認証状態確認のスキーマ定義
- **アダプタ実装**: `twitter_client/integrations/mcp_adapter.py` を新設し、ConfigManager とサービス層を再利用できるよう DI を設計
- **MCP テスト**: モックセッションによるユニットテスト／画像付きツイートまでの統合テスト
- **ドキュメント**: `docs/mcp_integration.md`（新規）でセットアップと利用手順を整理し、README からリンク
- **サポーティングタスク**: MCP で必要なエラーハンドリング追加、レスポンスモデルの JSON Schema 化

### 14.3 後続スプリント候補
- レート制限・バックオフ戦略 (`rate_limit.py`) の実装とサービス層統合
- MCP アダプタ拡張（クエリ API、ツイート削除など）
- `UserService` / `StreamService` などフェーズ 2 機能

### 14.4 バックログ（MCP 完了後に再開）
- 大容量動画（50MB 超）向けストリーミング最適化と CI 向けモック再構築
- チャンク動画アップロード統合テストの再有効化
- CI/CD パイプライン（lint, coverage, メトリクス連携）

### 14.5 進行状況チェックリスト（2025-10-12 現在）
- [x] デュアルクライアントとメディアサービスの安定化
- [x] README をユーザー向けガイドに再構成
- [ ] MCP エンドポイント仕様書を確定する
- [ ] MCP アダプタのスケルトンを実装する
- [ ] MCP 統合テスト（テキスト + 画像）を追加する
- [ ] MCP ドキュメントを公開し README からリンクする
- [ ] レート制限ハンドラの設計ドラフトを MCP 実装と並行して用意する

**現状ステータス**: コア API 利用と画像アップロードは安定稼働。動画アップロード最適化は MCP 完了後に再検討。
