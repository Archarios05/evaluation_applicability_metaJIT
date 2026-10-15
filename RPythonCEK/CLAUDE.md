# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

EOPL 5章のLETREC言語を **CEK抽象機械** として実装したもの。言語仕様・遷移規則・
ベンチマーク結果は `README.md` に詳しくあるので、まずそちらを読むこと。
このファイルには README に書かれていない「編集時の制約」だけを書く。

## コマンド

```sh
python smoke_test.py     # テスト一式 (CPython3)
python demo_trace.py     # 状態遷移を1ステップずつ表示 (CPython3)
```

テストフレームワークは使っていない。`smoke_test.py` は素の `assert` を並べた関数を
`__main__` から順に呼ぶだけなので、**1つだけ走らせるには関数を直接呼ぶ**:

```sh
python -c "import smoke_test; smoke_test.test_letrec()"
```

新しいテストを足したら `__main__` ブロックへの追記も必要（自動収集はされない）。

RPython翻訳は WSL 上で python2 + rpython ツールチェインを使う（README「使い方」参照）。
翻訳済みバイナリ `target-c` / `target-c-nojit` はコミット済みだが、ソースを変更したら
当然古くなる。

## 最重要の制約: 全ファイルが RPython (Python2 サブセット)

`smoke_test.py` と `demo_trace.py` **以外**のすべての .py は RPython で翻訳される。
したがって使ってはいけないもの:

- `@dataclass` / `abc.ABC` / 引数注釈 / f-string / `from __future__ import annotations`
- `Value or None` のような union になる戻り値（アノテータが通らない。
  `env.lookup_variable_value` が未束縛時に `None` ではなく例外を
  投げるのはこの理由）

型分岐は `isinstance` で行い、クラスは素の `__init__` だけを持つ形に揃える。

### print ではなく os.write

`cont.py` / `target.py` は `os.write(1, "...")` に `str` を直接渡す
（RPython では `str == bytes`）。CPython3 ではこれは動かないので、
`smoke_test.py` が冒頭で `os.write` を包むシムを噛ませている。
**翻訳対象ファイルの `os.write` を「Python3 で動くように」直してはいけない** —
壊れるのは翻訳の方。

## 依存の向きとダックタイピング

```
value / proc / state  →  cont  →  exp  →  machine  →  target
```

一方向であることが設計上の前提。特に **`state.py` は exp / cont のどちらも import
しない**。`exp.eval_step` / `kont.apply_kont` をダックタイピングで呼ぶことで循環を
避けているので、型注釈目的でも import を足さないこと。

## 言語に構文を1つ足すときに触る場所

1. `exp.py` に `Exp` サブクラス（`eval_step` = Eval遷移1本）
2. `cont.py` に対応する `Kont` サブクラス（`apply_kont` = Cont遷移1本）
3. `target.py` に `build_*` の例題ビルダ（パーサは存在せず、プログラムは手組みAST）
4. `smoke_test.py` にテスト + `__main__` への追記
5. `README.md` の「遷移規則」表を更新

`target.py` の `build_*` は `smoke_test.py` からも import されている。例題は
CPS版 (`../continuation_passing_interpreter/`) と同じものを維持する方針
— 挙動と性能を直接比較するためのプロジェクトなので、片方だけ変えない。

## ドライバが2本ある

- `run_machine` — レジスタ化した本番用ループ。JIT の `jit_merge_point` が入る
- `run_states` — 教科書どおりに `state.step()` を回すだけの版

両者は同じ答えを返さねばならず、`test_run_states_agrees` がそれを守っている。
遷移規則を変えたら両方に効く（規則は Exp/Kont 側にあるため）が、
`run_machine` だけ最適化して意味をずらさないこと。

## JIT 周りで壊しやすい点

- `jit_merge_point` は `run_machine` の**外側** `while` の先頭に置く。ここを動かすと
  CPS版で起きた `call_assembler` 問題が再発する
- greens は `['exp']`（制御レジスタ C）。AST ノードのポインタ同一性で
  「ループ先頭」を判定している
- `ContState` を進める**内側**ループには意図的に合流点を置いていない
  （決定的な連鎖なのでトレースに展開させる）

## 既知の改善余地

環境が dict ベースのフレーム (`Env.frame`) で、変数参照が毎回ハッシュ検索になる。
JIT が定数畳み込みできず、countdown で 1.8x 程度に留まる原因と見られる。
de Bruijn インデックス化 (EOPL 3.7節) して配列アクセスにするのが次の一手。

## コードを書く際
- コードを書く際はコメントの量を最小限にすること
- 何をしているかを簡潔に書くこと