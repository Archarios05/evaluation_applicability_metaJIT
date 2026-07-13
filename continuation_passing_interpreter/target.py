# -*- coding: utf-8 -*-
# RPython翻訳のためのentry_point/target定義。
#
# テキストソースをASTに変換するフロントエンド(パーサ)はまだ無いため、
# ここでは smoke_test.py と同じ手組みの構文木(AST)を直接Pythonコードとして
# 組み立て、value_of_program に渡して評価する。
#
# 使い方(WSL上、Python2 + rpythonツールチェイン):
#   python2 pypy/rpython/bin/rpython continuation_passing_interpreter/target.py
# で単体の実行ファイルが生成される(JITなし、まずは翻訳が通ることの確認)。
import os
from exp_representation import (
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
from interpreter import value_of_program
from classes import expval_to_num
#build_xxxはASTを組み立ててる


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


def entry_point(argv):
    run_one("diff_var", build_diff_var())
    run_one("let", build_let())
    run_one("if_zero", build_if_zero())
    run_one("proc_call", build_proc_call())
    run_one("letrec", build_letrec())
    # 注記: このCPS評価器はトランポリン化していないため、EndContに到達するまで
    # ホストのコールスタックが縮まない。fib_sequence(n)の合計呼び出し回数は
    # O(fib(n))で増えるため、nを大きくしすぎるとRPython翻訳後もCスタックを
    # 使い果たしてクラッシュする(手元ではn=20でスタックオーバーフローを確認)。
    run_one("fib_sequence", build_fib_sequence(12))
    return 0


def target(*args):
    return entry_point, None


def jitpolicy(driver):
    from rpython.jit.codewriter.policy import JitPolicy
    return JitPolicy()


if __name__ == "__main__":
    import sys
    entry_point(sys.argv)
