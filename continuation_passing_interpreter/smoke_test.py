from __future__ import annotations
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
    print("OK: %s => %d" % (name, result.num))


def test_diff_var():
    # EOPL fig 3.3: -(-(x,3), -(v,i))  in [i=1,v=5,x=10] => 3
    exp = DiffExp(
        DiffExp(VarExp("x"), ConstExp(3)),
        DiffExp(VarExp("v"), VarExp("i")),
    )
    check("diff_var", exp, 3)


def test_let():
    # let x = 5 in -(x,3) => 2
    exp = LetExp("x", ConstExp(5), DiffExp(VarExp("x"), ConstExp(3)))
    check("let", exp, 2)


def test_if_zero():
    # if zero?(-(x,x)) then 1 else 2 => 1  (初期環境の x=10 を利用)
    exp = IfExp(ZeroExp(DiffExp(VarExp("x"), VarExp("x"))), ConstExp(1), ConstExp(2))
    check("if_zero", exp, 1)


def test_proc_call():
    # EOPL p75: let f = proc (x) -(x,11) in (f (f 77)) => 55
    exp = LetExp(
        "f",
        ProcExp("x", DiffExp(VarExp("x"), ConstExp(11))),
        CallExp(VarExp("f"), CallExp(VarExp("f"), ConstExp(77))),
    )
    check("proc_call", exp, 55)


def test_letrec():
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
    exp = LetRecExp("double", "x", body, CallExp(VarExp("double"), ConstExp(5)))
    check("letrec", exp, 10)


if __name__ == "__main__":
    test_diff_var()
    test_let()
    test_if_zero()
    test_proc_call()
    test_letrec()
    print("all smoke tests passed")
