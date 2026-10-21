# CEK machine (仕様書の Scheme サブセット)

`../sotsuron_scheme/specification.md` (第 3 版) の言語を **CEK抽象機械** として実装したもの。
パーサは `../s-reader` を使う。CPS版 `../continuation_passing_interpreter/` と
値・環境・継続フレームの種類・例題をそろえてあるので、そのまま挙動・性能を比較できる。

EOPL 5章の LETREC 言語で書いていた旧版はタグ `eopl-letrec` にある。

## CEK機械とは

状態が3つのレジスタからなる抽象機械 (Felleisen & Friedman 1986)。

| レジスタ | 意味 | このコードでの実体 |
| --- | --- | --- |
| **C** (Control) | いま注目している式 | `exp.Exp` |
| **E** (Environment) | 変数の束縛 | `env.Frame` (トップ・レベルは `None`) |
| **K** (Kontinuation) | 残りの計算 | `cont.Kont` |

CPSインタプリタとの関係は Danvy らの *functional correspondence* そのもの:

```
直接式インタプリタ --CPS変換--> CPSインタプリタ
                   --継続をデータ構造化(EOPL 5.1)--> 継続オブジェクト
                   --トランポリン化(EOPL 5.2)------> Bounce
                   --レジスタ化(EOPL 5.3)---------> CEK機械  ← ここ
```

## CPS版との違い

| | `continuation_passing_interpreter` | `CEK` |
| --- | --- | --- |
| 1ステップの表現 | `eval_cps` / `apply_cont` が**次の関数を呼ぶ** | `eval_step` / `apply_kont` が**次の状態を返すだけ** |
| ホストのスタック | 値を返す側の継続の連鎖ぶんだけ伸びる | 常に一定。`run_machine` の `while` ループだけ |
| 手続き適用 | クロージャ・継続手続きは Bounce を返し、`trampoline` が開封 | `apply_procedure` の1状態遷移。`Bounce` 型自体が不要 |
| トランポリンに戻る頻度 | クロージャ・継続手続きの適用のときだけ | すべての簡約ステップ |
| JITの合流点 | `trampoline` の `while` (greens=`exp` = クロージャ本体) | `run_machine` の `while` (greens=`exp`) |

## ファイル構成

依存は一方向 (`value`/`env`/`state` → `primitives` → `proc` → `cont` → `exp` → `convert` → `machine` → `target`)。

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
| `examples/` | ベンチマーク用の例題 (RPython3imp と同じ) |

## 変換 (convert.py)

- lambda の仮引数・letrec の変数は字句アドレス `(depth, index)` にする。
  実行時はフレームを depth 枚たどって `vals[index]` を読み書きする。
  フレームの要素が仕様書 3.5節の「場所」で、`set!` はここを書き換える。
- define の変数は `GlobalCell` 1 個に解決する。初期値は `UNDEFINED` で、
  参照・`set!` のときに検査する (仕様書 4.7, 5.2節)。
- 標準手続きの名前 (define し直していないもの) は `PrimVal` の定数にする。
  `set!` できないので値は変わらない (仕様書 7.1節の制約 5)。
- プログラム `D* E0` は `DefineExp` の連鎖 1 本にする (仕様書 8.4節 𝒟)。

## 遷移規則

`ρ` = 環境、`κ` = 継続。`<e, ρ, κ>` が Eval状態、`<v, κ>` が Cont状態。

### Eval遷移 (`Exp.eval_step`)

```
<K, ρ, κ>                    -> <𝒦[K], κ>                (標準手続きの名前も定数)
<x, ρ, κ>                    -> <ρ(x), κ>                (define の変数は UNDEFINED ならエラー)
<(lambda (x*) e), ρ, κ>      -> <(closure lambda ρ), κ>
<(if e0 e1 e2), ρ, κ>        -> <e0, ρ, (if e1 e2 ρ κ)>
<(e0 e*), ρ, κ>              -> <e0, ρ, (app e* ⟨⟩ ρ κ)>
<(set! x e), ρ, κ>           -> <e, ρ, (set! x ρ κ)>
<(letrec ((x L)*) e), ρ, κ>  -> <e, ρ', κ>   ρ' = ρ[x*=(closure L* ρ')]
<(define x e) rest, ρ, κ>    -> <e, ρ, (define x rest κ)>
```

### Cont遷移 (`Kont.apply_kont`)

```
<v, (end)>                   -> halt v
<v, (if e1 e2 ρ κ)>          -> <e1, ρ, κ>  (v ≠ #f)  /  <e2, ρ, κ>  (v = #f)
<v, (app e* vs ρ κ)>         -> <e_i, ρ, (app e* vs§⟨v⟩ ρ κ)>    (残りのオペランドがある)
                             -> vs§⟨v⟩ を適用                    (ない)
<v, (set! x ρ κ)>            -> <unspecified, κ>  (x の場所に v を格納)
<v, (define x rest κ)>       -> <rest, (トップ・レベル), κ>  (x の場所に v を格納)
```

### 適用 (`ProcVal.apply_procedure`)

```
(closure (lambda (x*) e) ρ') v*, κ  -> <e, ρ'[x*=v*], κ>       ← β規則
(prim p) v*, κ                      -> <p(v*), κ>
(prim call/cc) f, κ                 -> f (cont κ), κ            (f の呼出しは末尾呼出し)
(cont κ') v, κ                      -> <v, κ'>                  (κ は捨てる)
```

引数の個数違い・手続きでない値の適用は `SchemeError`。

## 使い方

```sh
# CPython3 でテスト
python smoke_test.py

# 状態遷移を目で追う
python demo_trace.py

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

### CPS版との性能比較(2026-09-15 実測, WSL2 Ubuntu 24.04 / gcc 13.3.0)

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
