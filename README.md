# X (Twitter) API クライアント リデザイン

X (Twitter) API と連携するための Python クライアントです。tweepy をベースに v2 API (投稿) と v1.1 API (メディアアップロード) を統合し、シンプルに運用できるよう再設計しました。

## 主な機能
- デュアルクライアント構成：投稿は tweepy.Client (v2)、メディアは tweepy.API (v1.1)
- `.env` を用いた安全な認証情報管理と OAuth フロー統合
- `PostService` / `MediaService` による高レベル API
- `examples/create_post.py` による CLI からの投稿デモ
- 長文スレッド投稿ユーティリティと自動リプライチェーン構築
- リポスト／取り消し API と MCP ツール
- 検索 API の expansions／fields 指定対応と著者情報解決
- サービス層に組み込まれた構造化ログとイベントフック
- **MCP (Model Context Protocol) 統合**: AI アシスタントから X API を操作可能

## 必要条件
- Python 3.13 以上
- X (Twitter) 開発者アカウントと API キー一式
- パッケージ管理ツール [uv](https://docs.astral.sh/uv/)（推奨）

## インストール
```bash
uv sync
```

### 認証情報の設定
`.env` または環境変数で認証情報を設定します。`.env` は初回保存時に自動的に 0o600（所有者のみ読み書き可）になります。

1. **Python 3.13+** を想定。パッケージ管理には `uv` を利用。
2. 依存関係インストール: `uv sync`
環境変数で設定する場合（推奨）:
```bash
export X_API_KEY="your_api_key"
export X_API_SECRET="your_api_secret"
export X_ACCESS_TOKEN="your_access_token"
export X_ACCESS_TOKEN_SECRET="your_access_token_secret"
export X_BEARER_TOKEN="your_bearer_token"  # v2 API用（オプション）
```

`.env` ファイルを利用する場合（プロジェクト直下に配置）:
```bash
# .env
X_API_KEY=your_api_key
X_API_SECRET=your_api_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_TOKEN_SECRET=your_access_token_secret
X_BEARER_TOKEN=your_bearer_token
```

`.env` はリポジトリ直下に置くと `ConfigManager` が自動的に読み込みます。別パスを使う場合は `ConfigManager(dotenv_path=Path("/path/to/.env"))` のように明示してください。 `.env*` は `.gitignore` 済みのため、バージョン管理に含めないでください。OAuth フロー経由で取得したトークンは `ConfigManager.save_credentials()` により `.env` に追記されます。

## ライブラリとして利用する
クライアントをコードから直接呼び出すには、以下のようにインポートしてください。

```python
from x_client.config import ConfigManager
from x_client.factory import XClientFactory
from x_client.services.post_service import PostService
from x_client.services.media_service import MediaService

# 1. 認証情報を読み込み
config = ConfigManager()
client = XClientFactory.create_from_config(config)

# 2. サービス層を初期化
post_service = PostService(client)
media_service = MediaService(client)

# 3. 投稿を作成
post = post_service.create_post(text="Hello from x_client!")
print(f"Post created: {post.id}")

# 4. 画像付き投稿
from pathlib import Path
media_result = media_service.upload_image(Path("image.png"))
post = post_service.create_post(
    text="Check out this image!",
    media_ids=[media_result.media_id]
)

# 5. 長文スレッド投稿
thread = post_service.create_thread(
    """Python 3.13 highlights... (long text)""",
    chunk_limit=200,
)
for idx, segment_post in enumerate(thread.posts, start=1):
    print(f"Segment {idx}: {segment_post.id}")
if not thread.succeeded:
    print("Thread failed", thread.error)

# 6. リポスト操作
repost_state = post_service.repost_post(post.id)
print("Reposted:", repost_state.reposted)

undo_state = post_service.undo_repost(post.id)
print("Repost removed:", not undo_state.reposted)

# 7. 著者情報付き検索
search_results = post_service.search_recent(
    "from:twitterdev",
    expansions=["author_id"],
    user_fields=["username", "verified"],
    post_fields=["created_at"],
)
for item in search_results:
    author = item.author.username if item.author else "unknown"
    print(author, item.text)
```

## CLI で試す
`examples/create_post.py` を使うと、簡単に投稿を試せます。

```bash
# テキストのみ
python examples/create_post.py "Hello from x_client!"

# 画像付き
python examples/create_post.py "Check out this image!" --image path/to/image.png

# 動画付き（最大512MB、チャンクアップロード対応）
python examples/create_post.py "Check out this video!" --video path/to/video.mp4

# 別パスの .env を利用
python examples/create_post.py "Hello with custom env" --dotenv /secure/path/.env

# 長文スレッド投稿（chunk_limit=180 で自動分割）
python examples/create_post.py "Long form update..." --thread --chunk-limit 180

# ファイルからスレッドを投稿（UTF-8 テキストを想定）
python examples/create_post.py --thread-file docs/thread_draft.txt

# 日本語の長文スレッド例（280文字未満で適度に改行）
python examples/create_post.py --thread-file examples/long_thread_ja.txt --chunk-limit 180

# 英語の長文スレッド例（センテンス区切りを維持）
python examples/create_post.py --thread-file examples/long_thread_en.txt --chunk-limit 240

# レートリミット回避のため各投稿間で 8 秒待つ
python examples/create_post.py --thread-file examples/long_thread_en.txt --segment-pause 8

# 失敗したスレッドの先頭ツイートを削除（重複エラーの解消に利用）
python examples/create_post.py --delete 1234567890123456789

# リポスト / リポストの取り消し
python examples/create_post.py --repost 1234567890
python examples/create_post.py --undo-repost 1234567890
```

`examples/sample_image.png` をサンプル画像として同梱しているため、動作確認時には `--image examples/sample_image.png` を指定できます。

スレッド投稿はテキストのみサポートしています（API 制約上メディア添付は不可）。`--chunk-limit` で 1 セグメントあたりの文字数上限を調整できます。`--thread-file` を指定すると Markdown/テキストファイルをそのままスレッドとして分割投稿します。

### ロングスレッド投稿における言語別の考慮事項
- **日本語**: 全角文字が多い場合は 280 文字ギリギリまで詰めると読みづらくなるため、`--chunk-limit` を 150-200 文字程度に抑えて文節ごとのまとまりを維持してください。また、句読点直後で分割されると文脈が途切れやすいので、テキストファイル側で段落ごとに空行を入れておくと安全です。UTF-8 のまま保存すれば X API で正しく扱われます。
- **英語**: URL や絵文字を含むときは Twitter 側で 23 文字換算されるため、余裕を持って `--chunk-limit` を設定します。センテンス単位で改行しておくと、分割後も読みやすさが保たれます。また、引用符や Markdown 記法を使う場合は、変換後に 280 文字を超えていないか冒頭のドラフト投稿で必ず確認してください。

スレッドを再投稿する場合、X 側の仕様で 24 時間以内に全く同じ本文を投稿すると **Duplicate content** エラーになります。前回投稿したスレッドを削除するか、テキストにタイムスタンプなどの一意な語句を追加してから再実行してください。`--delete` オプションで先頭ツイートを素早く削除できます。

また、X API は短時間に連続で投稿すると HTTP 429 (Too Many Requests) を返すことがあります。本ライブラリでは `RateLimitExceeded` を検知するとレスポンスヘッダーの `x-rate-limit-reset` に従って待機してから再試行しますが、手動投稿でも同じ制限があるため、429 が発生した場合は 2～3 分ほど待ってからコマンドを再実行してください。
`--segment-pause` を 5–10 秒程度に設定するとセグメントごとの投稿間隔に余裕を持たせられ、429 を事前に回避しやすくなります。

リポスト操作は本文/メディア不要で、`--repost` で指定 ID をリポスト、`--undo-repost` で取り消します。

## ロギングと可観測性

`PostService` には構造化された INFO/DEBUG ログとイベントフックが標準で組み込まれています。`logging.basicConfig(level=logging.INFO)` を呼び出すだけで、スレッド投稿やリポストの進行状況が `post.thread.*` / `post.repost.*` といったイベント名で確認できます。

```python
import logging

from x_client.config import ConfigManager
from x_client.factory import XClientFactory
from x_client.services.post_service import PostService

logging.basicConfig(level=logging.INFO)

client = XClientFactory.create_from_config(ConfigManager())

def metrics_hook(event: str, payload: dict[str, object]) -> None:
    # Prometheus / OpenTelemetry などへの連携ポイント
    print("metrics", event, payload)

post_service = PostService(client, event_hook=metrics_hook)
post_service.create_post("observability ready!")
```

イベントフックは成功・失敗双方のイベントを単一コールバックへ集約するため、メトリクス送出や分散トレーシングとの連携が容易です。失敗時には `post.create.error` や `post.thread.error` が呼び出されるため、再試行戦略やアラート通知と組み合わせられます。

## MCP (Model Context Protocol) で利用する

このライブラリは MCP サーバーとして AI アシスタント（Claude など）から利用できます。サービス層を再利用したアダプタにより、自然言語から投稿やメディアアップロードを行えます。

### セットアップ
1. `.env` または環境変数に X (Twitter) API 資格情報を設定する（`X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` など）。
2. `from x_client.integrations.mcp_adapter import XMCPAdapter` をインポートし、`adapter = XMCPAdapter()` で初期化する。
3. MCP ホストにツール定義を登録し、AI アシスタントから呼び出せるようにする。`adapter.get_tool_schemas()` で各ツールの JSON Schema を取得可能。

アーキテクチャ構成：
```
AI Assistant ↔ MCP ↔ XMCPAdapter ↔ Service Layer ↔ TweepyClient ↔ X API
```

### 代表的な呼び出し例

```python
from x_client.integrations.mcp_adapter import XMCPAdapter

adapter = XMCPAdapter()  # 認証情報は ConfigManager が自動読み込み

post = adapter.create_post({"text": "Hello from MCP!"})
print(post)

media = adapter.upload_image({"path": "/path/to/image.png"})
adapter.create_post({"text": "Image post", "media_ids": [media["media_id"]]})
```

### 提供ツール

- `create_post`, `delete_post`, `get_post`, `search_recent_posts`
- `create_thread`, `repost_post`, `undo_repost`
- `upload_image`（画像: JPEG/PNG/WebP/GIF, 最大 5MB）
- `upload_video`（動画: MP4, 最大 512MB, チャンクアップロード対応）
- `get_auth_status`（OAuth1 アクセストークンから `user_id` を抽出し、利用可能であればレート制限情報 `{limit, remaining, reset_at}` を返却）

### エラーハンドリング
- `ConfigurationError`: 認証情報不足。`.env` と環境変数を確認。
- `AuthenticationError`: トークン失効。OAuth フローを再実行。
- `RateLimitExceeded`: レート制限到達。`reset_at` を参照し、バックオフを実施。
- `MediaProcessingTimeout` / `MediaProcessingFailed`: 動画処理が完了しない場合。`timeout` や動画品質を調整。

### トラブルシューティング
- **Missing credentials**: `echo $X_API_KEY` などで環境変数を確認し、`.env` が 0o600 で保存されているか確認する。
- **Invalid token**: `python examples/create_post.py "test"` を実行して OAuth フローを復旧。
- **Video timeout**: `upload_video` の `timeout` を延長するか、`ffmpeg` で再エンコードする。

### テスト
```bash
uv run pytest tests/unit/test_mcp_adapter.py -v
uv run pytest tests/integration/test_mcp_workflow.py -v
```

## ドキュメント

詳細な設計・計画や既知の懸念点は `docs/x_api_design.md` を参照してください（プロジェクト内ドキュメントはこの1ファイルに統合されています）。

## テスト実行
```bash
# 全テスト実行
uv run pytest

# カバレッジ付き実行
uv run pytest --cov=x_client --cov-report=html

# 詳細モード
uv run pytest -v

# 特定のテストファイル
uv run pytest tests/unit/test_tweepy_client.py
```

## サポート
バグ報告や改善提案は issue もしくは pull request でお知らせください。プロジェクト方針や設計に関する詳細は `docs/` を参照のうえ、必要に応じてコメントを追加してください。
