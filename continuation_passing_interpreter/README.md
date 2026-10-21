# continuation_passing_interpreter

`../sotsuron_scheme/specification.md` (第 3 版) の言語の **CPSインタプリタ** (EOPL 5章)。
継続をデータ構造で表し (5.1節)、手続き適用をトランポリン化してある (5.2節)。
パーサは `../s-reader` を使う。CEK版 `../RPythonCEK/` と値・環境・継続フレームの種類・
例題をそろえてあるので、そのまま挙動・性能を比較できる。

EOPL 5章の LETREC 言語で書いていた旧版はタグ `eopl-letrec` にある。

## 評価の進み方

- `Exp.eval_cps(env, cont)` と `Cont.apply_cont(val)` が、次の計算を**直接呼び出す**。
- クロージャと継続手続きの適用だけは評価をせず、Bounce を返す。
  - `ApplyProcBounce(body, env, cont)`: 拡張した環境で本体を評価する
  - `ApplyContBounce(cont, val)`: 捕まえた継続に値を渡す
- Bounce は呼出しの連鎖をそのまま戻って `interpreter.trampoline` に届き、
  ホストのスタックはそこで巻き戻る。末尾呼出しはこれで一定の領域で回る (仕様書 3.6節)。
- 標準手続きは呼び返しをしないので、その場で計算して継続に渡す。
  `call-with-current-continuation` は引数の手続きを今の継続で適用する (それが Bounce を返す)。

値を返す側の継続の連鎖 (非末尾再帰から戻るとき) はホストのスタックを使う。
深い非末尾再帰ではホストのスタックが尽き、実装制限の違反として `error` を出力する
(仕様書 9.2節。RPython では `StackOverflow`、CPython では `RecursionError` を捕まえる)。
CEK版はここでもスタックを使わない。

## ファイル

| ファイル | 中身 |
| --- | --- |
| `classes.py` | 手続き以外の値、`SchemeError`、`show`、Bounce (`ApplyProcBounce` / `ApplyContBounce`) |
| `env.py` | 環境のフレーム `Frame` (字句アドレスで引く) と define の変数の場所 `GlobalCell` |
| `primitives.py` | 標準手続き 22 個 (仕様書 6章)。`write_out` は出力先 |
| `proc.py` | 手続き値 `ClosureVal` / `PrimVal` / `ContVal` と `apply_procedure_k` |
| `cont.py` | 継続フレーム 6 種 (`EndCont` `IfCont` `AppCont` `SetLocalCont` `SetGlobalCont` `DefineCont`) |
| `exp.py` | 構文木 10 種と `eval_cps` |
| `convert.py` | s-reader の構文木 → `exp.py` の構文木。変数を字句アドレスに解決する |
| `interpreter.py` | `trampoline` と `JitDriver` |
| `target.py` | RPython翻訳用のエントリポイント |
| `rpy.py` | RPython の import と CPython 用ダミー |
| `smoke_test.py` | CPython3 用テスト (例は RPython3imp / CEK版と同じ) |
| `examples/` | ベンチマーク用の例題 |

`env.py` / `primitives.py` / `convert.py` は CEK版とほぼ同じ (import 元が `value` か `classes` かだけ違う)。

## JIT

```python
jitdriver = JitDriver(greens=['exp'], reds=['env', 'cont'])
```

- `jit_merge_point` は `trampoline` の `while` の先頭。ループのバックエッジが本物のジャンプになる。
- green の `exp` はクロージャ本体の構文木。同じ本体に戻ってきたらループの先頭とみなす。
  (旧版は green をクロージャ値 `proc` にしていた。値は実行時に作られるので、構文木のほうが素直)
- 継続手続きの適用 (`ApplyContBounce`) は合流点を通さず内側の `while` で進める。

## 使い方

```sh
python smoke_test.py
python target.py examples/fib.scm

# WSL
RPY=~/research/effect-jit-artifact/rpyeffect-jit/pypy/rpython/bin/rpython
python2 $RPY --opt=2   --output=target-c-nojit target.py
python2 $RPY --opt=jit --output=target-c       target.py
./target-c examples/countdown.scm
```

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

## 参考

- RPython JIT の最適化: https://rpython.readthedocs.io/en/latest/jit/optimizer.html
- Ardö, Bolz et al., *Loop-Aware Optimizations in PyPy's Tracing JIT* (DLS 2012):
  https://www.maths.lth.se/matematiklth/vision/publdb/reports/pdf/ardo-bolz-etal-dls-12.pdf
- 関数一覧と解説 (旧版): https://claude.ai/code/artifact/1be3dde2-3169-480b-a13c-ef21720873b2?via=auto_preview
