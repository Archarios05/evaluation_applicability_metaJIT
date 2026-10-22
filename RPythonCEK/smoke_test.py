# -*- coding: utf-8 -*-
# CPython3 用テスト
#   python smoke_test.py
# 例は RPython3imp/smoke_test.py と同じものを使う (実装モデル間で挙動をそろえるため)
import primitives
from convert import convert_program
from reader import ParseError, MAXINT
from syntax import parse_program
from value import SchemeError
from state import HaltState
from machine import run_program, run_states, initial_state


def run_with(text, runner):
    out = []
    primitives.write_out = out.append
    try:
        runner(convert_program(parse_program(text)))
    except (ParseError, SchemeError):
        out.append("error")
    return "".join(out)


def run(text):
    return run_with(text, run_program)


def check(text, expected):
    got = run(text)
    assert got == expected, "%r\n  expected %r\n  got      %r" % (text, expected, got)


SEQ = "(define seq (lambda (a b) b))\n"


def test_constants():
    check("(display 42)", "42")
    check("(display -7)", "-7")
    check("(display #t)", "#t")
    check("(display #f)", "#f")
    check("(display '())", "()")
    check("(display (newline))", "\n#<unspecified>")
    check("(display car)", "#<procedure>")
    check("(display (lambda (x) x))", "#<procedure>")


def test_arith():
    check("(display (+ 1 2))", "3")
    check("(display (- 1 2))", "-1")
    check("(display (* 6 7))", "42")
    for x, y, q, r, m in [(17, 5, 3, 2, 2), (17, -5, -3, 2, -3),
                          (-17, 5, -3, -2, 3), (-17, -5, 3, -2, -2)]:
        check("(display (quotient %d %d))" % (x, y), str(q))
        check("(display (remainder %d %d))" % (x, y), str(r))
        check("(display (modulo %d %d))" % (x, y), str(m))
    check("(display (= 1 1))", "#t")
    check("(display (< 1 2))", "#t")
    check("(display (> 1 2))", "#f")
    check("(display (<= 2 2))", "#t")
    check("(display (>= 1 2))", "#f")
    check("(display (zero? 0))", "#t")


def test_overflow():
    check("(display (+ %d 1))" % MAXINT, "error")
    check("(display (- %d 2))" % (-MAXINT), "error")
    check("(display (* %d 2))" % MAXINT, "error")
    check("(display (quotient (- %d 1) -1))" % (-MAXINT), "error")
    check("(display (remainder (- %d 1) -1))" % (-MAXINT), "0")
    check("(display (+ %d 0))" % MAXINT, str(MAXINT))


def test_predicates():
    check("(display (not #f))", "#t")
    check("(display (not 0))", "#f")
    check("(display (null? '()))", "#t")
    check("(display (pair? (cons 1 2)))", "#t")
    check("(display (eq? 100000 100000))", "#t")
    check("(display (eq? (cons 1 2) (cons 1 2)))", "#f")
    check("(display ((lambda (p) (eq? p p)) (cons 1 2)))", "#t")
    check("(display (eq? car car))", "#t")
    check("(display (eq? '() '()))", "#t")
    check("(display (eq? #f '()))", "#f")
    check("(display (if 0 1 2))", "1")
    check("(display (if '() 1 2))", "1")


def test_display_lists():
    check("(display (cons 1 (cons 2 '())))", "(1 2)")
    check("(display (cons 1 2))", "(1 . 2)")
    check("(display (cons (cons 1 '()) (cons 2 3)))", "((1) 2 . 3)")


def test_spec_examples():
    check("""(define fact
               (lambda (n) (if (= n 0) 1 (* n (fact (- n 1))))))
             (display (fact 10))""", "3628800")
    check(SEQ + "(seq (display 1) (seq (newline) (display 2)))", "1\n2")
    check("""(define sum (lambda (l) (if (null? l) 0 (+ (car l) (sum (cdr l))))))
             (define seq (lambda (a b) b))
             (define xs (cons 1 (cons 2 (cons 3 '()))))
             (seq (display xs) (seq (newline) (display (sum xs))))""", "(1 2 3)\n6")
    check("""(define product
               (lambda (l)
                 (call-with-current-continuation
                   (lambda (return)
                     (letrec ((loop (lambda (l)
                                      (if (null? l) 1
                                          (if (zero? (car l)) (return 0)
                                              (* (car l) (loop (cdr l))))))))
                       (loop l))))))
             (display (product (cons 1 (cons 0 (cons 3 '())))))""", "0")
    check("(display (+ 1 (call-with-current-continuation (lambda (k) (+ 10 (k 2))))))", "3")
    check(SEQ + """((lambda (r)
                      (seq (display (pair? r))
                           (if (pair? r) ((car r) 5) (display r))))
                    (call-with-current-continuation (lambda (k) (cons k '()))))""",
          "#t#f5")


