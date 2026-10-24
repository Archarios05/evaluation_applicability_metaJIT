# -*- coding: utf-8 -*-
# パーサのスモークテスト (CPython3 でそのまま実行できる)。
#   python smoke_test.py
from reader import ParseError, read_all, MAXINT
from syntax import (
    parse_program,
    IntExp,
    BoolExp,
    NilExp,
    VarExp,
    LambdaExp,
    IfExp,
    LetrecExp,
    SetExp,
    AppExp,
)


def parse_exp_text(text):
    return parse_program(text).body


def assert_error(text):
    try:
        parse_program(text)
    except ParseError:
        return
    raise AssertionError("expected ParseError: %r" % (text,))


def test_constants():
    assert parse_exp_text("42").value == 42
    assert parse_exp_text("-7").value == -7
    assert parse_exp_text("+7").value == 7
    assert parse_exp_text("#t").value is True
    assert parse_exp_text("#F").value is False
    assert isinstance(parse_exp_text("'()"), NilExp)
    assert isinstance(parse_exp_text("' ( )"), NilExp)


def test_integer_range():
    assert parse_exp_text(str(MAXINT)).value == MAXINT
    assert parse_exp_text(str(-MAXINT)).value == -MAXINT
    assert_error(str(MAXINT + 1))


def test_identifiers():
    e = parse_exp_text("(+ 1 2)")
    assert isinstance(e, AppExp) and e.rator.name == "+"
    assert parse_exp_text("(- 1 2)").rator.name == "-"
    assert parse_exp_text("(define ... 1) ...").name == "..."
    assert parse_exp_text("(define a->b? 1) a->b?").name == "a->b?"
    assert parse_exp_text("(define x+1 1) x+1").name == "x+1"


def test_case_insensitive():
    p = parse_program("(define Fact 1) (DISPLAY fact)")
    assert p.defines[0].name == "fact"
    assert p.body.rator.name == "display"
    assert isinstance(parse_exp_text("(LAMBDA (X) x)"), LambdaExp)


def test_comments_and_whitespace():
    e = parse_exp_text("; comment\r\n(car\t; c\n (cons 1 2))  ; end")
    assert e.to_string() == "(car (cons 1 2))"


def test_lambda():
    e = parse_exp_text("(lambda (x y) (+ x y))")
    assert isinstance(e, LambdaExp)
    assert e.params == ["x", "y"]
    assert isinstance(e.body, AppExp)
    assert parse_exp_text("(lambda () 1)").params == []


def test_if():
    e = parse_exp_text("(if #t 1 2)")
    assert isinstance(e, IfExp)
    assert isinstance(e.test, BoolExp)
    assert e.conseq.value == 1 and e.alt.value == 2


def test_letrec():
    e = parse_exp_text(
        "(letrec ((even? (lambda (n) (if (zero? n) #t (odd? (- n 1)))))"
        "         (odd?  (lambda (n) (if (zero? n) #f (even? (- n 1))))))"
        "  (even? 10))")
    assert isinstance(e, LetrecExp)
    assert e.names == ["even?", "odd?"]
    assert len(e.lambdas) == 2 and isinstance(e.lambdas[0], LambdaExp)
    assert parse_exp_text("(letrec () 1)").names == []


def test_set():
    e = parse_exp_text("(lambda (x) (set! x (+ x 1)))")
    assert isinstance(e.body, SetExp)
    assert e.body.name == "x"
    assert e.body.to_string() == "(set! x (+ x 1))"
    # letrec の変数、define の変数、定義し直した標準手続きの名前には代入できる
    parse_program("(letrec ((f (lambda () 1))) (set! f 2))")
    parse_program("(define x 1) (set! x 2)")
    parse_program("(define car 1) (set! car 2)")
    parse_program("(define f (lambda () (set! x 1))) (define x 0) (f)")
    parse_program("(lambda (car) (set! car 1))")
    # 4.7 節の例
    parse_program("(define seq (lambda (a b) b)) (define x 1)"
                  "(seq (set! x (+ x 1)) (display x))")


def test_program():
    p = parse_program(
        "(define fact\n"
        "  (lambda (n)\n"
        "    (if (= n 0)\n"
        "        1\n"
        "        (* n (fact (- n 1))))))\n"
        "(display (fact 10))\n")
    assert len(p.defines) == 1
    assert p.defines[0].name == "fact"
    assert p.to_string() == (
        "(define fact (lambda (n) (if (= n 0) 1 (* n (fact (- n 1))))))\n"
        "(display (fact 10))")


def test_forward_reference_and_shadowing():
    p = parse_program("(define f (lambda () g)) (define g 1) (define car 2) (f)")
    assert len(p.defines) == 3
    e = parse_exp_text("(lambda (car) car)")
    assert isinstance(e.body, VarExp)


