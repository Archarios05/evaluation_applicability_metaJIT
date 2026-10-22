# -*- coding: utf-8 -*-
# EOPL p159 図5.7: トランポリン化されたインタプリタのドライバ。
#
# 評価そのものは各 Exp/Cont のメソッド (eval_cps / apply_cont) が直接呼び合って進める。
# クロージャと継続手続きの適用だけは評価を行わずに Bounce を返し、
# Bounce はその呼出しの連鎖を戻ってここに届く。trampoline はそれを開封して次に進む。
#
# jit_merge_point はこの while に置く。ループのバックエッジが本物のジャンプになる
# (以前 apply_procedure_k の再帰に置いたときは call_assembler になり、
#  Cスタックを消費し続けて StackOverflow を起こした)。
from rpy import JitDriver
from cont import EndCont
from bounce import ApplyProcBounce, ApplyContBounce


def get_location(exp):
    return exp.to_string()


# greens=exp: クロージャ本体の構文木。同じ本体に戻ってきたらループとみなす
jitdriver = JitDriver(greens=['exp'], reds=['env', 'cont'],
                      get_printable_location=get_location)#JITLOGオプション


def trampoline(exp, env, cont):
    # EOPL p159 trampoline : Bounce -> FinalAnswer
    while True:
        jitdriver.jit_merge_point(exp=exp, env=env, cont=cont)
        bounce = exp.eval_cps(env, cont)
        while isinstance(bounce, ApplyContBounce):
            bounce = bounce.cont.apply_cont(bounce.val)
        if not isinstance(bounce, ApplyProcBounce):
            return bounce
        exp = bounce.body
        env = bounce.env
        cont = bounce.cont


def value_of_program(exp):
    # EOPL p159 value-of-program : Program -> FinalAnswer
    return trampoline(exp, None, EndCont())
#コレ要らないかも、、、いつまでEOPLとの整合性を取ればいいかわからない
