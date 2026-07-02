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
)
from interpreter import value_of_program
from classes import expval_to_num


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
    return 0


def target(*args):
    return entry_point, None


if __name__ == "__main__":
    import sys
    entry_point(sys.argv)