def test_errors():
    check("(display 1) (car '())", "error")      # 主式以外は define のみ
    check("(define x (display 1)) (car '())", "1error")
    check("(+ 1 2 3)", "error")
    check("(quotient 1 0)", "error")
    check("(modulo 1 0)", "error")
    check("(1 2)", "error")
    check("(call-with-current-continuation 1)", "error")
    check("(call-with-current-continuation (lambda (k) (k 1 2)))", "error")
    check("(call-with-current-continuation (lambda () 1))", "error")
    check("(lambda (x x) x)", "error")
    check("(if #t 1)", "error")
    check("(letrec ((x 1)) x)", "error")
    check("y", "error")
    check("((lambda (x) x))", "error")
    check("((lambda (x) x) 1 2)", "error")
    check("((lambda (f) (f 1 2)) (lambda (x) x))", "error")
    check("(car 1)", "error")
    check("(+ 1 #t)", "error")
    check("(newline 1)", "error")


def test_define_order():
    check("(define f (lambda () g)) (define g 1) (display (f))", "1")
    check("(define a b) (define b 2) (display a)", "error")
    check("(define car (lambda (x) 1)) (display (car 5))", "1")
    check("(define f (lambda (x) (car x))) (define car (lambda (x) 7)) (display (f 5))", "7")
    check("(define x (car '())) (define car cdr) 1", "error")


def test_evaluation_order():
    # 演算子を先に、オペランドを左から右へ
    check(SEQ + "((seq (display 1) (lambda (x y) x)) (display 2) (display 3))", "123")
    check("((lambda (a b) b) (display 1) (newline))", "1\n")
    check(SEQ + "((lambda (x) x) (seq (display 1) 0) (display 2))", "12error")


def test_lexical_scope():
    check("(display ((lambda (x) ((lambda (y) ((lambda (z) (+ x (+ y z))) 3)) 2)) 1))", "6")
    check("""(display ((lambda (x) ((lambda (y) ((lambda (f) (f 10))
                                               (lambda (a) (+ y (+ x a)))))
                                    (+ x 3)))
                       2))""", "17")
    check("(display ((lambda (g) (g 10)) ((lambda (x) (lambda (a) (+ x a))) 5)))", "15")
    check("""(define adder (lambda (x) (lambda (y) (lambda (z) (+ x (+ y z))))))
             (display (((adder 1) 20) 300))""", "321")
    check("""(define make-counter
               (lambda (n) (cons (lambda () n) (lambda () (make-counter (+ n 1))))))
             (display ((car ((cdr ((cdr (make-counter 5)))))))) """, "7")
    # 仮引数が外側の同名変数を隠す
    check("(display ((lambda (x) ((lambda (x) x) 2)) 1))", "2")


def test_letrec():
    check("""(letrec ((even? (lambda (n) (if (zero? n) #t (odd? (- n 1)))))
                      (odd? (lambda (n) (if (zero? n) #f (even? (- n 1))))))
               (display (even? 1001)))""", "#f")
    check("(display (letrec () 5))", "5")
    check("""(define f (lambda (x)
               (letrec ((g (lambda (y) (if (zero? y) x (g (- y 1))))))
                 g)))
             (display ((f 42) 10))""", "42")
    check("""(display ((lambda (k)
               (letrec ((loop (lambda (i acc) (if (zero? i) acc (loop (- i 1) (+ acc k))))))
                 (+ k (loop 3 0))))
              10))""", "40")
    check("""(display (letrec ((f (lambda (f) (+ f 1)))) (f 1)))""", "2")


def kont_depth(kont):
    depth = 0
    while hasattr(kont, "kont"):
        kont = kont.kont
        depth += 1
    return depth


def max_kont_depth(text):
    # run_states で 1 ステップずつ進め、継続の長さの最大値を返す
    out = []
    primitives.write_out = out.append
    state = initial_state(convert_program(parse_program(text)))
    deepest = 0
    while not isinstance(state, HaltState):
        deepest = max(deepest, kont_depth(state.kont))
        state = state.step()
    return "".join(out), deepest


