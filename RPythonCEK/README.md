# CEK machine (仕様書の Scheme サブセット)

`../sotsuron_scheme/specification.md` (第 3 版) の言語を CEK抽象機械として実装したもの。
パーサは `../s-reader` を使う。



| レジスタ | 意味 | このコードでの実体 |
| --- | --- | --- |
| **C** (Control) | いま注目している式 | `exp.Exp` |
| **E** (Environment) | 変数の束縛 | `env.Frame` (トップ・レベルは `None`) |
| **K** (Kontinuation) | 残りの計算 | `cont.Kont` |

CPSインタプリタとの関係は Danvy らの *functional correspondence* そのもの:


## ファイル構成

依存(`value`/`env`/`state` → `primitives` → `proc` → `cont` → `exp` → `convert` → `machine` → `target`)。

| ファイル | 中身 |
| --- | --- |
| `value.py` | 手続き以外の値 (`IntVal` `BoolVal` `NIL` `PairVal` `UNSPECIFIED` `UNDEFINED`)、`SchemeError`、`display` の表示 `show` |
| `env.py` | 環境のフレーム `Frame` (字句アドレスで引く) と define の変数の場所 `GlobalCell` |
| `state.py` | 状態 `EvalState` / `ContState` / `HaltState`。CEKの `<C,E,K>` そのもの |
| `primitives.py` | 標準手続き 22 個 (仕様書 6章)。`write_out` は出力先 (テストで差し替える) |
| `proc.py` | 手続き値 `ClosureVal` / `PrimVal` / `ContVal`。`apply_procedure` が適用の遷移規則 |
| `cont.py` | 継続フレーム 6 種。各 `apply_kont` が Cont遷移1本 |
| `exp.py` | 構文木 10 種。各 `eval_step` が Eval遷移1本 |
| `convert.py` | s-reader の構文木 → `exp.py` の構文木。変数を字句アドレスに解決する |
| `machine.py` | 機械の駆動ループ `run_machine` (JIT用) / `run_states` (教科書どおり) と `JitDriver` |
| `target.py` | RPython翻訳用のエントリポイント |
| `rpy.py` | RPython の import と CPython 用ダミー |
| `smoke_test.py` | CPython3で動くテスト一式 (例は RPython3imp と同じ) |
| `demo_trace.py` | 状態遷移を1ステップずつ表示するデモ (CPython専用) |
| `show_ast.py` | convert 後の構文木を木の形で表示する (CPython専用) |
| `examples/` | ベンチマーク用の例題 (RPython3imp と同じ) |


引数の個数違い・手続きでない値の適用は `SchemeError`。

## 使い方

```sh
# CPython3 でテスト
python smoke_test.py

# 状態遷移を目で追う
python demo_trace.py

# convert 後の構文木を見る
python show_ast.py examples/fib.scm

# CPython3 で直接実行
python target.py examples/fib.scm

# RPython翻訳 (WSL上、python2 + rpythonツールチェイン)
RPY=~/research/effect-jit-artifact/rpyeffect-jit/pypy/rpython/bin/rpython
python2 $RPY --opt=2   --output=target-c-nojit target.py
python2 $RPY --opt=jit --output=target-c       target.py
./target-c examples/countdown.scm
```

エラーはどれも `error` の 1 行だけを出力する (仕様書 9.1節)。

## JITについて

```python
jitdriver = JitDriver(greens=['exp'], reds=['env', 'kont'],
                      get_printable_location=get_location)
```

- `jit_merge_point` を `run_machine` の `while` の先頭に置いているので、
  ループのバックエッジがそのまま本物のジャンプになる。
- green を制御レジスタ `exp` にしているのは、ASTノードが翻訳時に固定された
  ポインタで「同じ式に戻ってきた = ループ先頭」の判定に使えるため
  (Pycket などRPython製CEK機械と同じ流儀)。
- Cont遷移 (値を継続に渡すだけの決定的な連鎖) は内側の `while` でまとめて進める。
  合流点を持たないのでJITはトレースに展開する。
- 旧版で効き目を抑えていた dict ベースの環境は、字句アドレス + 配列のフレームに置き換えた。
  depth と index は green の `exp` から読む定数なので、フレームをたどるループは展開される (`unroll_safe`)。

## 実測 (2026-10-20, WSL2 Ubuntu, 各 3 回の最小値, 秒)

`examples/` の同じプログラムを CEK版・CPS版・RPython3imp の翻訳済みバイナリで走らせた。

| 例題 | CEK-nojit | CEK-jit | CPS-nojit | CPS-jit | 3imp-nojit | 3imp-jit |
| --- | --- | --- | --- | --- | --- | --- |
| `countdown.scm` (末尾再帰 10^7 回) | 1.79 | 0.046 | 1.38 | 0.042 | 0.71 | 0.17 |
| `let-loop.scm` (letrec + 関数位置の lambda, 10^7 回) | 3.20 | 0.069 | 2.56 | 0.068 | 1.25 | 0.29 |
| `fib.scm` (fib 30) | 0.67 | 0.098 | 0.57 | 0.110 | 0.29 | 0.11 |
| `sum.scm` (非末尾再帰 10^6 段) | 0.62 | 0.45 | error | error | 0.58 | 0.52 |
| `callcc.scm` | 0.009 | 0.026 | 0.010 | 0.028 | 0.009 | 0.024 |

- CPS版の `sum` は、値を返す側の継続の連鎖でCスタックが尽き、`error` を出力して終了する
  (`StackOverflow` を捕まえて実装制限の違反として報告している)。
- 末尾再帰のループでは JIT で 30〜45 倍速くなる。旧版 (dict の環境) では 1.8 倍程度だった。
- 翻訳時間は `--opt=2` が約 35 秒、`--opt=jit` が約 345 秒 (CEK・CPS とも)。

## 旧版 (EOPL LETREC 言語, タグ `eopl-letrec`) での測定

以下は言語を書き換える前の実装での結果。例題・環境の表現が今と違うので、今の版と直接は比べられない。

### ベンチマーク(2026-09-08 実測, WSL2 Ubuntu / gcc -j8)

`target.py` は引数を取ると1つのプログラムだけを走らせる(JITのウォームアップ代を
切り分けたいので他の例題を混ぜない):

```sh
./target-c countdown 10000000     # 末尾再帰。継続は伸びない
./target-c sum 1000000            # 非末尾再帰。継続がn段積まれる
./target-c fib 20                 # fib列を出力
./target-c                        # 引数なしなら全例題
```


```sh
# CPS版 target.py に build_countdown/build_sum_to/bench/parse_int を足してから
RPY=../continuation_passing_interpreter/pypy-tutorial-jp/pypy/rpython/bin/rpython
CPS=../continuation_passing_interpreter/continuation_passing_interpreter
PYTHONPATH=$CPS python2 $RPY --opt=2   --output=cps-nojit $CPS/target.py
PYTHONPATH=$CPS python2 $RPY --opt=jit --output=cps-jit   $CPS/target.py
./cps-jit countdown 10000000
```
