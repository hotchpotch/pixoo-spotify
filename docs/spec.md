# pixoo-spotify 仕様メモ

## 1. 初期の仕様（要約）
- Pixoo (64x64/32x32/16x16) に表示できる GIF を生成し、HTTP サーバで配信する CLI アプリ。
- Spotify の「現在再生中」情報を取得し、アートワーク + テキスト（アーティスト/タイトル）を表示。
- GIF は以下の要件：
  - アートワークを 64x64 の背景に使用（なければ灰色背景）
  - `{artist}\n{title}` を行ごとにスクロール表示
  - ビットマップフォント使用（Misaki Gothic, size 8）
  - 文字列は max 40 文字
  - 右下寄せを標準とし、位置選択可能
  - fps は 8
- Misaki Gothic フォントを raw でダウンロードし `./fonts/` に保存（gitignore 対象）
- 行ごとに言語判定（langdetect）しフォントを割り当てる（当面は en/ja ともに Misaki）
- HTTP サーバは FastAPI + Uvicorn（async）
- CLI は Typer、型は Pydantic / type hint を徹底
- Pixoo デバイス検出は `https://app.divoom-gz.com/Device/ReturnSameLANDevice`
- Pixoo への再生指示は `Device/PlayTFGif` を利用

## 2. 現在の実装（2026-01-09 時点）
### 構成と主要モジュール
- `pixoo_spotify/cli.py`
  - Typer CLI: `run` / `auth` / `devices` / `demo` / `gif`
- `pixoo_spotify/app.py`
  - Spotify → GIF 生成 → HTTP 配信 → Pixoo 再生のメインループ
- `pixoo_spotify/gif.py`
  - GIF 生成ロジック（アートワーク + 行単位スクロール）
- `pixoo_spotify/fonts.py`
  - Misaki Gothic の自動ダウンロード
- `pixoo_spotify/spotify.py`
  - Spotipy OAuth + 現在再生中トラック取得
- `pixoo_spotify/pixoo.py`
  - Pixoo デバイス発見 / PlayTFGif 呼び出し
- `pixoo_spotify/server.py`
  - FastAPI で `/gif` を配信
- `pixoo_spotify/config.py`
  - Pydantic 設定、config.toml/json 対応
- `pixoo_spotify/ui.py`
  - Rich による表示（フォアグラウンド時）
- `pixoo_spotify/dummy.py`
  - ダミー用の Track + Artwork
- `tests/`
  - GIF 生成・設定マージのテスト

### 依存関係
- Runtime: `fastapi`, `uvicorn`, `typer`, `pydantic`, `spotipy`, `httpx`, `pillow`, `langdetect`, `rich`
- Dev: `pytest`, `ruff`, `ty`, `tox`, `tox-uv`
- dev extra に登録済み: `uv run --extra dev tox`

### Spotify 認証（PKCE）
- PKCE を利用し `client_secret` は不要（`client_id` のみ必須）。
- `redirect_uri` は `http://127.0.0.1:8888/callback` がデフォルト。
- GUI ブラウザが使える場合は自動で認証完結（ローカルリダイレクト受信）。
- GUI が使えない場合は URL を別端末で開き、リダイレクトURLをコピペするフロー。

### CLI 例
- 認証: `uv run pixoo-spotify auth`
- 実行: `uv run pixoo-spotify run --public-base-url http://<host>:8000 --device-ip <pixoo-ip>`
- ダミーGIF作成: `uv run pixoo-spotify demo`

## 3. 未確認事項 / 要検証
- Spotify OAuth のヘッドレス環境対応（`open_browser=True`）は環境によって失敗の可能性あり。
- PKCE のリダイレクト URL が `127.0.0.1` 以外の場合は HTTPS が必要（運用環境に注意）。
- Pixoo 側の `Device/PlayTFGif` が実機で正常に再生されるか未検証。
- Pixoo が GIF のスクロール表現を意図通り表示できるか未検証。
- Pixoo からの画像取得サイズが 64px のみか、32/16 も取得可能か要確認。
- `public_base_url` を指定しない場合の URL が Pixoo 側から到達できるかはネットワーク依存。
- `fonts/` の自動ダウンロードがネットワーク制限下で失敗した場合の挙動。
- 文字列の長さ制限（max 40）での表示崩れ確認が必要。

## 4. 次の開発者への申し送り事項
- 実機 Pixoo での再生確認を最優先で実施してください。
- Spotify 認証は手動入力フローなので、運用を考えるなら OAuth リダイレクト受け側の実装が必要です。
- `config.toml` のサンプルがまだ無いので、運用向けにテンプレ追加が望ましいです。
- GIF のスクロール速度・余白・位置は `GifConfig` で調整可能です。
- 文字の言語判定は行単位で行い、フォントは en/ja ともに Misaki Gothic に固定しています。
- 64/32/16 サイズは `GifConfig.size` で変更できますが、文字表示の見え方確認が必要です。
- テストは軽量なので、Pixoo 実機テストを自動化する場合は統合テストを追加してください。
