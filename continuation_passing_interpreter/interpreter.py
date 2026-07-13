# -*- coding: utf-8 -*-
# EOPL p143 value-of-program / value-of/k のエントリポイント。
# p159 図5.7: トランポリン化されたインタプリタのドライバ。
#
# 実際のディスパッチは各Exp/Contのメソッド(eval_cps/apply_cont)が担う。
# classes.ProcVal.apply_procedure_k はもう評価そのものを行わず、
# ApplyProcBounce(次にやるべき計算のスナップショット)を返すだけになったので、
# 「そのスナップショットを開封して次の評価に進む」という本物のループが
# ここのtrampoline()に必要になる。
#
# jit_merge_point/can_enter_jitはこの本物のwhileループに置くことで、
# RPythonのJITが本物のbackward jumpとしてループを認識できるようにする
# (以前の実装ではapply_procedure_kの再帰呼び出しに置いていたため、
#  コンパイル後も call_assembler という本物のCALLになってしまい、
#  Cスタックを消費し続けてStackOverflowを起こしていた)。
from env_representation import init_env
from cont_representation import EndCont
from classes import Value, ApplyProcBounce

try:
    from rpython.rlib.jit import JitDriver
except ImportError:
    class JitDriver(object):
        def __init__(self, **kw):
            pass

        def jit_merge_point(self, **kw):
            pass

        def can_enter_jit(self, **kw):
            pass


def get_location(proc):
    return "call proc(%s)" % (proc.var,)


# greens=proc: 同じ手続き(同じvar/body/env)を指す間はホットループ候補とみなす。
# reds=val, cont: 呼び出しごとに変わる実引数値と継続。
jitdriver = JitDriver(greens=['proc'], reds=['val', 'cont'],
                       get_printable_location=get_location)


def trampoline(bounce):
    # EOPL p159 trampoline : Bounce -> FinalAnswer
    # bounceがValue(ExpVal)になるまで、ApplyProcBounceを開封し続ける。
    while not isinstance(bounce, Value):
        proc = bounce.proc
        val = bounce.val
        cont = bounce.cont
        jitdriver.jit_merge_point(proc=proc, val=val, cont=cont)
        new_env = proc.env.extend_env([proc.var], [val])
        bounce = proc.body.eval_cps(new_env, cont)
        if isinstance(bounce, ApplyProcBounce):
            jitdriver.can_enter_jit(proc=bounce.proc, val=bounce.val, cont=bounce.cont)
    return bounce


def valueofk(exp, env, cont):
    # EOPL p143 value-of/k : Exp x Env x Cont -> Bounce (p159以降)
    return exp.eval_cps(env, cont)


def value_of_program(exp):
    # EOPL p159 value-of-program : Program -> FinalAnswer
    # (a-programによるラップは省略し、Exp自体をプログラムとして扱う)
    bounce = valueofk(exp, init_env(), EndCont())
    return trampoline(bounce)


def run(exp):
    return value_of_program(exp)