def tail_calls_stay_flat(text, expected):
    out, deepest = max_kont_depth(text)
    assert out == expected, (text, out)
    assert deepest < 20, (text, deepest)


def test_tail_calls():
    #  末尾呼出しでは継続が伸びない
    tail_calls_stay_flat("""(letrec ((even? (lambda (n) (if (zero? n) #t (odd? (- n 1)))))
                                     (odd? (lambda (n) (if (zero? n) #f (even? (- n 1))))))
                              (display (even? 10000)))""", "#t")
    tail_calls_stay_flat("""(define loop (lambda (n) (if (zero? n) 0 (loop (- n 1)))))
                            (display (loop 10000))""", "0")
    tail_calls_stay_flat("""(define loop (lambda (n)
                               (if (zero? n) 0 ((lambda (m) ((lambda (k) (loop k)) m)) (- n 1)))))
                            (display (loop 10000))""", "0")
    tail_calls_stay_flat("""(define loop (lambda (n)
                               (if (zero? n) 0
                                   (letrec ((f (lambda () (loop (- n 1))))) (f)))))
                            (display (loop 10000))""", "0")
    tail_calls_stay_flat("""(define loop (lambda (n k)
                               (if (zero? n) (k 7) (loop (- n 1) k))))
                            (display (call-with-current-continuation (lambda (k) (loop 10000 k))))""",
                         "7")
    # 非末尾再帰では伸びる (検査そのものが効いていることの確認)
    out, deepest = max_kont_depth("""(define sum (lambda (n) (if (zero? n) 0 (+ n (sum (- n 1))))))
                                     (display (sum 1000))""")
    assert out == "500500" and deepest >= 1000, deepest


def test_deep_recursion():
    # 継続はヒープ上にあるので、ホストの再帰上限に関係なく深く再帰できる
    check("""(define sum (lambda (n) (if (zero? n) 0 (+ n (sum (- n 1))))))
             (display (sum 100000))""", "5000050000")


def test_callcc():
    check("(display (call-with-current-continuation (lambda (k) 1)))", "1")
    check("(display (call-with-current-continuation (lambda (k) (k 1))))", "1")
    check("(display (call-with-current-continuation call-with-current-continuation))",
          "#<procedure>")
    check("(display ((call-with-current-continuation call-with-current-continuation) (lambda (x) 5)))",
          "5")
    check("(call-with-current-continuation display)", "#<procedure>")
    check("""(display ((lambda (k) (eq? k k))
                       (call-with-current-continuation (lambda (k) k))))""", "#t")
    # 何度でも呼べる継続
    check(SEQ + """((lambda (p)
                      (seq (display (car p))
                           (if (< (car p) 3) ((cdr p) (cons (+ (car p) 1) (cdr p))) 0)))
                    (call-with-current-continuation (lambda (k) (cons 0 k))))""", "0123")
    # 非末尾の深い位置で捕まえた継続に、戻った後で再突入する
    check("""(define sum (lambda (n out)
               (if (zero? n)
                   (call-with-current-continuation (lambda (c) (out (cons c '()))))
                   (+ n (sum (- n 1) out)))))
             ((lambda (r)
                (if (pair? r)
                    ((car r) 100)
                    (display r)))
              (call-with-current-continuation (lambda (out) (sum 10 out))))""", "155")
    # define の途中で捕まえた継続を呼ぶと、以降の define がやり直される
    check(SEQ + """(define r (call-with-current-continuation (lambda (k) (cons 0 k))))
                   (define n (car r))
                   (seq (display n)
                        (if (< n 2) ((cdr r) (cons (+ n 1) (cdr r))) 0))""", "012")
    # 再突入しても途中まで求めたオペランドの値は共有されない
    check("""(display (letrec ((f (lambda (n) (if (zero? n) 0 (+ 1 (f (- n 1)))))))
                (+ (f 3) (call-with-current-continuation (lambda (k) (f (k 10)))))))""", "13")
    check(SEQ + """(define k #f)
                   (define n 0)
                   (define l (cons 1 (call-with-current-continuation (lambda (c) (seq (set! k c) 2)))))
                   (seq (display l)
                        (if (< n 2) (seq (set! n (+ n 1)) (k (* n 10))) 0))""",
          "(1 . 2)(1 . 10)(1 . 20)")
    # 手続きを呼ばずに継続だけで回るループ
    check("""(define n 0)
             (define r (call-with-current-continuation (lambda (k) k)))
             (define d (set! n (+ n 1)))
             (if (< n 10000) (r r) (display n))""", "10000")


