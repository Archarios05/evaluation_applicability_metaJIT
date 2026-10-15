# -*- coding: utf-8 -*-
# RPython翻訳のための entry_point / target 定義。
#
# テキストソースをASTに変換するフロントエンド(パーサ)はまだ無いため、
# ここでは手組みの構文木(AST)を直接Pythonコードとして組み立て、
# value_of_program に渡して評価する
# (continuation_passing_interpreter/target.py と同じ例題を使う。
#  同じプログラムを両方で走らせて挙動・性能を比べられるようにするため)。
#
# 使い方(WSL上、Python2 + rpythonツールチェイン):
#   python2 pypy/rpython/bin/rpython CEK/target.py            # JITなし
#   python2 pypy/rpython/bin/rpython --opt=jit CEK/target.py  # JITあり
import os
from exp import (
    ConstExp,
    VarExp,
    DiffExp,
    ZeroExp,
    IfExp,
    LetExp,
    ProcExp,
    CallExp,
    LetRecExp,
    PrintExp,
)
from machine import value_of_program
from value import expval_to_num


def build_diff_var():
    # EOPL fig 3.3: -(-(x,3), -(v,i))  in [i=1,v=5,x=10] => 3
    return DiffExp(
        DiffExp(VarExp("x"), ConstExp(3)),
        DiffExp(VarExp("v"), VarExp("i")),
    )


def build_let():
    # let x = 5 in -(x,3) => 2
    return LetExp("x", ConstExp(5), DiffExp(VarExp("x"), ConstExp(3)))


def build_if_zero():
    # if zero?(-(x,x)) then 1 else 2 => 1
    return IfExp(ZeroExp(DiffExp(VarExp("x"), VarExp("x"))), ConstExp(1), ConstExp(2))


def build_proc_call():
    # EOPL p75: let f = proc (x) -(x,11) in (f (f 77)) => 55
    return LetExp(
        "f",
        ProcExp("x", DiffExp(VarExp("x"), ConstExp(11))),
        CallExp(VarExp("f"), CallExp(VarExp("f"), ConstExp(77))),
    )


def build_letrec():
    # letrec double(x) = if zero?(x) then 0 else -((double -(x,1)), -2)
    # in (double 5) => 10
    body = IfExp(
        ZeroExp(VarExp("x")),
        ConstExp(0),
        DiffExp(
            CallExp(VarExp("double"), DiffExp(VarExp("x"), ConstExp(1))),
            ConstExp(-2),
        ),
    )
    return LetRecExp("double", "x", body, CallExp(VarExp("double"), ConstExp(5)))


def build_add(exp1, exp2):
    # このEOPLサブセットには加算(add-exp)が無いため、-(exp1, -(0, exp2)) で代用する。
    return DiffExp(exp1, DiffExp(ConstExp(0), exp2))


def build_countdown(n):
    # letrec loop(i) = if zero?(i) then 0 else (loop -(i,1)) in (loop n)
    # 末尾呼び出しなので継続は伸びない。CEK機械が「継続もホストスタックも
    # 一定サイズのまま」ループを回せることの確認用。
    loop_body = IfExp(
        ZeroExp(VarExp("i")),
        ConstExp(0),
        CallExp(VarExp("loop"), DiffExp(VarExp("i"), ConstExp(1))),
    )
    return LetRecExp("loop", "i", loop_body, CallExp(VarExp("loop"), ConstExp(n)))


def build_sum_to(n):
    # letrec sum(i) = if zero?(i) then 0 else -(i, -(0, (sum -(i,1)))) in (sum n)
    # 非末尾再帰なので継続(Diff2Kont)がn段積まれる。
    # ただし積まれるのはヒープ上の継続だけで、ホストの呼び出しスタックは一定。
    sum_body = IfExp(
        ZeroExp(VarExp("i")),
        ConstExp(0),
        build_add(VarExp("i"), CallExp(VarExp("sum"), DiffExp(VarExp("i"), ConstExp(1)))),
    )
    return LetRecExp("sum", "i", sum_body, CallExp(VarExp("sum"), ConstExp(n)))


