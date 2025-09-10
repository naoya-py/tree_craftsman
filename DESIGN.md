# セマンティックコミット／バージョン自動化 設計書

目的
- conventional commits に基づき、自動的にセマンティックバージョン（vX.Y.Z）を決定してタグ作成・CHANGELOG 更新・version ファイル更新を行う。
- Python リポジトリ（tree_craftsman）向けに、CI 上で自動リリースを実行する運用設計と最低限の実装スケルトンを用意する。

採用方針
- リリースエンジン: Node の semantic-release を使用（慣れているプラグインが豊富なため）。ただし pyproject.toml の version を更新するために @semantic-release/exec 経由で Python スクリプトを呼び、pyproject.toml を更新する。
- コミット規約: Conventional Commits（feat/fix/docs/...、BREAKING CHANGE / type!: で major）
- メインブランチ: main（ここにマージされたコミットを解析してリリース）
- タグ形式: vX.Y.Z

バージョニングルール（要約）
- major: BREAKING CHANGE を含む、または type!: を用いたコミット（例 feat!: ）
- minor: feat:
- patch: fix:, perf:
- no release: docs:, style:, chore:, ci:, test:, refactor:（必要ならルール追加可）
- 優先度: major > minor > patch（同一期間のコミット群で最も重大なものだけ反映）

CI ワークフロー（概要）
1. main ブランチへ push / merge が起きる
2. GitHub Actions が実行（fetch-depth: 0）
3. Node 環境を用意し、semantic-release と必要プラグインをインストール
4. semantic-release がコミットを解析して nextRelease.version を決定
5. @semantic-release/exec で Python スクリプトを呼び pyproject.toml（または setup.cfg）内の version を更新
6. @semantic-release/changelog で CHANGELOG.md を更新
7. @semantic-release/git で CHANGELOG.md と pyproject.toml をコミット（semantic-release 側で行う）
8. Git タグと GitHub Release を作成
9. （オプション）PyPI への upload は別ジョブ／設定で実行

ファイル構成（スケルトン）
- .releaserc.json               - semantic-release の設定
- .github/workflows/release.yml - リリース用 GitHub Actions
- tools/bump_version.py         - pyproject.toml を更新するスクリプト（呼び出し専用）
- .czrc                        - commitizen 設定（コミット作成補助）
- commitlint.config.js         - commitlint 設定
- CHANGELOG.md                 - 自動生成されるので空のヘッダを置く（任意）
- DESIGN.md (本書)             - 設計書

運用上の注意
- コミットメッセージの一貫性維持のため commitizen や commitlint を導入を推奨する。
- マージ戦略は「squash and merge」を推奨（squash 時のメッセージを conventional commit 形式にする）。
- 大規模な breaking change は PR テンプレートで明示する運用を追加する。
- private リポジトリや monorepo の場合は設定を拡張する（パッケージごとの release、paths フィルタ等）。

拡張 / 代替案
- Node semantic-release の代わりに python-semantic-release を採用することも可能。その場合は pyproject.toml に [tool.semantic_release] を追加し、GitHub Actions の実行コマンドを変更する。
- CHANGELOG のフォーマットや release notes のテンプレートは @semantic-release/release-notes-generator の preset/host を調整してプロジェクトに合わせる。

短いワークフロー例（ユーザー操作→結果）
- PR を squash & merge（メッセージ: "feat: add X"） → CI が main 上で実行 → semantic-release が feat を検知して minor 増分 → pyproject.toml を更新、CHANGELOG.md 更新、タグ v1.1.0 作成 → GitHub Release 作成