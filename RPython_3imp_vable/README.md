# 3imp スタックベースモデル、PyPy 型フレーム版 (RPython)

`../RPython_3imp` を元に、スタックを JIT の **virtualizable** にした版。
命令セット・コンパイラ・値・標準手続きは `../RPython_3imp` と同じで、変えたのはスタックの持ち方だけ。
計測では実装名 `3imp_vable` として扱う (`../bench/run_bench.py`)。

## 元の 3imp との違い

元の 3imp は 1 本の大きな配列をスタックにしていて、JIT はその読み書きを消せない
(配列は伸びるので virtualizable にできず、添字も `s` からの相対位置で定数にならない)。
この版は PyPy と同じ形にした。

| | `RPython_3imp` | この版 |
| --- | --- | --- |
| スタック | 1 本の配列 (`vm.stack`、足りなくなると伸ばす) | clambda の呼出しごとに固定長の `Frame` |
| JIT から見たスタック | ふつうのヒープ配列 | `Frame` が virtualizable (`slots[*]`) |
| `s` と `f` | 配列全体での位置 | フレーム内の位置。pc ごとに一定なので `promote` する |
| 末尾でない clambda 呼出し | 同じループで続ける | `execute` の再帰 (ホストの C スタックを使う) |
| 末尾呼出し | `shift` して同じループで続ける | `shift` 後は手続きと引数がフレームの 0 番からに並ぶので、そのフレームを使い回す |
| slambda / letrec | スタックに重ねる | 同じ (呼んだ側のフレームの中に重ねる) |
| `call/cc` | スタック全体をコピー。何度でも呼べる | 今のフレームの中身だけコピー。**捕まえたフレームが生きている間だけ**呼べる |

- フレームの大きさは、コンパイル時に全命令のスタックの深さを求めて最大値にする (`codegen.max_depth`)。
  同じ pc に違う深さで来ることがないこともここで確かめている。
- 標準手続きには配列ではなく引数の値を渡す (`primitives.call_primitive(pid, x, y)`)。
  virtualizable の配列はほかの関数に渡せないため。
- 大域変数 (`globals_w`) と手続きの呼び分けは元の 3imp のまま。スタック以外の差を混ぜないため。

## 制限

- 末尾でない再帰が深いと C スタックが尽きて `error` を出力する (CPS 版と同じ)。
- 継続は「捕まえたフレームにまだ戻れる」場合だけ呼べる。呼出しから戻った後のフレームに
  再突入しようとすると `error`。`smoke_test.py` の該当テストは `error` を期待値にしてある。

## ファイル

`../RPython_3imp` と同じ構成。変えたのは `vm.py` (全面)、`codegen.py` (`max_depth`)、
`primitives.py` (`call_primitive` の引数)、`value.py` (`W_Continuation`)、`rpy.py`、`target.py`、`smoke_test.py`。

## 使い方

```sh
# リポジトリのルートで
PYTHONPATH=".;s-reader" python RPython_3imp_vable/smoke_test.py     # Windows
PYTHONPATH=.:s-reader  python RPython_3imp_vable/target.py --dis RPython_3imp_vable/examples/fib.scm

# WSL (RPython_3imp_vable の中で)
ROOT=/mnt/c/B4/research/eval_applicability_metaJIT
export PYTHONPATH=$ROOT:$ROOT/s-reader
RPY=~/research/effect-jit-artifact/rpyeffect-jit/pypy/rpython/bin/rpython
python2 $RPY --opt=2   --output=3imp-c-nojit target.py
python2 $RPY --opt=jit --output=3imp-c       target.py
```