def build_fib_sequence(n):
    # letrec fib(k) = if zero?(k) then 0
    #                 else if zero?(-(k,1)) then 1
    #                 else fib(-(k,1)) + fib(-(k,2))
    # in letrec loop(i) = if zero?(-(n,i)) then print(fib(i))
    #                      else let _ = print(fib(i)) in (loop -(i,-1))
    #    in (loop 0)
    # fib(0), fib(1), ..., fib(n) を昇順にPrintExpで出力する式木。
    fib_body = IfExp(
        ZeroExp(VarExp("k")),
        ConstExp(0),
        IfExp(
            ZeroExp(DiffExp(VarExp("k"), ConstExp(1))),
            ConstExp(1),
            build_add(
                CallExp(VarExp("fib"), DiffExp(VarExp("k"), ConstExp(1))),
                CallExp(VarExp("fib"), DiffExp(VarExp("k"), ConstExp(2))),
            ),
        ),
    )

    print_fib_i = PrintExp(CallExp(VarExp("fib"), VarExp("i")))
    # -(i, -1) = i - (-1) = i + 1 で昇順にインクリメントする。
    next_i = DiffExp(VarExp("i"), ConstExp(-1))
    loop_body = IfExp(
        ZeroExp(DiffExp(ConstExp(n), VarExp("i"))),
        print_fib_i,
        LetExp("_", print_fib_i, CallExp(VarExp("loop"), next_i)),
    )

    return LetRecExp(
        "fib",
        "k",
        fib_body,
        LetRecExp("loop", "i", loop_body, CallExp(VarExp("loop"), ConstExp(0))),
    )


def run_one(name, exp):
    result = value_of_program(exp)
    num = expval_to_num(result)
    os.write(1, name)
    os.write(1, " => ")
    os.write(1, str(num))
    os.write(1, "\n")


def parse_int(s):
    # RPythonでも確実に動く整数パーサ(int(str)の可否に依存しないため自前で書く)。
    i = 0
    neg = False
    if len(s) > 0 and s[0] == "-":
        neg = True
        i = 1
    if i >= len(s):
        raise ValueError("not a number: %s" % (s,))
    result = 0
    while i < len(s):
        c = s[i]
        if c < "0" or c > "9":
            raise ValueError("not a number: %s" % (s,))
        result = result * 10 + (ord(c) - ord("0"))
        i += 1
    if neg:
        return -result
    return result


def bench(name, n):
    # ベンチマーク用: 1つのプログラムだけをn指定で走らせる。
    # JITのウォームアップ代を取り返せるかを見たいので、他の例題は混ぜない。
    if name == "countdown":
        run_one("countdown", build_countdown(n))
        return 0
    if name == "sum":
        run_one("sum_to", build_sum_to(n))
        return 0
    if name == "fib":
        run_one("fib_sequence", build_fib_sequence(n))
        return 0
    os.write(2, "unknown benchmark: %s (countdown|sum|fib)\n" % (name,))
    return 1


def entry_point(argv):
    # 引数ありならベンチマークモード:  ./target-c countdown 50000000
    if len(argv) >= 3:
        return bench(argv[1], parse_int(argv[2]))

    run_one("diff_var", build_diff_var())
    run_one("let", build_let())
    run_one("if_zero", build_if_zero())
    run_one("proc_call", build_proc_call())
    run_one("letrec", build_letrec())
    # 手続き呼び出しも継続の適用もすべて run_machine のwhileループ内の
    # 状態遷移なので、呼び出し回数がいくら増えてもホストのスタックは一定。
    run_one("countdown", build_countdown(1000000))
    run_one("sum_to", build_sum_to(100000))
    run_one("fib_sequence", build_fib_sequence(10))
    return 0


def target(*args):
    return entry_point, None


def jitpolicy(driver):
    from rpython.jit.codewriter.policy import JitPolicy
    return JitPolicy()


if __name__ == "__main__":
    import sys
    entry_point(sys.argv)
