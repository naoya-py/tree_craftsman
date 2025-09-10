# py_tree_craftsman (pytree)

[![build](https://img.shields.io/badge/build-passing-brightgreen)](#)
[![tests](https://img.shields.io/badge/tests-none-lightgrey)](#)
[![coverage](https://img.shields.io/badge/coverage-0%25-lightgrey)](#)

小さなユーティリティ `pytree` は、指定したディレクトリから ASCII ツリーを生成し、人間向けの UTF-8 テキストと機械処理向けの JSON を出力します。追加で Structlog + orjson を用いて `logs/tree_logs.jsonl` に JSONL ログを残します。日時は Pendulum の `Asia/Tokyo`（ISO 8601、常に +09:00）で付与します。

## 目次
- プロジェクト概要
- インストール
- 実行方法
- サンプル
- コマンドライン引数とオプション
- 出力とログ
- 終了コード

## プロジェクト概要

`pytree` は次を行います:

- 指定ディレクトリのファイル/フォルダ構造を ASCII tree として生成
- 人間向け UTF-8 テキスト (`<basename>_tree.txt`) を作成
- orjson でシリアライズした機械処理用 JSON (`<basename>_tree.json`) を作成
- `logs/tree_logs.jsonl` に JSONL を追記（structlog + orjson）

デフォルトの出力先はリポジトリルートの `out` ディレクトリです（`--out` で上書き可）。

## インストール

開発用仮想環境を作り、依存をインストールしてください:

```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

将来的にパッケージ化する場合は `pyproject.toml` / `setup.cfg` に `console_scripts` を追加して `pytree` をインストールできるようにしてください。

## 実行方法

PowerShell 例（`src` を PYTHONPATH にして直接実行する場合）:

```powershell
$env:PYTHONPATH = 'D:\Dev\Projects\py_tree_craftsman\src'
D:\Dev\Projects\py_tree_craftsman\.venv\Scripts\python.exe -m tree_craftsman <PATH> [--out <OUT_DIR>]
```

引数に `--out` を与えない場合、デフォルトはプロジェクトルート下の `out` ディレクトリです。

## サンプル

指定したディレクトリのツリーを生成し、デフォルト出力先にファイルを作成する例:

```powershell
$env:PYTHONPATH = 'D:\Dev\Projects\py_tree_craftsman\src'
D:\Dev\Projects\py_tree_craftsman\.venv\Scripts\python.exe -m tree_craftsman C:\Users\you\Documents
```

もしくは `--out` を指定:

```powershell
D:\Dev\Projects\py_tree_craftsman\.venv\Scripts\python.exe -m tree_craftsman C:\Users\you\Documents --out C:\temp\tree_out
```

## コマンドライン引数とオプション

`pytree`（モジュールとして `python -m tree_craftsman` でも利用可）は Click を使った CLI を提供します。主な引数/オプション:

- `path` (必須位置引数): 解析対象のディレクトリパス（存在チェックあり）
- `--out <dir>`: 出力先ディレクトリ（デフォルト: `./out`）
- `-a`, `--show-hidden`: ドットファイル/フォルダを含める
- `-v`, `--verbose`: 冗長モード（指定回数でログレベル上昇）
- `--debug`: デバッグ用のスタックトレースを表示

使用例:

```powershell
D:\Dev\Projects\py_tree_craftsman\.venv\Scripts\python.exe -m tree_craftsman C:\path\to\dir --out D:\out\dir -a -v
```

自動生成されるヘルプは以下のコマンドで確認できます:

```powershell
D:\Dev\Projects\py_tree_craftsman\.venv\Scripts\python.exe -m tree_craftsman --help
```

実際のヘルプ出力例:

```text
Usage: pytree [OPTIONS] [PATH]

	pytree: generate an ASCII tree and machine-
	readable json for PATH.

	PATH must be an existing directory.

Options:
	--out TEXT         Output directory (defaults
 to                                                                 repo/out)
	-a, --show-hidden  Include hidden files      
	-v, --verbose      Increase verbosity        
	--debug            Show debug output
	--help             Show this message and exit
```

## 出力とログ

- 人間向けのテキスト: `out/<basename>_tree.txt` (UTF-8)
- 機械向け JSON: `out/<basename>_tree.json` (orjson によるエンコード、バイナリとして保存)
- ログ: `logs/tree_logs.jsonl` に JSONL 形式で追記（structlog + orjson）

ログには以下のような情報が含まれます: パス、生成時刻（ISO 8601, Asia/Tokyo）、出力ファイルパス、ファイルサイズなど。

## 終了コード

CLI は明確な終了コードを返します:

- `0` — 成功
- `2` — 使用方法エラー（引数不足など）
- `3` — 入力パスが見つからない（FileNotFound）
- `4` — 書き込み/権限エラーもしくはその他の実行時エラー

## テスト

簡易な smoke テストは `tests/test_generator.py` にあります。pytest を使って拡張テストを追加してください。

```powershell
D:\Dev\Projects\py_tree_craftsman\.venv\Scripts\python.exe -m pytest -q
```

## ライセンス

プロジェクトのライセンスをここに明記してください（例: MIT）。

---

必要なら README に CLI 説明の短い図示、出力 JSON のスキーマ例、CI バッジの本番リンクを追加します。どれを優先しますか？
