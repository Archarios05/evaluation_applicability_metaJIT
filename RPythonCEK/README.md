# CEK machine (EOPL LETREC 言語)

`continuation_passing_interpreter/` のCPSインタプリタを、**CEK抽象機械**として
書き直したもの。言語仕様(EOPL 5.1節のLETREC言語 + `print`)も、継続フレームの
種類も、例題プログラムも向こうと同じなので、そのまま挙動・性能を比較できる。

## CEK機械とは

状態が3つのレジスタからなる抽象機械 (Felleisen & Friedman 1986)。

| レジスタ | 意味 | このコードでの実体 |
| --- | --- | --- |
| **C** (Control) | いま注目している式 | `exp_representation.Exp` |
| **E** (Environment) | 変数の束縛 | `env_representation.Env` |
| **K** (Kontinuation) | 残りの計算 | `cont_representation.Kont` |

CPSインタプリタとの関係は Danvy らの *functional correspondence* そのもの:

```
直接式インタプリタ --CPS変換--> CPSインタプリタ
                   --継続をデータ構造化(EOPL 5.1)--> 継続オブジェクト
                   --トランポリン化(EOPL 5.2)------> Bounce
                   --レジスタ化(EOPL 5.3)---------> CEK機械  ← ここ
```

## CPS版との違い(ここが本題)

| | `continuation_passing_interpreter` | `CEK` |
| --- | --- | --- |
| 1ステップの表現 | `eval_cps` / `apply_cont` が**次の関数を呼ぶ** | `eval_step` / `apply_kont` が**次の状態を返すだけ** |
| ホストのスタック | 継続の連鎖ぶんだけ伸びる (CPythonでは `sys.setrecursionlimit` が必要だった) | 常に一定。`run_machine` の `while` ループだけ |
| 手続き適用 | `ProcVal.apply_procedure_k` が `ApplyProcBounce` を返し、`trampoline` が開封 | `RandKont.apply_kont` の1状態遷移。`Bounce` 型自体が不要 |
| トランポリンに戻る頻度 | 手続き呼び出しのときだけ | すべての簡約ステップ |
| JITの合流点 | `trampoline` の `while` (greens=`proc`) | `run_machine` の `while` (greens=`exp`) |

実際、CPS版のスモークテストは深い再帰のために再帰上限を100万に引き上げていたが、
こちらは上限に一切触れずに `countdown(100000)` / `sum_to(20000)` が通る
(`smoke_test.py`)。

この差は翻訳後にさらに極端になる(CPS版は `sum` が n=12,000 でStackOverflowする)。
実測は「CPS版との性能比較」節を参照。

## ファイル構成

依存は一方向 (`classes`/`state` → `cont_representation` → `exp_representation` → `machine`)。

| ファイル | 中身 |
| --- | --- |
| `classes.py` | 値 `NumVal` / `BoolVal` / `ProcVal` と `expval_to_*`。CPS版と違い `Bounce` は無い |
| `state.py` | 状態 `EvalState` / `ContState` / `HaltState`。CEKの `<C,E,K>` そのもの |
| `env_representation.py` | フレーム方式の環境 (EOPL p38 / SICP 3.2) |
| `cont_representation.py` | 継続フレーム9種。各 `apply_kont` が Cont遷移1本 |
| `exp_representation.py` | AST 10種。各 `eval_step` が Eval遷移1本 |
| `machine.py` | 機械の駆動ループ + `JitDriver` + `value_of_program` |
| `target.py` | RPython翻訳用の `entry_point` / `target` / `jitpolicy` |
| `smoke_test.py` | CPython3で動くテスト一式 |
| `demo_trace.py` | 状態遷移を1ステップずつ表示するデモ(CPython専用) |

## 遷移規則

`ρ` = 環境、`κ` = 継続。`<e, ρ, κ>` が Eval状態、`<v, κ>` が Cont状態。

### Eval遷移 (`Exp.eval_step`)

```
<(const n), ρ, κ>          -> <(num-val n), κ>
<(var x), ρ, κ>            -> <ρ(x), κ>
<(proc x body), ρ, κ>      -> <(closure x body ρ), κ>
<(zero? e1), ρ, κ>         -> <e1, ρ, (zero1 κ)>
<(if e1 e2 e3), ρ, κ>      -> <e1, ρ, (if-test e2 e3 ρ κ)>
<(let x e1 body), ρ, κ>    -> <e1, ρ, (let x body ρ κ)>
<(diff e1 e2), ρ, κ>       -> <e1, ρ, (diff1 e2 ρ κ)>
<(call rator rand), ρ, κ>  -> <rator, ρ, (rator rand ρ κ)>
<(print e1), ρ, κ>         -> <e1, ρ, (print1 κ)>
<(letrec p b pb body), ρ, κ> -> <body, ρ[p=(closure b pb ρ')], κ>
```

