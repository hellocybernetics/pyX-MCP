# Twitter API クライアント 設計・計画（2025-10-12 更新）

## 1. 目的と範囲
- Python 製のクライアントライブラリとして、Twitter(X) API の投稿・取得・メディアアップロードを安全かつ拡張しやすく利用できるようにする。
- 旧 `oldsrc/` 配下の実装を置き換え、サービス層・MCP 連携・CLI から再利用できる単一コードベースを維持する。
- プロトタイプ段階を脱し、本番運用を見据えた品質（テスト容易性、エラーハンドリング、監視性）を確保する。

## 2. アーキテクチャ概要
```
Client Apps / MCP / CLI
             ↓
 Service Layer (TweetService, MediaService, …)
             ↓
    TweepyClient (v2 Tweet + v1.1 Media)
             ↓
Twitter API v2 / v1.1
```
- `twitter_client` パッケージを中心にサービス層と統合クライアントを提供し、外部インターフェース（ライブラリ API、CLI、MCP）から共通利用する。
- コンフィグ／認証、HTTP クライアント、ドメインモデル、例外を分離し、変更点を局所化する。

## 3. 品質目標
- **再利用性**: ライブラリ、CLI、MCP から同じサービス層を呼び出せる構造を維持する。
- **拡張性**: 新しいエンドポイント追加時に最小限の改修で済むよう、クライアント層とサービス層を疎結合に保つ。
- **信頼性**: レート制限や外部 API のエラーをドメイン例外で明示し、早期検知と再試行戦略を可能にする。
- **テスタビリティ**: 依存注入と HTTP モックを前提に、ユニット／統合テストを両立させる。
- **セキュリティ**: 資格情報の責務を `ConfigManager` に集約し、Secrets のハードコードを禁止する。
- **可観測性**: ログと将来導入予定のメトリクスで挙動を追跡できるようにする。

## 4. コンポーネント
### 4.1 Config & Auth
- `ConfigManager` (`config.py`): `.env`/環境変数から資格情報を読み込み、OAuth フローで得たトークンを保存。将来的に Keyring 等を差し替え可能な抽象化を維持。
- `OAuthManager` (`auth.py`): OAuth 1.0a フローをカプセル化。`callback_handler` を注入して CLI/MCP/GUI で再利用する設計。

### 4.2 クライアント層
- `TweepyClient` (`clients/tweepy_client.py`): tweepy.Client (v2) と tweepy.API (v1.1) を統合し、ツイート操作とチャンク式メディアアップロードを一本化。
- 将来の補助 `RestClient`（HTTPX など）導入を想定し、サービス層から差し替えられるインターフェースを定義済み。

### 4.3 サービス層
- `TweetService`: 投稿/取得/削除/検索を提供し、レスポンスを `pydantic` モデルへマッピング。
- `MediaService`: MIME/サイズ検証、チャンクアップロード、`processing_info` ポーリング、`MediaProcessingTimeout`/`MediaProcessingFailed` 例外を扱う。
- `UserService` などフェーズ2以降の拡張を想定したモジュール構造を維持。

### 4.4 モデルと例外
- すべての I/O モデルを `pydantic` v2 ベースで定義し、JSON Schema を自動生成可能にする。
- 例外体系: `TwitterClientError`（基底）、`AuthenticationError`、`RateLimitExceeded`、`ApiResponseError`、`MediaProcessingTimeout` 等。

### 4.5 ロギングと可観測性
- Python `logging` を利用し、呼び出し側から Logger を DI 可能。今後のメトリクス連携を見据え、レート制限情報や処理時間を構造化ログ化する計画。

## 5. MCP 統合設計
- `twitter_client/integrations/mcp_adapter.py` がサービス層をラップし、MCP に準拠したツール群を公開。
- 提供ツール: `post_tweet`, `delete_tweet`, `get_tweet`, `search_recent_tweets`, `upload_image`, `upload_video`, `get_auth_status`。
- `get_auth_status` は OAuth1 アクセストークンの `<user_id>-...` 形式からユーザー ID を抽出し、`RateLimitedClient` が保持するヘッダーを `{limit, remaining, reset_at}` に整形。ヘッダー未取得時は `rate_limit` を省略する。
- MCP 向けスキーマは `twitter_client/integrations/schema.py` で管理し、JSON Schema 生成を通じてツール定義を同期。利用手順は README の MCP セクションを参照。
- 既知課題: Tweepy のチャンクアップロードを HTTP モックする際、`responses` 互換性により統合テストをスキップ（`tests/integration/test_mcp_workflow.py::test_video_upload_workflow`）。CI 復帰に向けモック戦略の再設計が必要。

