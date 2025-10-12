# 開発ステータス（2025-10-12 時点）

## 1. 完了済みチェックリスト
- [x] デュアルクライアント構成（tweepy.Client v2 + tweepy.API v1.1）
- [x] ConfigManager / OAuthManager による `.env` ベースの認証情報管理
- [x] TweetService / MediaService のユースケース実装と単体テスト
- [x] CLI サンプル `examples/post_tweet.py`
- [x] メディアアップロードの安定化（GIF 自動ルーティング、ポーリング設定）

## 2. 進行中および直近の優先事項
### 2.1 MCP アダプタ構築（最優先）
- [ ] **MCP API スキーマ定義**
  - [ ] ツイート投稿、メディアアップロード、認証状態取得のエンドポイント設計
  - [ ] `pydantic` モデルとのマッピングポリシーを決定
- [ ] **アダプタ実装**
  - [ ] `twitter_client/integrations/mcp_adapter.py` のスケルトン作成
  - [ ] ConfigManager とサービス層の DI（依存注入）整備
  - [ ] ユーザー／サービスアカウント切り替えの抽象化
- [ ] **MCP 用テスト**
  - [ ] モック接続先によるユニットテスト
  - [ ] 代表的なワークフロー（テキスト投稿・画像付き投稿）の統合テスト
- [ ] **ドキュメント整備**
  - [ ] `docs/mcp_integration.md`（仮）でセットアップ／利用手順
  - [ ] README から MCP 手順への導線を追加

### 2.2 レート制限・リトライ戦略
- [ ] `rate_limit.py` の実装とバックオフ設定
- [ ] TweetService / MediaService からの組み込み
- [ ] テストケース（429 応答をモック）

## 3. 後回しにした項目（バックログ）
- [ ] 50MB 超動画ストリーミングの最適化（MCP 完了後に再検討）
- [ ] Streaming API / UserService など Phase 2 以降のモジュール追加
- [ ] CI/CD での自動化（lint, coverage, メトリクス）

## 4. 参考情報
- 設計全般: `docs/twitter_api_design.md`
- CLI / ライブラリ利用方法: `README.md`
- 旧 tweepy 実装は 2025-10-11 時点で削除済み。履歴はコミット `57963d0a1802be367b02958c2e8732d1dfe2ec40` を参照。v1.1 メディアエンドポイント依存のため最新 API では利用不可。
