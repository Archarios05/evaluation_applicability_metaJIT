# -*- coding: utf-8 -*-
# EOPL p161 図5.8の even/odd (相互末尾再帰) をモデルにしたストレステスト。
#
# 本実装のLETREC(exp_representation.LetRecExp)は「1つの名前だけを自分自身に
# 再帰束縛する」教科書どおりの最小構成であり、letrec*のような複数手続きの
# 同時相互束縛はサポートしていない。そのため even/odd のように2つの手続きが
# お互いの名前を直接参照し合う形はそのままでは書けない。
#
# 代わりに、単一の自己再帰手続き self_gen(flag) が
#   flag == 0 のとき「even」として振る舞う proc(n) を、
#   flag != 0 のとき「odd」として振る舞う proc(n) を
# その場で構築して返す、という一段のインダイレクションを挟むことで、
# 「呼び出しのたびに異なるProcValオブジェクト(even用/odd用)が交互に
#  apply_procedure_k に渡される」という、図5.8のeven/oddと同じ本質的な
# ストレス(手続きの"同一性"が呼び出しごとに切り替わる相互再帰)を再現する。
#
#   letrec self_gen(flag) =
#     if zero?(flag)
#     then proc (n) if zero?(n) then 1 else ((self_gen 1) -(n,1))   # even
#     else proc (n) if zero?(n) then 0 else ((self_gen 0) -(n,1))   # odd
#   in let odd_fn = (self_gen 1)
#      in (odd_fn N)
#
# EOPLのeven/oddの定義 (p161) をそのまま踏襲しているので、結果は N mod 2 になる
# (Nが奇数なら1、偶数なら0)。
#
# ここで検証したいのは:
#   1. 手続き呼び出しのたびに"新しいProcValインスタンス"が生成・適用されても
#      (interpreter.trampoline の jitdriver.jit_merge_point(greens=['proc'], ...) が
#       前提とする「同じ手続きの繰り返し」が崩れる状況でも)、
#      Pythonの再帰上限を極端に下げてもクラッシュしないこと
#      (=トランポリンがCスタックではなくwhileループでループを回している証拠)。
#   2. 計算結果がEOPLのeven/odd定義と一致すること(トランポリン化で計算の
#      意味が壊れていないこと)。
import sys
import os

# cont_representation.py の os.write は RPython(Python2, str==bytes)を前提に
# strをそのまま渡す。CPython3でこのテストを動かすためだけの互換シム
# (RPython翻訳対象のファイルは一切変更しない)。
_orig_os_write = os.write


def _os_write_compat(fd, data):
    if isinstance(data, str):
        data = data.encode("ascii")
    return _orig_os_write(fd, data)


os.write = _os_write_compat

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


def build_mutual_even_odd(n):
    # letrec self_gen(flag) = if zero?(flag) then <even> else <odd>
    even_proc = ProcExp(
        "n",
        IfExp(
            ZeroExp(VarExp("n")),
            ConstExp(1),
            CallExp(
                CallExp(VarExp("self_gen"), ConstExp(1)),  # (self_gen 1) -> odd
                DiffExp(VarExp("n"), ConstExp(1)),
            ),
        ),
    )
    odd_proc = ProcExp(
        "n",
        IfExp(
            ZeroExp(VarExp("n")),
            ConstExp(0),
            CallExp(
                CallExp(VarExp("self_gen"), ConstExp(0)),  # (self_gen 0) -> even
                DiffExp(VarExp("n"), ConstExp(1)),
            ),
        ),
    )
    self_gen_body = IfExp(ZeroExp(VarExp("flag")), even_proc, odd_proc)

    return LetRecExp(
        "self_gen",
        "flag",
        self_gen_body,
        LetExp(
            "odd_fn",
            CallExp(VarExp("self_gen"), ConstExp(1)),
            CallExp(VarExp("odd_fn"), ConstExp(n)),
        ),
    )


def check(name, exp, expected_num):
    result = value_of_program(exp)
    assert isinstance(result, NumVal), "%s: NumVal ではない結果 %r" % (name, result)
    assert result.num == expected_num, "%s: 期待値 %r, 実際 %r" % (
        name,
        expected_num,
        result.num,
    )
    print("OK: %s => %d" % (name, result.num))


def test_mutual_recursion_small():
    # EOPL p161: (odd 13) と同じ形。まずは小さいnで正しさだけ確認する。
    for n in range(0, 8):
        expected = n % 2
        check("mutual_even_odd(%d)" % n, build_mutual_even_odd(n), expected)


def test_mutual_recursion_stress_low_recursion_limit():
    # Pythonの再帰上限をわざと極端に低く設定した状態で、大きなNでも
    # RecursionError にならずに完走することを確認する
    # (トランポリンがCスタックではなくwhileループでループを回している証拠)。
    n = 200001  # 奇数
    expected = n % 2

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        check("mutual_even_odd_stress(%d)" % n, build_mutual_even_odd(n), expected)
    finally:
        sys.setrecursionlimit(old_limit)


if __name__ == "__main__":
    test_mutual_recursion_small()
    test_mutual_recursion_stress_low_recursion_limit()
    print("all mutual recursion tests passed")
