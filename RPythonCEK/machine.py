# -*- coding: utf-8 -*-
# CEK機械の駆動部(遷移関数を回すだけのループ)とエントリポイント。
#
# 遷移規則そのものは exp.eval_step / cont.apply_kont
# に書いてあるので、ここがやるのは「停止状態になるまで遷移を繰り返す」ことだけ。
#
# CPS版 interpreter.py の trampoline() との対応:
#   trampoline は「手続き呼び出し(ApplyProcBounce)のときだけ」ループに戻ってきた。
#   CEKの run_machine は「すべての簡約ステップ」がループに戻ってくる。
#   よってホストの呼び出しスタックは深さ一定のまま(CPS版はcont側の連鎖で伸びた)。
from env import init_env
from cont import EndKont
from state import EvalState, ContState, HaltState

try:
    from rpython.rlib.jit import JitDriver
except ImportError:
    # CPythonで直接動かすとき用のダミー(pypy-tutorial-jpと同じ手口)。
    class JitDriver(object):
        def __init__(self, **kw):
            pass

        def jit_merge_point(self, **kw):
            pass

        def can_enter_jit(self, **kw):
            pass


def get_location(exp):
    return exp.to_string()


jitdriver = JitDriver(greens=['exp'], reds=['env', 'kont'],
                      get_printable_location=get_location)


def run_machine(exp, env, kont):
    
    while True:
        jitdriver.jit_merge_point(exp=exp, env=env, kont=kont)

        # (1) Eval遷移を1回
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
    # 教科書どおりの1行ドライバ。run_machine と意味は完全に同じで、
    # 状態オブジェクトを毎回作る分だけ素直(トレース表示や単体確認用)。
    while not isinstance(state, HaltState):
        state = state.step()
    return state.val


def initial_state(exp):
    # CEK機械の初期状態 <exp, init-env, end-kont>
    return EvalState(exp, init_env(), EndKont())


def value_of_program(exp):
    # EOPL p143 value-of-program : Program -> FinalAnswer
    # (a-programによるラップは省略し、Exp自体をプログラムとして扱う)
    return run_machine(exp, init_env(), EndKont())


def run(exp):
    return value_of_program(exp)