def test_set():
    check(SEQ + "(define x 1) (seq (set! x (+ x 1)) (display x))", "2")
    check(SEQ + """(define make-counter
                     (lambda (n) (lambda () (seq (set! n (+ n 1)) n))))
                   (define c1 (make-counter 0))
                   (define c2 (make-counter 100))
                   (seq (display (c1)) (seq (display (c1)) (seq (display (c2)) (display (c1)))))""",
          "121013")
    check("(define x 1) (display (set! x 2))", "#<unspecified>")
    check("(display ((lambda (x) (set! x 2)) 1))", "#<unspecified>")
    check(SEQ + "(define f (lambda (x) (seq (set! x (* x 10)) x))) (display (f 4))", "40")
    check(SEQ + "(display ((lambda (x) (seq (set! x 5) x)) 1))", "5")
    check(SEQ + """(display ((lambda (x)
                                ((lambda (y) (seq (set! x (+ x y)) x)) 10))
                              1))""", "11")
    check(SEQ + """(display ((lambda (x)
                                ((lambda (get)
                                   (seq (set! x 2) (+ (get) ((lambda () x)))))
                                 (lambda () x)))
                              1))""", "4")
    check(SEQ + """(define pair (lambda (x) (cons (lambda () x) (lambda (v) (set! x v)))))
                   (define p (pair 1))
                   (seq ((cdr p) 42) (display ((car p))))""", "42")
    check(SEQ + """(display (letrec ((f (lambda () 1)))
                                (seq (set! f (lambda () 2)) (f))))""", "2")
    check(SEQ + """(define n 0)
                   (define inc (lambda () (set! n (+ n 1))))
                   (seq (inc) (seq (inc) (display n)))""", "2")
    check(SEQ + "(define car cdr) (seq (set! car (lambda (x) 9)) (display (car 1)))", "9")
    check(SEQ + """(display ((lambda (x)
                                (seq ((lambda (x) (set! x 100)) 0) x))
                              1))""", "1")
    check("(define f (lambda (x) (set! x 1))) (display (f 0))", "#<unspecified>")
    check("(define g 0) (define f (lambda () (set! g 1))) (display (f))", "#<unspecified>")
    check(SEQ + """(define acc 0)
                   (define loop (lambda (i)
                                  (if (zero? i) acc
                                      (seq (set! acc (+ acc i)) (loop (- i 1))))))
                   (display (loop 100000))""", "5000050000")
    # 継続で戻っても、変数の場所の値は巻き戻らない
    check(SEQ + """(define k #f)
                   (display ((lambda (x)
                               (seq (call-with-current-continuation (lambda (c) (set! k c)))
                                    (seq (set! x (+ x 1))
                                         (if (< x 3) (k 0) x))))
                             0))""", "3")
    check("(define a (set! b 1)) (define b 2) b", "error")
    check("(define a (set! b (display 1))) (define b 2) b", "1error")
    check("(set! car cdr)", "error")
    check("(set! z 1)", "error")


def test_run_states_agrees():
    # run_machine (JIT 用) と run_states (教科書どおり) は同じ出力を返す
    def by_states(exp):
        return run_states(initial_state(exp))

    for text in ["""(define fib (lambda (n) (if (< n 2) n (+ (fib (- n 1)) (fib (- n 2))))))
                    (display (fib 15))""",
                 SEQ + """((lambda (p)
                             (seq (display (car p))
                                  (if (< (car p) 3) ((cdr p) (cons (+ (car p) 1) (cdr p))) 0)))
                           (call-with-current-continuation (lambda (k) (cons 0 k))))""",
                 "(display (cons 1 (cons #t '())))",
                 "(car '())"]:
        assert run_with(text, run_program) == run_with(text, by_states), text


TESTS = [test_constants, test_arith, test_overflow, test_predicates, test_display_lists,
         test_spec_examples, test_errors, test_define_order, test_evaluation_order,
         test_lexical_scope, test_letrec, test_tail_calls, test_deep_recursion,
         test_callcc, test_set, test_run_states_agrees]

if __name__ == "__main__":
    for t in TESTS:
        t()
        print("ok " + t.__name__)
    print("all smoke tests passed")