### Cont遷移 (`Kont.apply_kont`)

```
<v,  (end)>                -> halt v            (+ "End of computation." を出力)
<v,  (zero1 κ)>            -> <(bool-val v=0), κ>
<v,  (if-test e2 e3 ρ κ)>  -> <e2, ρ, κ>  /  <e3, ρ, κ>
<v,  (let x body ρ κ)>     -> <body, ρ[x=v], κ>
<v1, (diff1 e2 ρ κ)>       -> <e2, ρ, (diff2 v1 κ)>
<v2, (diff2 v1 κ)>         -> <(num-val v1-v2), κ>
<v,  (print1 κ)>           -> <v, κ>             (+ v を出力)
<v1, (rator rand ρ κ)>     -> <rand, ρ, (rand v1 κ)>
<v2, (rand (closure x body ρ') κ)> -> <body, ρ'[x=v2], κ>    ← β規則
```

## 使い方

```sh
# CPython3 でテスト
python smoke_test.py

# 状態遷移を目で追う
python demo_trace.py

# RPython翻訳 (WSL上、python2 + rpythonツールチェイン)
python2 ../continuation_passing_interpreter/pypy-tutorial-jp/pypy/rpython/bin/rpython target.py
python2 ../continuation_passing_interpreter/pypy-tutorial-jp/pypy/rpython/bin/rpython --opt=jit target.py
```

`target.py` は RPython(Python2サブセット)前提なので、CPython3で直接は実行しない
(`os.write` に `str` を渡す)。CPython3から動かしたいときは `smoke_test.py` のように
`os.write` を包むシムを噛ませる。

## JITについて

```python
jitdriver = JitDriver(greens=['exp'], reds=['env', 'kont'],
                      get_printable_location=get_location)
```

- `jit_merge_point` を `run_machine` の `while` の先頭に置いているので、
  ループのバックエッジがそのまま本物のジャンプになる。
  CPS版で `apply_procedure_k` の再帰に置いて `call_assembler` になってしまった
  問題は、機械化した時点で構造的に起きない。
- green を制御レジスタ `exp` にしているのは、ASTノードが翻訳時に固定された
  ポインタで「同じ式に戻ってきた = ループ先頭」の判定に使えるため
  (Pycket などRPython製CEK機械と同じ流儀)。
- Cont遷移(値を継続に渡すだけの決定的な連鎖)は内側の `while` でまとめて進める。
  合流点を持たないのでJITはトレースに展開する。

## ベンチマーク(2026-09-08 実測, WSL2 Ubuntu / gcc -j8)

`target.py` は引数を取ると1つのプログラムだけを走らせる(JITのウォームアップ代を
切り分けたいので他の例題を混ぜない):

```sh
./target-c countdown 10000000     # 末尾再帰。継続は伸びない
./target-c sum 1000000            # 非末尾再帰。継続がn段積まれる
./target-c fib 20                 # fib列を出力
./target-c                        # 引数なしなら全例題
```

### countdown(末尾再帰ループ)

| n | python2 | 翻訳のみ(--opt=2) | 翻訳+JIT | JIT/翻訳のみ |
| --- | --- | --- | --- | --- |
| 100,000 | 1.91 s | 0.02 s | 0.02 s | 1.0x (差なし) |
| 1,000,000 | 18.23 s | 0.16 s | 0.09 s | 1.8x |
| 10,000,000 | - | 1.63 s | 0.86 s | 1.9x |
| 50,000,000 | - | 7.72 s | 4.54 s | 1.7x |

### sum(継続がn段積まれる非末尾再帰)

| n | 翻訳のみ | 翻訳+JIT | JIT/翻訳のみ |
| --- | --- | --- | --- |
| 100,000 | 0.04 s | 0.03 s | 1.3x |
| 1,000,000 | 0.44 s | 0.31 s | 1.4x |
| 5,000,000 | 2.50 s | 2.08 s | 1.2x |

読み取れること:

- python2実行 → 翻訳で **約110倍**、そこからJITで **さらに1.7〜1.9倍**。
  効き幅が大きいのは圧倒的に「翻訳」の方。
- n=100,000 以下ではJITあり/なしの差が出ない。トレース+コンパイルが
  終わる前にプログラムが終わるため(`jit-summary` で Tracing 0.0007s / 1ループ)。
- countdown(1.8x)より sum(1.2〜1.4x)の方が伸びが小さい。sum は継続フレームが
  ヒープに積み上がって仮想化(virtuals)で消せないぶん、JITの利きが鈍る。
- countdown でも1.8倍止まりなのは、環境が dict ベースのフレーム
  (`Env.frame`)で、変数参照が毎回ハッシュ検索になりJITが定数畳み込みできないため
  と思われる。de Bruijn インデックス化(EOPL 3.7節)して配列アクセスにすれば
  効き幅は伸びるはず。ここが次の改善点。

