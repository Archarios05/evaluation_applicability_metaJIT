# s-reader

`../sotsuron_scheme/specification.md` の言語のパーサ。RPython (Python2 サブセット) で書いてあり、CPython3 でも動く。

## ファイル

| ファイル | 中身 |
| --- | --- |
| `reader.py` | 字句解析 + S式リーダー (仕様書 2章)。テキスト → `Datum` の列 |
| `syntax.py` | `Datum` → 構文木 + 静的検査 (仕様書 7章, 7.1節) |
| `target.py` | 翻訳確認用。ファイルを構文解析して構文木を表示する |
| `smoke_test.py` | CPython3 用テスト|

## 使い方

```python
from reader import ParseError
from syntax import parse_program

try:
    program = parse_program(text)   # syntax.Program
except ParseError as e:
    ...                             # e.msg に理由。利用者には "error" とだけ出す (9.1節)
```

構文木はインタプリタの実装モデルに依存しない。各インタプリタ (CEK, CPS など) は
これを自分の `Exp` に変換して使う。

| クラス | フィールド |
| --- | --- |
| `Program` | `defines: [Define]`, `body: Exp` |
| `Define` | `name: str`, `exp: Exp` |
| `IntExp` / `BoolExp` | `value` |
| `NilExp` | (なし) — `'()` |
| `VarExp` | `name: str` |
| `LambdaExp` | `params: [str]`, `body: Exp` |
| `IfExp` | `test`, `conseq`, `alt` |
| `SetExp` | `name: str`, `exp: Exp` — `(set! name exp)` |
| `LetrecExp` | `names: [str]`, `lambdas: [LambdaExp]`, `body: Exp` |
| `AppExp` | `rator: Exp`, `rands: [Exp]` |

識別子は小文字に正規化済み。標準手続きの名前一覧は `syntax.PRIMITIVES`。

## 実行前に検出するエラー

- 字句エラー (文字列・文字・ベクタ・ドット・`#x` など、区切り文字の欠落)
- 構文エラー (BNF に合わない形、`'()` 以外の quote、トップ・レベル以外の `define`、主式の欠落)
- 構文キーワード (R5RS のものすべて) を変数として使う
- 仮引数・letrec 変数・define の重複 (7.1節 1〜3)
- 未束縛変数 (7.1節 4)
- 未束縛変数・標準手続きの名前 (定義し直していないもの) への `set!` (7.1節 5)
- 固定長整数 (`sys.maxint`) に収まらない整数リテラル (9.2節の実装制限)

## テストと翻訳

```sh
python smoke_test.py

# WSL
python2 ~/research/effect-jit-artifact/rpyeffect-jit/pypy/rpython/bin/rpython --opt=2 --output=parser-c target.py
./parser-c prog.scm
```
