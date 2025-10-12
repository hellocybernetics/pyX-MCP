# 開発ステータス (2025-10-12 更新)

## 現状まとめ
- 設計ドキュメント: `docs/twitter_api_design.md`
- **Sprint 1 完了**（主要機能実装済み）
  - `TwitterClientFactory` によるデュアルクライアント初期化
  - ConfigManager / OAuthManager / TweepyClient / TweetService / MediaService 実装
  - GIF 自動ルーティング（チャンクアップロード）とポーリング設定外部化
- テスト状況
  - ユニットテスト: 32 ケース
  - 統合テスト: 15 ケース（HTTP モック含む）
  - `uv run pytest` ベースで CI 実行可能
- セキュリティ: 認証情報ファイルの自動パーミッション設定 (0o600)
- ドキュメント: `examples/post_tweet.py` を含む使用例・CLI フロー整備済み

## 今後のタスク例
1. **Sprint 2**
   - レート制限ハンドリング (`rate_limit.py`) と指数バックオフ戦略
   - 50MB 超動画アップロードのストリーミング最適化
2. MCP アダプタ連携手順のドキュメント化と実装
3. `UserService` などフェーズ 2 以降のモジュール追加
4. CI/CD での lint / test 自動化と監視メトリクス整備

## 旧実装について
- 旧 tweepy 実装（`create_tweet.py`, `handlers.py`, `twitter_api_tweepy.py`）は 2025-10-11 時点で削除済み。
- 過去の挙動を参照する場合は Git 履歴 `57963d0a1802be367b02958c2e8732d1dfe2ec40` 付近を参照。
- 旧実装は v1.1 メディアエンドポイント依存のため、最新 API では動作しない。
