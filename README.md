# Twitter API クライアント リデザイン

このリポジトリは、tweepy を中核とした Twitter(X) API クライアントを再設計するための作業リポジトリです。旧実装 (`oldsrc/`) は 2025-10-11 時点で削除済みで、必要に応じて Git 履歴から参照してください。

## 現在のステータス (2025-10-11)
- 設計ドキュメント: `docs/twitter_api_design.md`
- `twitter_client/` に ConfigManager・OAuthManager・TweepyClient・TweetService・MediaService を実装済み
- ユニットテスト: `tests/unit/` に 22 ケース（config/auth/client/services）を追加
- 旧実装の参照: `git show <commit>:oldsrc/twitter_api_tweepy.py` 等で取得可能

## 設計ドキュメントの概要
`docs/twitter_api_design.md` では以下を定義しています。
- tweepy v2 API を利用した投稿・取得・メディア(画像/動画) アップロード
- `pydantic` v2 BaseModel によるリクエスト/レスポンスモデリング
- MCP 連携を想定したサービス層・アダプタ構成
- メディア処理要件（チャンクアップロード、`MediaProcessingTimeout` など）
- フェーズ別ロードマップと外部ライブラリ比較

## セットアップ
1. Python 3.11+ を想定。パッケージ管理には `uv` を利用。
2. 依存関係インストール: `uv sync`
3. 認証情報は `credentials/twitter_config.json` または環境変数で管理予定（詳しくは設計ドキュメントの ConfigManager セクション参照）。

## 次のアクション例
1. `TweetService`/`MediaService` の振る舞いを統合テストで検証し、必要に応じて HTTP モックを拡充する。
2. MCP アダプタや `UserService` などフェーズ2 以降のモジュールを実装する。
3. README/ドキュメントを随時更新し、MCP 連携手順や使用例を追記する。

## テストの実行
- `uv run pytest`

## 連絡先 / メモ
- 旧実装は v1.1 メディアエンドポイント依存のため、最新 API では利用できません。
- 変更提案や疑問点があれば設計ドキュメントにコメントを追記し、日付と担当者を残す運用を推奨します。
