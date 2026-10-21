# -*- coding: utf-8 -*-
# CEK機械の状態遷移を1ステップずつ表示するデモ (CPython専用、RPython翻訳対象外)。
#   python demo_trace.py
#
# CPSインタプリタでは関数呼び出しの連鎖の中に隠れていた計算の途中経過が、
# CEK機械では <C, E, K> というデータとして全部見えることを確認する。
import sys
import primitives
from convert import convert_program
from syntax import parse_program
from machine import initial_state
from state import HaltState

primitives.write_out = lambda s: sys.stdout.write("[out] %r\n" % (s,))


def kont_chain(kont):
    # 継続チェーンを外側に向かってたどり、フレーム名を並べる
    names = []
    while kont is not None:
        names.append(kont.to_string())
        kont = getattr(kont, "kont", None)
    return " -> ".join(names)


def trace(text, max_steps=200):
    print("=== %s ===" % " ".join(text.split()))
    state = initial_state(convert_program(parse_program(text)))
    i = 0
    while not isinstance(state, HaltState):
        print("%3d: %-36s K = %s" % (i, state.to_string(), kont_chain(state.kont)))
        state = state.step()
        i += 1
        if i > max_steps:
            print("... (max_steps 到達)")
            return
    print("%3d: %s" % (i, state.to_string()))
    print("total steps = %d\n" % (i,))


if __name__ == "__main__":
    # 1. 算術だけ。app 継続が積まれ、値が返って畳まれる
    trace("(- 10 3)")

    # 2. if。テストを評価する間だけ if 継続が積まれる
    trace("(if (zero? (- 10 10)) 1 2)")

    # 3. 手続き呼出し。app 継続で演算子・オペランドを左から右へ求め、
    #    最後の値が来た時点で制御がクロージャ本体へ移る (β規則)
    trace("((lambda (x) (- x 11)) 77)")

    # 4. 末尾再帰。ステップは進むのに継続チェーンの長さが増えない
    trace("(letrec ((loop (lambda (i) (if (zero? i) 0 (loop (- i 1)))))) (loop 3))")

    # 5. call-with-current-continuation。K レジスタの値がそのまま継続手続きになる
    trace("(display (+ 1 (call-with-current-continuation (lambda (k) (+ 10 (k 2))))))")
