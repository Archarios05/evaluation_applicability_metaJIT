# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`../sotsuron_scheme/specification.md` の言語を **CEK抽象機械** として実装したもの。
遷移規則・ファイル構成は `README.md` にあるので、まずそちらを読むこと。
このファイルには README に書かれていない「編集時の制約」だけを書く。
EOPL LETREC 言語で書いていた旧版はタグ `eopl-letrec`。

## コマンド

```sh
python smoke_test.py               # テスト一式 (CPython3)
python demo_trace.py               # 状態遷移を1ステップずつ表示 (CPython3)
python target.py examples/fib.scm  # 1 本実行 (CPython3)
```

テストフレームワークは使っていない。`smoke_test.py` は素の `assert` を並べた関数を
`TESTS` から順に呼ぶだけなので、**1つだけ走らせるには関数を直接呼ぶ**:

```sh
python -c "import smoke_test; smoke_test.test_callcc()"
```

新しいテストを足したら `TESTS` への追記も必要（自動収集はされない）。

RPython翻訳は WSL 上で python2 + rpython ツールチェインを使う（README「使い方」参照）。

## 最重要の制約: 全ファイルが RPython (Python2 サブセット)

`smoke_test.py` と `demo_trace.py` **以外**のすべての .py は RPython で翻訳される。
したがって使ってはいけないもの:

- `@dataclass` / `abc.ABC` / 引数注釈 / f-string / `from __future__ import annotations`
- `Value or None` のような union になる戻り値（アノテータが通らない）

型分岐は `isinstance` で行い、クラスは素の `__init__` だけを持つ形に揃える。
RPython の import (`JitDriver` など) は `rpy.py` 経由にして、CPython ではダミーに落とす。

### 出力は primitives.write_out

`display` / `newline` / `error` の出力はすべて `primitives.write_out` を通す
（中身は `os.write(1, s)`。RPython では `str == bytes`）。CPython3 で動かすときは
`smoke_test.py` や `target.py` の `__main__` がこれを差し替える。
**翻訳対象ファイルの `os.write` を「Python3 で動くように」直してはいけない** —
壊れるのは翻訳の方。

## パーサは ../s-reader

`convert.py` が `sys.path` に `../s-reader` を足して `reader` / `syntax` を import する。
静的検査 (未束縛変数・`set!` の対象など) は s-reader が済ませている前提で、
`convert.py` は名前の解決しかしない。s-reader の構文木と `exp.py` はクラス名が
重なるので、`convert.py` では `syntax.IfExp` のようにモジュール名付きで参照する。

## 依存の向きとダックタイピング

```
value / env / state  →  primitives  →  proc  →  cont  →  exp  →  convert  →  machine  →  target
```

一方向であることが設計上の前提。特に **`state.py` は exp / cont のどちらも import
しない**。`exp.eval_step` / `kont.apply_kont` をダックタイピングで呼ぶことで循環を
避けているので、型注釈目的でも import を足さないこと。

## 構文や標準手続きを足すときに触る場所

1. 仕様書と `../s-reader` (構文・静的検査)
2. `exp.py` に `Exp` サブクラス（`eval_step` = Eval遷移1本）
3. 必要なら `cont.py` に `Kont` サブクラス（`apply_kont` = Cont遷移1本）
4. `convert.py` に変換
5. `smoke_test.py` にテスト + `TESTS` への追記
6. `README.md` の「遷移規則」を更新

CPS版 (`../continuation_passing_interpreter/`) にも同じ変更を入れる。値・環境・
継続フレームの種類・例題 (`examples/`) をそろえて挙動と性能を直接比べるための
プロジェクトなので、片方だけ変えない。`primitives.py` / `env.py` / `convert.py` は
CPS版とほぼ同じ内容。

## 継続は何度でも呼ばれる

`call-with-current-continuation` は K レジスタの値をそのまま `ContVal` に入れるだけで、
継続は multi-shot。したがって **継続フレームのフィールドを書き換えてはいけない**
（`AppKont.apply_kont` が `vals` を作り直しているのはこのため）。
一方、変数の場所 (`Frame.vals` / `GlobalCell.value`) は継続で巻き戻らないのが正しい。

## ドライバが2本ある

- `run_machine` — レジスタ化した本番用ループ。JIT の `jit_merge_point` が入る
- `run_states` — 教科書どおりに `state.step()` を回すだけの版

両者は同じ答えを返さねばならず、`test_run_states_agrees` がそれを守っている。
遷移規則を変えたら両方に効く（規則は Exp/Kont/Proc 側にあるため）が、
`run_machine` だけ最適化して意味をずらさないこと。

## JIT 周りで壊しやすい点

- `jit_merge_point` は `run_machine` の**外側** `while` の先頭に置く。ここを動かすと
  CPS版で起きた `call_assembler` 問題が再発する
- greens は `['exp']`（制御レジスタ C）。AST ノードのポインタ同一性で
  「ループ先頭」を判定している
- `ContState` を進める**内側**ループには意図的に合流点を置いていない
  （決定的な連鎖なのでトレースに展開させる）
- 実行時にループを持つ関数は `unroll_safe` を付ける (`env.frame_at`, `LetrecExp.eval_step`)

## コードを書く際
- コードを書く際はコメントの量を最小限にすること
- 何をしているかを簡潔に書くこと