計測に使ったバイナリ: `target-c` (JITあり, 6.8MB) / `target-c-nojit` (440KB)。
再現するには「使い方」のコマンドで両方を翻訳して
`/usr/bin/time -f %e ./target-c countdown 10000000` のように測る。

## CPS版との性能比較(2026-09-15 実測, WSL2 Ubuntu 24.04 / gcc 13.3.0)

CPS版 `../continuation_passing_interpreter/` の `target.py` にも、このリポジトリと同一の
`build_countdown` / `build_sum_to` / `bench()` / `parse_int()` を移植したうえで、
まったく同じASTを両実装に食わせて比較した。各3回の最小値(秒)、既定スタック8MB。

| prog | n | CEK-nojit | CEK-jit | CPS-nojit | CPS-jit |
| --- | --- | --- | --- | --- | --- |
| countdown | 1,000,000 | 0.21 | 0.12 | 0.16 | **0.09** |
| countdown | 10,000,000 | 1.80 | 0.87 | 1.45 | **0.69** |
| countdown | 50,000,000 | 9.01 | 4.55 | 6.76 | **3.14** |
| sum | 100,000 | 0.05 | **0.03** | StackOverflow | StackOverflow |
| sum | 1,000,000 | 0.41 | **0.32** | StackOverflow | StackOverflow |
| sum | 5,000,000 | 2.41 | **1.77** | StackOverflow | StackOverflow |

`sum` で使える再帰深度(既定スタック8MB):

| バイナリ | sum の最大 n |
| --- | --- |
| cps-jit | 5,000 |
| cps-nojit | 12,000 |
| cek-nojit / cek-jit | 5,000,000 以上(未探索) |

読み取れること:

- **末尾再帰(countdown)ではCPS版のほうが1.3〜1.45倍速く、JITを入れても逆転しない。**
  CEKが毎遷移で `EvalState`/`ContState` を確保するコストを、JITのvirtualsが消し切れて
  いない。「翻訳+JITすれば中間オブジェクトは消える」という見込みは外れた。
- **非末尾再帰(sum)ではCPS版が動かない。** `Fatal RPython error: StackOverflow`
  (exit 134)でアボートする。CPS版は `RandCont` だけが `Bounce` を返し、残り8フレームの
  `apply_cont` は素の再帰呼び出しなので、継続の連鎖がそのままCスタックを食う。
  CEKは継続がヒープ上のオブジェクト連結なのでCスタックは一定。
- CPS版はJITを入れると深度限界が 12,000 -> 5,000 に**悪化**する。
- JITの効き幅自体はほぼ互角(countdownで CEK 1.75〜2.07x / CPS 1.78〜2.15x)。
  CEKの `sum` が 1.28〜1.67x と鈍いのは、継続フレームがヒープに積まれてvirtualsで
  消せないため(上のベンチマーク節の考察と一致)。

CPython3.13上で同じASTを走らせても傾向は同じで、CPS版のほうが速い(countdown 2.4x /
sum 1.7x)。ただしそこでもCPS版は深さで先に止まる。`sys.setrecursionlimit(2000000)` と
128MBスタックを与えても `sum` は n=600,000 が限界で、n=1,000,000 は `RecursionError`。
CEKは同じ n=1,000,000 を14.1秒で完走する。

結論として、**CEK機械の優位は速度ではなく深さ耐性にある**。どの実行形態
(CPython / 翻訳 / 翻訳+JIT)でもCPS版のほうが速く、CEKが勝つのは
「CPS版が動かない領域で動く」という一点。

計測に使ったCPS版バイナリ: `cps-jit` (7,112,224 B) / `cps-nojit` (444,736 B)。
翻訳時間は `--opt=2` が51秒、`--opt=jit` が516秒。

```sh
# CPS版 target.py に build_countdown/build_sum_to/bench/parse_int を足してから
RPY=../continuation_passing_interpreter/pypy-tutorial-jp/pypy/rpython/bin/rpython
CPS=../continuation_passing_interpreter/continuation_passing_interpreter
PYTHONPATH=$CPS python2 $RPY --opt=2   --output=cps-nojit $CPS/target.py
PYTHONPATH=$CPS python2 $RPY --opt=jit --output=cps-jit   $CPS/target.py
./cps-jit countdown 10000000
```

## 参考

- EOPL (Friedman & Wand) 5章: 5.1 継続のデータ構造表現 / 5.2 トランポリン / 5.3 レジスタ化
- Felleisen & Friedman, *Control operators, the SECD machine, and the λ-calculus* (1986) — CEK機械
- Ager, Biernacki, Danvy, Midtgaard, *A functional correspondence between evaluators and abstract machines* (2003)
- <https://rpython.readthedocs.io/en/latest/jit/optimizer.html>
