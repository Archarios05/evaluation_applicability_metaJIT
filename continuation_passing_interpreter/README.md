# continuation_passing_interpreter

`../sotsuron_scheme/specification.md` (第 3 版) の言語の **CPSインタプリタ** (EOPL 5章)。
継続をデータ構造で表し (5.1節)、手続き適用をトランポリン化してある (5.2節)。
パーサは `../s-reader` を使う。CEK版 `../RPythonCEK/` と値・環境・継続フレームの種類・
例題をそろえてあるので、そのまま挙動・性能を比較できる。
EOPL 5章の LETREC 言語で書いていた旧版はタグ `eopl-letrec` にある。
## ファイル

| ファイル | 中身 |
| --- | --- |
| `bounce.py` | トランポリンの Bounce (`ApplyProcBounce` / `ApplyContBounce`) |
| `value.py` | 手続き以外の値、`SchemeError`、`show` |
| `env.py` | 環境のフレーム `Frame` (字句アドレスで引く) と define の変数の場所 `GlobalCell` |
| `primitives.py` | 標準手続き 22 個 。`write_out` は出力先 |
| `proc.py` | 手続き値 `ClosureVal` / `PrimVal` / `ContVal` と `apply_procedure_k` |
| `cont.py` | 継続フレーム 6 種 (`EndCont` `IfCont` `AppCont` `SetLocalCont` `SetGlobalCont` `DefineCont`) |
| `exp.py` | 構文木 10 種と `eval_cps` |
| `convert.py` | s-reader の構文木 → `exp.py` の構文木。変数を字句アドレスに解決する |
| `interpreter.py` | `trampoline` と `JitDriver` |
| `target.py` | RPython翻訳用のエントリポイント |
| `rpy.py` | RPython の import と CPython 用ダミー |
| `smoke_test.py` | CPython3 用テスト (例は RPython3imp / CEK版と同じ) |
| `examples/` | ベンチマーク用の例題 |

`value.py` / `env.py` / `primitives.py` / `convert.py` は CEK版とほぼ同じ。CPS版の `Value` は `Bounce` を継承し、
手続きでない値の適用 `apply_procedure_k` を持つ点だけが違う。
→CEKと揃えたい
## JIT

```python
jitdriver = JitDriver(greens=['exp'], reds=['env', 'cont'])
```

- `jit_merge_point` は `trampoline` の `while` の先頭。ループのバックエッジが本物のジャンプになる。
- green の `exp` はクロージャ本体の構文木。同じ本体に戻ってきたらループの先頭とみなす。
  (旧版は green をクロージャ値 `proc` にしていた。値は実行時に作られるので、構文木のほうがまだマシ？？）
- 継続手続きの適用 (`ApplyContBounce`) は合流点を通さず内側の `while` で進める。

## 使い方

```sh
python smoke_test.py
python target.py examples/fib.scm

# WSL
RPY=~/research/effect-jit-artifact/rpyeffect-jit/pypy/rpython/bin/rpython

RPythonのディレクトリ指定

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
