# メタトレーシングJITのインタプリタ実装モデルにおける適用性評価

卒業論文の実装コード一式。同じ Scheme サブセット言語のインタプリタを複数の実装モデルで RPython により書き、
メタトレーシングJIT の効果を比較する。

## フォルダ構成

| フォルダ | 内容 |
| --- | --- |
| [`sotsuron_scheme/`](sotsuron_scheme/) | 対象言語の仕様書 (`specification.md`)。R5RS から機能を削った自作言語で、`r5rs-ja/` は参照元の R5RS 日本語訳 |
| [`s-reader/`](s-reader/) | 対象言語のパーサ (字句解析・S式リーダー・構文木への変換と静的検査)。各インタプリタが共通で使う |
| [`RPythonCEK/`](RPythonCEK/) | **CEK 機械**による実装。|
| [`continuation_passing_interpreter/`](continuation_passing_interpreter/) | CPS インタプリタによる実装 (EOPL 5章)。|
| [`RPython_3imp/`](RPython_3imp/) | スタック型バイトコードインタプリタによる実装。Dybvig "Three Implementation Models for Scheme" 4章のスタックベースモデルを RPython で書き直したもの |
| [`bench/`](bench/) | 計測スクリプト。各実装の JIT あり / なしのバイナリで例題を実行し、時間と PYPYLOG を採取・集計する |

各フォルダの詳細はそれぞれの `README.md` を参照。

## bench/ のスクリプト

WSL 上の `python3` でリポジトリのルートから実行する。

| ファイル | 役割 |
| --- | --- |
| `run_bench.py` | 時間計測とログ採取。結果は `bench/results/runs/<日時>/` に置く |
| `collect_noopt.py` | 最適化前 (`jit-log-noopt`) と最適化後 (`jit-log-opt`) のトレースを同じ実行で採取する |
| `analyze.py` | 計測結果から指標ごとの表を作る |
| `logtool.py` | 計測回の一覧・比較、トレースの表示、HTML ビューア (`logviewer.html`) の書き出し |

## メモ
- [`計測結果20261022.md`](計測結果20261022.md): 2026-10-22 の計測結果

## 前提

- 各インタプリタは RPython で翻訳してバイナリ (`target-c`, `target-c-nojit`, `3imp-c` など) を作る。
  バイナリは原則 git 管理外 (`.gitignore`) なので、翻訳手順は各フォルダの README を参照。
- `smoke_test.py` は CPython3 でそのまま動く。
- 3つのインタプリタは元は別リポジトリで、履歴ごとこのリポジトリに統合した。
