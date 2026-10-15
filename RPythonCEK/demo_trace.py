# -*- coding: utf-8 -*-
# CEK機械の状態遷移を1ステップずつ表示するデモ(CPython専用、RPython翻訳対象外)。
#   python demo_trace.py
#
# 「CPSインタプリタでは関数呼び出しの連鎖の中に隠れていた計算の途中経過が、
#   CEK機械では <C, E, K> という*データ*として全部見える」ことを確認するための
#   スクリプト。JITのトレースを読む前の準備運動として使う。
import os

_orig_os_write = os.write


def _os_write_compat(fd, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return _orig_os_write(fd, data)


os.write = _os_write_compat

from exp_representation import (
    ConstExp, VarExp, DiffExp, ZeroExp, IfExp, LetExp, ProcExp, CallExp, LetRecExp,
)
from machine import initial_state
from state import HaltState


def kont_chain(kont):
    # 継続チェーンを外側に向かってたどり、フレーム名を並べて表示する。
    names = []
    while kont is not None:
        names.append(kont.to_string())
        kont = getattr(kont, "saved_kont", None)
    return " -> ".join(names)


def trace(name, exp, max_steps=200):
    print("=== %s ===" % name)
    state = initial_state(exp)
    i = 0
    while not isinstance(state, HaltState):
        print("%3d: %-28s K = %s" % (i, state.to_string(), kont_chain(state.kont)))
        state = state.step()
        i += 1
        if i > max_steps:
            print("... (max_steps 到達)")
            return
    print("%3d: %s" % (i, state.to_string()))
    print("total steps = %d\n" % (i,))


if __name__ == "__main__":
    # 1. 算術だけ。Diff1Kont -> Diff2Kont と継続が積まれ、値が返って畳まれる様子。
    trace("-(x, 3)   in [i=1,v=5,x=10]", DiffExp(VarExp("x"), ConstExp(3)))

    # 2. let と zero? と if。継続フレームの種類が増える。
    trace(
        "let y = -(x,10) in if zero?(y) then 1 else 2",
        LetExp(
            "y",
            DiffExp(VarExp("x"), ConstExp(10)),
            IfExp(ZeroExp(VarExp("y")), ConstExp(1), ConstExp(2)),
        ),
    )

    # 3. 手続き呼び出し。RatorKont -> RandKont と進み、RandKont の遷移で
    #    制御がクロージャ本体へ移る(これがCEKのβ規則)。
    trace(
        "let f = proc(x) -(x,11) in (f 77)",
        LetExp(
            "f",
            ProcExp("x", DiffExp(VarExp("x"), ConstExp(11))),
            CallExp(VarExp("f"), ConstExp(77)),
        ),
    )

    # 4. 末尾再帰。ステップは進むのに継続チェーンの長さが増えないことを見る
    #    (末尾呼び出しが「継続を積まない」= 定数領域で回る、の意味)。
    loop_body = IfExp(
        ZeroExp(VarExp("i")),
        ConstExp(0),
        CallExp(VarExp("loop"), DiffExp(VarExp("i"), ConstExp(1))),
    )
    trace(
        "letrec loop(i) = if zero?(i) then 0 else (loop -(i,1)) in (loop 3)",
        LetRecExp("loop", "i", loop_body, CallExp(VarExp("loop"), ConstExp(3))),
    )
