# -*- coding: utf-8 -*-
# CEK機械の駆動部 (遷移関数を回すだけのループ)。
#
# 遷移規則そのものは exp.eval_step / cont.apply_kont / proc.apply_procedure
# に書いてあるので、ここがやるのは「停止状態になるまで遷移を繰り返す」ことだけ。
#
# CPS版 interpreter.py の trampoline() との対応:
#   trampoline は手続き適用のときだけループに戻ってくる。
#   run_machine はすべての簡約ステップがループに戻ってくる。
#   よってホストの呼び出しスタックは深さ一定のまま (CPS版は継続の連鎖で伸びる)。
from rpy import JitDriver
from cont import EndKont
from state import EvalState, ContState, HaltState


def get_location(exp):
    return exp.to_string()


jitdriver = JitDriver(greens=['exp'], reds=['env', 'kont'],
                      get_printable_location=get_location)


def run_machine(exp, env, kont):
    while True:
        jitdriver.jit_merge_point(exp=exp, env=env, kont=kont)

        # Eval遷移を1回、続く Cont遷移はまとめて進める
        state = exp.eval_step(env, kont)
        while isinstance(state, ContState):
            state = state.kont.apply_kont(state.val)

        if isinstance(state, HaltState):
            return state.val

        assert isinstance(state, EvalState)
        exp = state.exp
        env = state.env
        kont = state.kont


def run_states(state):
    # 教科書どおりのドライバ。run_machine と意味は完全に同じ
    while not isinstance(state, HaltState):
        state = state.step()
    return state.val


def initial_state(exp):
    # 初期状態 <program, (トップ・レベル), κ0>
    return EvalState(exp, None, EndKont())


def run_program(exp):
    return run_machine(exp, None, EndKont())
