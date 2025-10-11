# Twitter API クライアント リデザイン

このリポジトリは、tweepy を中核とした Twitter(X) API クライアントを再設計するための作業リポジトリです。旧実装 (`oldsrc/`) は 2025-10-11 時点で削除済みで、必要に応じて Git 履歴から参照してください。

## 現在のステータス (2025-10-12 更新)
- 設計ドキュメント: `docs/twitter_api_design.md`
- `twitter_client/` に ConfigManager・OAuthManager・TweepyClient（デュアルクライアント）・TweetService・MediaService を実装済み
- **デュアルクライアント構成**: ツイート操作はtweepy.Client (v2 API)、メディアアップロードはtweepy.API (v1.1 API)を使用
- ユニットテスト: `tests/unit/` に 22 ケース（config/auth/client/services）全て通過 ✅
- セキュリティ強化: 認証情報ファイルのパーミッション自動設定 (0o600)
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
3. 認証情報は `credentials/twitter_config.json` または環境変数で管理。ファイル保存時に自動的に0o600（所有者のみ読み書き可能）に設定されます。

### 認証情報の設定
環境変数で設定する場合（推奨）:
```bash
export TWITTER_API_KEY="your_api_key"
export TWITTER_API_SECRET="your_api_secret"
export TWITTER_ACCESS_TOKEN="your_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="your_access_token_secret"
export TWITTER_BEARER_TOKEN="your_bearer_token"  # v2 API用（オプション）
```

または `credentials/twitter_config.json` に保存:
```json
{
  "access_token": "your_access_token",
  "access_token_secret": "your_access_token_secret",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "bearer_token": "your_bearer_token"
}
```

## 次のアクション例
1. `TweetService`/`MediaService` の振る舞いを統合テストで検証し、必要に応じて HTTP モックを拡充する。
2. MCP アダプタや `UserService` などフェーズ2 以降のモジュールを実装する。
3. README/ドキュメントを随時更新し、MCP 連携手順や使用例を追記する。

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
