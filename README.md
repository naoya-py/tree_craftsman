# py_tree_craftsman (pytree)

軽量なユーティリティ `pytree` は指定したディレクトリから ASCII ツリーを生成し、
人間向けの UTF-8 テキストと機械処理向けの JSON を出力します。ログは
`logs/tree_logs.jsonl` に JSONL で記録します（structlog + orjson）。

この README はリポジトリ現状に合わせて更新されています。

## 目次
- 概要
- インストール（Poetry）
- 使い方（CLI / スクリプト）
- サンプル生成スクリプト
- ログとローテーション
- テスト
- 開発上の注意点

## 概要

現在の実装で提供している主な機能:

- 指定ディレクトリのファイル/フォルダ構造を ASCII tree として生成
- 人間向けテキスト（`out/..._tree.txt`）と機械向け JSON（`out/..._tree.json`）を出力
- `src/tree_craftsman/logger.py` にサイズベースのログローテーションを行う
	`configure_size_rotating_logger` を用意
- 開発用にランダムなフォルダ構造を生成するスクリプトを `tools/generate_sample_tree.py`
	として追加
- テストは `pytest` を使い `tests/` 以下に配置（`tests/conftest.py` はテスト時に
	`src/` を自動でパスに追加します）

## インストール（Poetry 推奨）

Poetry を使う場合の手順（PowerShell）:

```powershell
# 依存をインストール（dev グループを有効にする）
poetry install --with dev

# テスト実行
poetry run pytest -q
```

備考: `pyproject.toml` 内で Python 要件と `pytest` バージョンを調整済みです。ローカルで
直接 `python` を使う場合は `PYTHONPATH=src` を設定して実行できますが、開発では Poetry を
推奨します。

## 使い方（CLI）

本プロジェクトは Click を使った CLI（モジュール `tree_craftsman.__main__`）を提供します。
仮想環境から実行する例:

```powershell
# デフォルトの出力先はプロジェクトルートの `out` ディレクトリ
poetry run python -m tree_craftsman C:\path\to\dir --out out
```

主なオプション:

- `path` (位置引数): 解析対象ディレクトリ
- `--out <dir>`: 出力先（デフォルト: `./out`）
- `-a`, `--show-hidden`: 隠しファイル/フォルダを含める
- `-v`, `--verbose`: 冗長モード（複数回指定で詳細化）
- `--debug`: スタックトレースを表示

出力ファイル例:

- `out/<basename>_tree.txt` — 人間向けテキスト（UTF-8）
- `out/<basename>_tree.json` — 機械向け JSON（orjson でシリアライズ）

## サンプル生成スクリプト

テストや動作確認用にランダムなディレクトリ構造を作るスクリプトを用意しています:

- `tools/generate_sample_tree.py`

実行例:

```powershell
# サンプルを生成して out/samples に配置
poetry run python tools/generate_sample_tree.py --root out/samples --depth 3 --breadth 2 --files-per-dir 3 --max-kb 2

# 生成結果の manifest を確認
Get-Content out\samples\manifest.json | ConvertFrom-Json
Get-ChildItem -Recurse out\samples | Select-Object FullName, Length
```

このスクリプトは `manifest.json` を作成し、生成したファイル/ディレクトリの一覧を記録します。

## ログとローテーション

ロギングは `src/tree_craftsman/logger.py` の `configure_size_rotating_logger` を使うと簡単に
サイズベースのローテーションが行えます（`logging.handlers.RotatingFileHandler` を利用）。

実装上のポイント:

- 単一プロセス環境での利用を想定（Windows の場合、複数プロセスで同一ファイルへ書き込むと
	競合が発生するため、マルチプロセス対応が必要なら `concurrent-log-handler` 等を検討してください）
- ローテート設定: `maxBytes`, `backupCount` を指定して古いログを自動削除
- 出力は JSONL（structlog + orjson）やテキストでも可能
- 将来的にはローテート後の圧縮（`.gz`）や保持ポリシー（age/size）にも対応予定

例: ロガー設定（コードスニペット）

```python
from tree_craftsman.logger import configure_size_rotating_logger

logger = configure_size_rotating_logger('logs/tree_logs.jsonl', max_bytes=10*1024*1024, backup_count=5)
logger.info('started', path=str(path))
```

## テスト

現在のテスト構成:

- `tests/test_rotating_logger.py` — RotatingFileHandler の動作確認
- `tests/conftest.py` — テスト実行時に `src/` を sys.path に追加

テスト実行:

```powershell
poetry run pytest -q
```

テスト状況: ローカルで `3 passed` を確認済みです。

## 開発上の注意点

- `src/` レイアウトを採用しているため、開発時は Poetry 経由で仮想環境を使うか、
	`PYTHONPATH` に `src` を追加してテスト/実行を行ってください。`tests/conftest.py` は
	テスト実行を容易にするため `src` を自動で追加します。
- マルチプロセス向けのロギングや、本番のログ集約（Filebeat/Fluentd/Loki 等）は別途運用設計が必要です。

---

必要なら次の作業を行います:

- ログ圧縮（ローテート後の自動 gzip）と manifest の拡張
- 出力ファイル名を `実行ディレクトリ名/<basename>_YYYYMMDDTHHMMSS.ext` の形式に変更する `save_run_outputs` の実装
- CI（GitHub Actions）ワークフロー追加（Windows + Poetry でテスト実行）

どれを優先しますか？
