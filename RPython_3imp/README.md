# 3imp スタックベースモデル (RPython)

`../3imp/3imp-4.3+4.4+4.5.scm` (Dybvig "Three Implementation Models for Scheme" 4章) を
RPython で書き直したもの。受け付ける言語は `../sotsuron_scheme/specification.md` のサブセットで、
パーサは `../s-reader` を使う。


## 命令

`opcodes.py` 参照。3imp の命令 (`refer` `refer-free` `refer-global` `indirect` `constant`
`functional` `close` `box` `test` `assign` `assign-global` `frame` `argument` `apply`
`assign-free` `return` `halt`) に `jump` `shift` `define-global` を足した 20 個。
`assign` `assign-free` `assign-global` は a を未規定値にする (set! 式の値)。

```sh
python target.py --dis examples/let-loop.scm   # 平坦なコードを表示
```

## ファイル

| ファイル | 中身 |
| --- | --- |
| `value.py` | 値 (`W_Int` `W_Pair` `W_Closure` `W_Functional` `W_Continuation` …) と `display` の表示 |
| `primitives.py` | 標準手続き。`call-with-current-continuation` だけは `vm.py` の `apply` で扱う |
| `opcodes.py` | 命令番号と逆アセンブラ |
| `codegen.py` | 構文木 → `Code`。3imp の `preprocess` + `3imp-compile` |
| `vm.py` | VM と `JitDriver` |
| `target.py` | RPython のエントリポイント |
| `rpy.py` | RPython の import と CPython 用ダミー |
| `smoke_test.py` | CPython3 用テスト |
| `examples/` | ベンチマーク用の例題 |

## 使い方

```sh
python smoke_test.py
python target.py examples/fib.scm

# WSL
RPY=~/research/effect-jit-artifact/rpyeffect-jit/pypy/rpython/bin/rpython
python2 $RPY --opt=2   --output=3imp-c-nojit target.py
python2 $RPY --opt=jit --output=3imp-c       target.py
./3imp-c examples/countdown.scm
```

## JIT

- `greens=['pc', 'code']`, `reds=['f', 's', 'a', 'c', 'vm']` (整数を先に並べる必要がある)。
- `apply` と `return` で pc が後ろに戻るときに `can_enter_jit`。
- スタックは 1 本の大きな配列 (3imp と同じ) なので virtualizable にしていない。
  積んだ値はすべてヒープに書かれる。
- 継続の保存と復元 (`save_stack`/`restore_stack`) は `dont_look_inside`。

## 実測 (2026-10-20, WSL2 Ubuntu, 1 回計測)

| 例題 | 翻訳のみ (`3imp-c-nojit`) | 翻訳 + JIT (`3imp-c`) |
| --- | --- | --- |
| `countdown.scm` (末尾再帰 10^7 回) | 0.75 s | 0.18 s |
| `let-loop.scm` (slambda + letrec, 10^7 回) | 1.27 s | 0.31 s |
| `fib.scm` (fib 30) | 0.29 s | 0.11 s |
| `sum.scm` (非末尾再帰 10^6 段) | 0.60 s | 0.57 s |

`sum` だけ JIT がほぼ効かない。再帰が深い間はスタックが伸び続けてトレースが閉じにくい？？（未確認）
翻訳時間は `--opt=2` が約 45 秒、`--opt=jit` が約 330 秒。
