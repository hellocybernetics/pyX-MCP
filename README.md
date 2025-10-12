# Twitter API クライアント リデザイン

Twitter(X) API と連携するための Python クライアントです。tweepy をベースに v2 API (ツイート投稿) と v1.1 API (メディアアップロード) を統合し、シンプルに運用できるよう再設計しました。

## 主な機能
- デュアルクライアント構成：ツイート投稿は tweepy.Client (v2)、メディアは tweepy.API (v1.1)
- `.env` を用いた安全な認証情報管理と OAuth フロー統合
- `TweetService` / `MediaService` による高レベル API
- `examples/post_tweet.py` による CLI からの投稿デモ

## 必要条件
- Python 3.13 以上
- Twitter 開発者アカウントと API キー一式
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

## ライブラリとして利用する
クライアントをコードから直接呼び出すには、以下のようにインポートしてください。

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

## CLI で試す
`examples/post_tweet.py` を使うと、簡単にツイート投稿を試せます。

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
開発ロードマップや詳細な設計は `docs/` ディレクトリを参照してください。主に以下のドキュメントを用意しています。
- `docs/twitter_api_design.md`: アーキテクチャ設計、サービス分割、エラーハンドリング方針など
- `docs/development_status.md`: スプリント進捗や今後のタスク

## テスト実行
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

## サポート
バグ報告や改善提案は issue もしくは pull request でお知らせください。プロジェクト方針や設計に関する詳細は `docs/` を参照のうえ、必要に応じてコメントを追加してください。
