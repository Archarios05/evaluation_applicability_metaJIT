# 3imp スタックベースモデル (RPython)

`../3imp/3imp-4.3+4.4+4.5.scm` (Dybvig "Three Implementation Models for Scheme" 4章) を
RPython で書き直したもの。受け付ける言語は `../sotsuron_scheme/specification.md` のサブセットで、
パーサは `../s-reader` を使う。

## 元の Scheme 版からの変更

| 項目 | 3imp-4.3+4.4+4.5.scm | この実装 |
| --- | --- | --- |
| コード表現 | 次の命令を最後の要素に持つ入れ子リスト (if で DAG) | 1 本の整数配列 `Code.ops`。分岐は `test`/`jump` の絶対番地。lambda 本体はその場に置いて `functional`/`close` の終端番地で飛び越す |
| set! | `find-sets` → `box`/`indirect`/`assign` | 元のまま。set! される仮引数だけ本体の先頭で `box` する。自由変数への代入は `assign-free`。**letrec 変数** は常に box (`letrec` = 未定義値で呼ぶ slambda + `box` + `assign`) |
| 大域変数 | A リスト、実行時に `assq` | コンパイル時に番号を振った配列 `refer-global i`。define 前の参照と set! はエラー (仕様 4.7, 5.2)。define は検査なしの `define-global` |
| 評価順序 | 引数は右から左、演算子は最後 | 演算子を先に評価して積み、引数は左から右 (仕様 4.3) |
| 末尾呼出し | なし | `shift n k` (論文 4.6節)。仕様 3.6 の真正な末尾再帰 |
| call/cc | 未実装 (`find-free` に痕跡のみ) | スタックをコピーする継続 (論文 4.4節 `conti`/`nuate`)。何度でも呼べる |
| 標準手続き | `+ - >=` を `prim-return` で | 仕様 6章の 22 個。引数個数・型・あふれを検査 |
| define の lambda | slambda (functional) | clambda (closure)。トップレベルなので自由変数は無い |
| slambda の判定 | 関数位置 (if の枝も含む) | `((lambda ...) ...)` の形だけ |

slambda / clambda の使い分け、ディスプレイクロージャ、CB による自由変数の判定は元のまま。

## スタックの形

```
[frame (ret f c)] [手続き] [引数0] … [引数n-1] [一時値…]
                            ^ f
```

- `frame` は 3imp の x, f, c をまとめて 1 スロットの `W_Frame` として積む。
  RPython のスタックは要素の型を 1 つに揃える必要があるため。
- **ダイナミックリンク (保存した f) は残した**。`return k` は k 個捨てた後、frame から f を戻す。
- 手続きスロットは 3imp に無い。演算子を先に評価する (仕様 4.3) ために置いた。
  slambda の場合はここにある `W_Functional` が静的リンクを持ち、`refer n m` は
  `stack[f-1].link` を n 回たどる。
- 末尾位置の slambda / letrec は frame を積まず、外側の呼出しの領域の上に重ねる。
  その本体の `return`/`shift` は外側の領域も一緒に捨てる。静的リンクを壊さずに末尾呼出しを保つため。

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

`sum` だけ JIT がほぼ効かない。再帰が深い間はスタックが伸び続けてトレースが閉じにくいためと思われる (未確認)。
翻訳時間は `--opt=2` が約 45 秒、`--opt=jit` が約 330 秒。