def test_spec_examples():
    parse_program("(define seq (lambda (a b) b))"
                  "(seq (display 1) (seq (newline) (display 2)))")
    parse_program("(define sum (lambda (l) (if (null? l) 0 (+ (car l) (sum (cdr l))))))"
                  "(define seq (lambda (a b) b))"
                  "(define xs (cons 1 (cons 2 (cons 3 '()))))"
                  "(seq (display xs) (seq (newline) (display (sum xs))))")
    parse_program("(define seq (lambda (a b) b))"
                  "(define make-counter (lambda (n) (lambda () (seq (set! n (+ n 1)) n))))"
                  "(define c1 (make-counter 0)) (define c2 (make-counter 100))"
                  "(seq (display (c1)) (seq (display (c1)) (seq (display (c2)) (display (c1)))))")
    # 10.7 の実行時エラーの例は構文としては正しい
    for text in ["(car '())", "(+ 1 2 3)", "(quotient 1 0)", "(1 2)",
                 "(call-with-current-continuation 1)",
                 "(call-with-current-continuation (lambda (k) (k 1 2)))",
                 "(define a (set! b 1)) (define b 2) b"]:
        parse_program(text)


def test_static_errors():
    # 10.7 の実行前エラーの例
    assert_error("(lambda (x x) x)")
    assert_error("(if #t 1)")
    assert_error("(letrec ((x 1)) x)")
    assert_error("y")
    assert_error("(set! car cdr)")
    assert_error("(set! z 1)")
    # 7.1 節の制約
    assert_error("(letrec ((f (lambda () 1)) (f (lambda () 2))) 1)")
    assert_error("(define a 1) (define a 2) a")
    assert_error("(lambda (x) y)")
    assert_error("(define f (lambda () x)) (letrec ((x (lambda () 1))) x)")
    assert_error("(define f (lambda () (set! x 1))) (letrec ((x (lambda () 1))) x)")
    assert_error("(lambda (x) (set! display x))")


def test_syntax_errors():
    for text in [
        "",
        "; only comment",
        "(define x 1)",
        "1 2",
        "(define x 1) 2 (define y 2) y",
        "()",
        "(lambda x x)",
        "(lambda (x) x x)",
        "(lambda (1) 1)",
        "(if 1 2 3 4)",
        "(letrec ((f (lambda () 1))))",
        "(letrec (f (lambda () 1)) 1)",
        "(letrec ((f)) 1)",
        "(define x)",
        "(define 1 2) 1",
        "(display (define x 1))",
        "(quote ())",
        "'a",
        "'(1 2)",
        "'1",
        "(let ((x 1)) x)",
        "(begin 1)",
        "(define else 1) 1",
        "(lambda (if) 1)",
        "(define x 1) (set! x)",
        "(define x 1) (set! x 1 2)",
        "(set! 1 2)",
        "(set! (car x) 1)",
        "(lambda (set!) 1)",
        "else",
    ]:
        assert_error(text)


def test_lexical_errors():
    for text in [
        "(+ 1 2",
        "(+ 1 2))",
        ")",
        "\"str\"",
        "#\\a",
        "#(1 2)",
        "#true",
        "#",
        "`()",
        "(cons 1 . 2)",
        ".",
        "..",
        "1.5",
        "12abc",
        "+a",
        "-x",
        "(define a' 1) 1",
        "#x10",
        "[1]",
        "{}",
        "|a|",
    ]:
        assert_error(text)


def test_call_cc():
    # 6.7 節, 10.5 節
    e = parse_exp_text(
        "(display (+ 1 (call-with-current-continuation (lambda (k) (+ 10 (k 2))))))")
    assert e.rands[0].rands[1].rator.name == "call-with-current-continuation"
    parse_program("(define seq (lambda (a b) b))"
                  "((lambda (r)"
                  "   (seq (display (pair? r))"
                  "        (if (pair? r) ((car r) 5) (display r))))"
                  " (call-with-current-continuation (lambda (k) (cons k '()))))")
    parse_program("(define product"
                  "  (lambda (l)"
                  "    (call-with-current-continuation"
                  "      (lambda (return)"
                  "        (letrec ((loop (lambda (l)"
                  "                         (if (null? l)"
                  "                             1"
                  "                             (if (zero? (car l))"
                  "                                 (return 0)"
                  "                                 (* (car l) (loop (cdr l))))))))"
                  "          (loop l))))))"
                  "(display (product (cons 1 (cons 0 (cons 3 '())))))")
    assert parse_exp_text("(CALL-WITH-CURRENT-CONTINUATION car)").rator.name ==         "call-with-current-continuation"
    p = parse_program("(define call/cc call-with-current-continuation) (call/cc car)")
    assert p.body.rator.name == "call/cc"
    # call/cc という別名は持たない (6.7 節)
    assert_error("(call/cc (lambda (k) (k 1)))")


def test_reader():
    data = read_all("(a (b 1) '() #t)")
    assert len(data) == 1
    assert data[0].to_string() == "(a (b 1) '() #t)"


if __name__ == "__main__":
    test_constants()
    test_integer_range()
    test_identifiers()
    test_case_insensitive()
    test_comments_and_whitespace()
    test_lambda()
    test_if()
    test_letrec()
    test_set()
    test_program()
    test_forward_reference_and_shadowing()
    test_spec_examples()
    test_static_errors()
    test_syntax_errors()
    test_lexical_errors()
    test_call_cc()
    test_reader()
    print("all tests passed")
