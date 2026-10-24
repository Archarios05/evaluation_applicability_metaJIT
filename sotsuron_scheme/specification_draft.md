# 基本方針
R5RSのSchemeをベースにする。
そこから機能を削ったものを考える
```
E = Z + M + F (+ Ep)
```

にしたほうがいいかも、つまり整数、雑値、手続き、ペア
→


プリミティブの案（すべて2引数固定）

- 算術：`+` `-` `*` `quotient` `remainder` `modulo`
- 比較：`=` `<` `>` `<=` `>=`
- 述語：`zero?` `not` `eq?`
- `cons` `car` `cdr` `null?` `pair?`
- 出力：`display` `newline`


文字列は要らない？

型→boolean? pair? symbol? number? char? string? vector? port? procedure?

の中からどれかを削る。charとstringとvector消したい

型→boolean? pair? symbol? number?  vecto port? procedure?


<式> ::= <整数> | #t | #f | '()
       | <変数>
       | (lambda (<変数>*) <式>)
       | (if <式> <式> <式>)
       | (letrec ((<変数> (lambda ...))*) <式>)
       | (<式> <式>*)
<プログラム> ::= (define <変数> <式>)* <式>

評価順序→左から右に固定

マクロ？