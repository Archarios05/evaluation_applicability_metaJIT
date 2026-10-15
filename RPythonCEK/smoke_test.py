# -*- coding: utf-8 -*-
# CEK機械のスモークテスト(CPython3でそのまま実行できる)。
#   python smoke_test.py
#
# continuation_passing_interpreter/smoke_test.py と同じ例題に加えて、
# 「ホストの再帰上限を一切いじらずに深い再帰が回る」ことを確認する。
# CPS版は sys.setrecursionlimit(1000000) が必要だったが、CEK機械は
# すべての遷移が run_machine のwhileループなのでその必要がない。
import os

# cont.py の os.write は RPython(Python2, str==bytes)を前提に
# strをそのまま渡す。CPython3でこのテストを動かすためだけの互換シム
# (RPython翻訳対象のファイルは一切変更しない)。
_orig_os_write = os.write


def _os_write_compat(fd, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return _orig_os_write(fd, data)


os.write = _os_write_compat

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
)
from machine import value_of_program, run_states, initial_state
from value import NumVal
from target import build_fib_sequence, build_countdown, build_sum_to


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


def test_fib_sequence():
    # fib(0), fib(1), ..., fib(n) を昇順に出力し、最終値は fib(n) になる。
    n = 12
    expected = [0, 1]
    while len(expected) <= n:
        expected.append(expected[-1] + expected[-2])
    check("fib_sequence", build_fib_sequence(n), expected[n])


def test_deep_tail_recursion():
    # 末尾呼び出し100000回。継続もホストスタックも伸びない。
    # (sys.setrecursionlimit を触っていないことが本質。)
    check("countdown(100000)", build_countdown(100000), 0)


def test_deep_non_tail_recursion():
    # 非末尾再帰20000段。継続はヒープ上に20000段積まれるが、
    # ホストの呼び出しスタックは一定なので RecursionError にならない。
    n = 20000
    check("sum_to(%d)" % n, build_sum_to(n), n * (n + 1) // 2)


def test_run_states_agrees():
    # 教科書どおりの1状態ずつのドライバ(run_states)と、
    # レジスタ化した run_machine が同じ答えを出すことを確認する。
    exp = LetExp("x", ConstExp(5), DiffExp(VarExp("x"), ConstExp(3)))
    result = run_states(initial_state(exp))
    assert isinstance(result, NumVal) and result.num == 2
    print("OK: run_states == run_machine")


if __name__ == "__main__":
    test_diff_var()
    test_let()
    test_if_zero()
    test_proc_call()
    test_letrec()
    test_fib_sequence()
    test_deep_tail_recursion()
    test_deep_non_tail_recursion()
    test_run_states_agrees()
    print("all smoke tests passed")
