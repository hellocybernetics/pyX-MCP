# Twitter API クライアント リデザイン

このリポジトリは、tweepy を中核とした Twitter(X) API クライアントを再設計するための作業リポジトリです。旧実装 (`oldsrc/`) は 2025-10-11 時点で削除済みで、必要に応じて Git 履歴から参照してください。

## 現在のステータス (2025-10-12 更新)
- 設計ドキュメント: `docs/twitter_api_design.md`
- **Sprint 1 完了**: 全ての主要機能実装済み ✅
  - `TwitterClientFactory`: デュアルクライアント初期化を簡素化
  - ConfigManager・OAuthManager・TweepyClient（デュアルクライアント）・TweetService・MediaService を実装済み
  - **デュアルクライアント構成**: ツイート操作はtweepy.Client (v2 API)、メディアアップロードはtweepy.API (v1.1 API)を使用
  - **GIF 自動ルーティング**: GIF ファイルは自動的に `tweet_gif` カテゴリ + チャンクアップロードへルーティング
  - **ポーリング設定外部化**: MediaService の `poll_interval` と `timeout` をコンストラクタで設定可能
- テスト: **46テスト成功（1スキップ）** ✅
  - ユニットテスト: 32ケース（factory/config/auth/client/services + GIF/polling tests）
  - 統合テスト: 15ケース（ワークフロー検証 10ケース + HTTP モック 5ケース）
  - HTTP モックテスト: responses ライブラリで実 API 呼び出しをモック
- セキュリティ強化: 認証情報ファイルのパーミッション自動設定 (0o600)
- 動作例: `examples/post_tweet.py` で実際の使用方法を提供
- 旧実装の参照: `git show <commit>:oldsrc/twitter_api_tweepy.py` 等で取得可能

## 設計ドキュメントの概要
`docs/twitter_api_design.md` では以下を定義しています。
- tweepy v2 API を利用した投稿・取得・メディア(画像/動画) アップロード
- `pydantic` v2 BaseModel によるリクエスト/レスポンスモデリング
- MCP 連携を想定したサービス層・アダプタ構成
- メディア処理要件（チャンクアップロード、`MediaProcessingTimeout` など）
- フェーズ別ロードマップと外部ライブラリ比較

## セットアップ
1. **Python 3.13+** を想定。パッケージ管理には `uv` を利用。
2. 依存関係インストール: `uv sync`
3. 認証情報は `.env` または環境変数で管理します。`.env` ファイルは自動的に0o600（所有者のみ読み書き可能）に設定されます。
4. **新機能**: `TwitterClientFactory` を使用してクライアントを簡単に初期化できます。

### 認証情報の設定
環境変数で設定する場合（推奨）:
```bash
export TWITTER_API_KEY="your_api_key"
export TWITTER_API_SECRET="your_api_secret"
export TWITTER_ACCESS_TOKEN="your_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="your_access_token_secret"
export TWITTER_BEARER_TOKEN="your_bearer_token"  # v2 API用（オプション）
```

`.env` ファイルを利用する場合（プロジェクト直下に配置）:
```bash
# .env
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_BEARER_TOKEN=your_bearer_token
```

`.env` はリポジトリ直下に置くと `ConfigManager` が自動的に読み込みます。別パスを使う場合は `ConfigManager(dotenv_path=Path("/path/to/.env"))` のように明示してください。 `.env*` は `.gitignore` 済みのため、バージョン管理に含めないでください。OAuth フロー経由で取得したトークンは `ConfigManager.save_credentials()` により `.env` に追記されます。

## 使用例

### 基本的な使い方

```python
from twitter_client.config import ConfigManager
from twitter_client.factory import TwitterClientFactory
from twitter_client.services.tweet_service import TweetService
from twitter_client.services.media_service import MediaService

# 1. 認証情報を読み込み
config = ConfigManager()
client = TwitterClientFactory.create_from_config(config)

# 2. サービス層を初期化
tweet_service = TweetService(client)
media_service = MediaService(client)

# 3. ツイートを投稿
tweet = tweet_service.create_tweet(text="Hello from twitter_client!")
print(f"Tweet created: {tweet.id}")

# 4. 画像付きツイート
from pathlib import Path
media_result = media_service.upload_image(Path("image.png"))
tweet = tweet_service.create_tweet(
    text="Check out this image!",
    media_ids=[media_result.media_id]
)
```

### コマンドライン例

`examples/post_tweet.py` を使用してコマンドラインからツイートを投稿:

```bash
# テキストのみ
python examples/post_tweet.py "Hello from twitter_client!"

# 画像付き
python examples/post_tweet.py "Check out this image!" --image path/to/image.png

# 動画付き（最大512MB、チャンクアップロード対応）
python examples/post_tweet.py "Check out this video!" --video path/to/video.mp4

# 別パスの .env を利用
python examples/post_tweet.py "Hello with custom env" --dotenv /secure/path/.env
```

`examples/sample_image.png` をサンプル画像として同梱しているため、動作確認時には `--image examples/sample_image.png` を指定できます。

## 次のアクション例
1. ✅ **完了**: `TwitterClientFactory` 実装とテストケース追加（Sprint 1）
2. ✅ **完了**: 統合テスト追加（15ケース: ワークフロー 10 + HTTP モック 5）
3. ✅ **完了**: 動作例 `examples/post_tweet.py` 作成
4. ✅ **完了**: GIF 自動ルーティング + ポーリング設定外部化
5. **Sprint 2**: レート制限実装（`rate_limit.py` 完成、backoff 戦略）
6. **Sprint 2**: 50MB+ 動画ストリーミング最適化
7. `UserService` などフェーズ2 以降のモジュールを実装する
8. MCP アダプタや連携手順を追加する

## テストの実行
```bash
# 全テスト実行
uv run pytest

# カバレッジ付き実行
uv run pytest --cov=twitter_client --cov-report=html

# 詳細モード
uv run pytest -v

# 特定のテストファイル
uv run pytest tests/unit/test_tweepy_client.py
```

## 連絡先 / メモ
- 旧実装は v1.1 メディアエンドポイント依存のため、最新 API では利用できません。
- 変更提案や疑問点があれば設計ドキュメントにコメントを追記し、日付と担当者を残す運用を推奨します。
