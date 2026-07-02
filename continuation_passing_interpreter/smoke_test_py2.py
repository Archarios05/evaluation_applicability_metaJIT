# -*- coding: utf-8 -*-
# smoke_test.py のPython2版。RPython翻訳の前段階として、
# CPython2でもインタプリタの挙動が変わらないことを確認するための開発用スクリプト。
# (Python3専用構文は使わない: from __future__ import annotations 等は書かない)
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
from classes import NumVal


def check(name, exp, expected_num):
    result = value_of_program(exp)
    assert isinstance(result, NumVal), "%s: NumVal ではない結果 %r" % (name, result)
    assert result.num == expected_num, "%s: 期待値 %r, 実際 %r" % (
        name,
        expected_num,
        result.num,
    )
    print "OK: %s => %d" % (name, result.num)


def test_diff_var():
    exp = DiffExp(
        DiffExp(VarExp("x"), ConstExp(3)),
        DiffExp(VarExp("v"), VarExp("i")),
    )
    check("diff_var", exp, 3)


def test_let():
    exp = LetExp("x", ConstExp(5), DiffExp(VarExp("x"), ConstExp(3)))
    check("let", exp, 2)


def test_if_zero():
    exp = IfExp(ZeroExp(DiffExp(VarExp("x"), VarExp("x"))), ConstExp(1), ConstExp(2))
    check("if_zero", exp, 1)


def test_proc_call():
    exp = LetExp(
        "f",
        ProcExp("x", DiffExp(VarExp("x"), ConstExp(11))),
        CallExp(VarExp("f"), CallExp(VarExp("f"), ConstExp(77))),
    )
    check("proc_call", exp, 55)


def test_letrec():
    body = IfExp(
        ZeroExp(VarExp("x")),
        ConstExp(0),
        DiffExp(
            CallExp(VarExp("double"), DiffExp(VarExp("x"), ConstExp(1))),
            ConstExp(-2),
        ),
    )
    exp = LetRecExp("double", "x", body, CallExp(VarExp("double"), ConstExp(5)))
    check("letrec", exp, 10)


if __name__ == "__main__":
    test_diff_var()
    test_let()
    test_if_zero()
    test_proc_call()
    test_letrec()
    print "all smoke tests passed (python2)"
