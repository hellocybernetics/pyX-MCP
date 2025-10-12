# X (Twitter) API クライアント リデザイン

X (Twitter) API と連携するための Python クライアントです。tweepy をベースに v2 API (投稿) と v1.1 API (メディアアップロード) を統合し、シンプルに運用できるよう再設計しました。

## 主な機能
- デュアルクライアント構成：投稿は tweepy.Client (v2)、メディアは tweepy.API (v1.1)
- `.env` を用いた安全な認証情報管理と OAuth フロー統合
- `PostService` / `MediaService` による高レベル API
- `examples/create_post.py` による CLI からの投稿デモ
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
```

`examples/sample_image.png` をサンプル画像として同梱しているため、動作確認時には `--image examples/sample_image.png` を指定できます。

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