## 6. 現在の実装状況（2025-10-12）
- ✅ デュアルクライアント構成確立（tweepy.Client v2 + tweepy.API v1.1）。
- ✅ ConfigManager / OAuthManager による資格情報管理と CLI サンプル。
- ✅ `TweetService`/`MediaService` と主要ユニットテスト完了。
- ✅ MCP アダプタ実装・スキーマ・ユニット/統合テスト整備。
- ✅ README に MCP 利用方法を統合。
- 🔄 レート制限ハンドラと自動バックオフは未実装。`rate_limit.py` ドラフトを次スプリントで扱う予定。
- 🔄 実際の Twitter API を用いた手動検証はリリース前に実施が必要。

テストサマリー（最後のローカル実行）:
- ユニット: 66 passed
- 統合: 6 passed / 3 skipped（動画ワークフロー含む）

## 7. 既知の制約・懸念点
- OAuth1 アクセストークンのフォーマットが `<user_id>-<token>` でない場合、`get_auth_status` の `user_id` 取得に失敗する。プロダクション用資格情報で要確認。
- レート制限情報はレートリミットが発生したリクエスト後にのみ取得できるため、初回の `get_auth_status` では `rate_limit` が空になる場合がある。仕様として許容しつつ、今後の UX 改善を検討。
- Tweepy + `responses` の互換性不足により、チャンク動画アップロード統合テストをスキップ中。モック戦略の刷新または別ライブラリ採用を検討。
- 実環境での API 呼び出し結果は手動検証に頼っており、CI での自動カバレッジが不十分。

## 8. 今後の計画
### 8.1 次スプリント（2025-10-19〜2025-10-31）
1. `rate_limit.py` 実装と指数バックオフ導入。
2. サービス層からのレート制限例外連携および再試行ロジック追加。
3. MCP レスポンスにバックオフ情報を付与する設計検討。
4. レート制限・認証エラーのテストケース拡充（429/401 モック）。

### 8.2 バックログ
- 50MB 超動画のストリーミング最適化と CI モック再構築。
- `UserService` / `StreamService` などフェーズ2機能の設計。
- MCP ツールの拡張（ツイート削除以外のユーザー操作など）。
- CI/CD パイプライン整備（lint、カバレッジ、メトリクス、Secrets スキャン）。
- マルチユーザー認証管理、Secrets 管理基盤との統合。

## 9. 手動検証ポリシー（暫定）
1. `.env` に有効な Twitter API 資格情報を設定し、`ConfigManager` から読み込む。
2. `python examples/post_tweet.py --video <path>` などで動画アップロード→ツイート投稿を確認し、`processing_info` を記録。
3. タイムアウト／失敗分岐は大容量ファイルや不正動画を用意して検証し、`MediaProcessingTimeout` / `MediaProcessingFailed` 発生をログ化。
4. 手動テスト結果は `docs/manual_test_reports/`（将来作成）に日付付きで記録し、モック戦略改善後は CI へ還元する。

## 10. 重要な決定と背景
- 2025-10-11: 旧 tweepy 実装を削除し、新パッケージへ全面移行。必要に応じてコミット `57963d0a1802be367b02958c2e8732d1dfe2ec40` で参照可能。
- デュアルクライアント方針を採用し、メディア系は v1.1 API を継続利用。将来 v2 で補完された場合に差し替えやすい抽象化を保持。
- MCP アダプタはサービス層のロジックを再利用し、JSON Schema によるツール宣言を採用。エラーハンドリングはドメイン例外から MCP エラー形式へマッピング。
- ロギングは標準 `logging` を活用し、呼び出し側でハンドラ差し替え可能な設計とした。メトリクス導入はバックログに位置付け。
- tweepy 採用理由: コミュニティ規模と更新頻度が高く、v2/v1.1 API の双方を一貫したインターフェースで扱える点、既存ツールの社内資産との互換性を優先した。動画アップロードのチャンク処理や OAuth1 サポートが成熟しており、Phase 1 を迅速に立ち上げる目的に合致していた。
- RestClient 準備の背景: Ads/Premium/GraphQL など tweepy がカバーしないエンドポイントや、HTTP レベルでの細かなタイムアウト制御・リトライ実装が必要になるリスクを見込み、HTTPX ベースのフォールバックを計画。`clients/rest_client.py` のスケルトンとインターフェースは初期段階から確保済み。
- 差し替え容易性の確保: サービス層は `TweetClient` / `MediaClient` プロトコルに依存し、具象実装は DI で注入する構造を採用。メディア処理やツイート操作はインターフェース経由で呼び出すため、tweepy 実装を RestClient 実装へ置き換える際はファクトリで注入するクライアントを切り替えるだけで済む。テストもプロトコル準拠のフェイクで構築しており、将来の全面移行時にサービス層の改修を最小化できる。

---
この文書はプロジェクトの単一ソースとして設計と計画を管理する。最新の利用手順や API 例は `README.md` を参照し、更新が必要な場合は本書と README を同期させること。
