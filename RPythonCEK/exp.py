# -*- coding: utf-8 -*-
# 抽象構文木(CEK機械の C レジスタ)の定義。
# 対象言語は EOPL 5.1節の LETREC 言語 (const, var, proc, zero?, if, let,
# diff, call, letrec) + 独自拡張の print。
#
# 各 Exp サブクラスの eval_step(env, kont) が
#   <exp, ρ, κ>_eval -> 次の状態
# という遷移規則1本に対応する(EOPL p154-155 図5.4/5.5 の value-of/k の各ケース)。
# RPythonはmatch文をサポートしないので、遷移規則の場合分けは
# 「Expサブクラスの仮想メソッドディスパッチ」で表現する。
#
# CPS版 (eval_cps) との違いは戻り値だけ:
#   CPS版 : return cont.apply_cont(NumVal(self.num))      # 呼び出して結果を返す
#   CEK版 : return ContState(NumVal(self.num), kont)      # 次の状態を返すだけ
from value import NumVal
from proc import ProcVal
from state import EvalState, ContState
from cont import (
    Zero1Kont,
    IfTestKont,
    LetKont,
    Diff1Kont,
    RatorKont,
    Print1Kont,
)


class Exp(object):
    def eval_step(self, env, kont):
        raise NotImplementedError

    def to_string(self):
        return "exp"


class ConstExp(Exp):
    # <(const-exp n), ρ, κ> -> <(num-val n), κ>_cont
    def __init__(self, num):
        self.num = num

    def eval_step(self, env, kont):
        return ContState(NumVal(self.num), kont)

    def to_string(self):
        return "const(%d)" % (self.num,)


class VarExp(Exp):
    # <(var-exp x), ρ, κ> -> <ρ(x), κ>_cont
    def __init__(self, var):
        self.var = var

    def eval_step(self, env, kont):
        return ContState(env.lookup_variable_value(self.var), kont)

    def to_string(self):
        return "var(%s)" % (self.var,)


class ProcExp(Exp):
    # <(proc-exp x body), ρ, κ> -> <(closure x body ρ), κ>_cont
    def __init__(self, var, body):
        self.var = var
        self.body = body

    def eval_step(self, env, kont):
        return ContState(ProcVal(self.var, self.body, env), kont)

    def to_string(self):
        return "proc(%s)" % (self.var,)


class ZeroExp(Exp):
    # <(zero?-exp e1), ρ, κ> -> <e1, ρ, (zero1-kont κ)>_eval
    def __init__(self, exp1):
        self.exp1 = exp1

    def eval_step(self, env, kont):
        return EvalState(self.exp1, env, Zero1Kont(kont))

    def to_string(self):
        return "zero?"


class IfExp(Exp):
    # <(if-exp e1 e2 e3), ρ, κ> -> <e1, ρ, (if-test-kont e2 e3 ρ κ)>_eval
    def __init__(self, exp1, exp2, exp3):
        self.exp1 = exp1
        self.exp2 = exp2
        self.exp3 = exp3

    def eval_step(self, env, kont):
        return EvalState(self.exp1, env, IfTestKont(self.exp2, self.exp3, env, kont))

    def to_string(self):
        return "if"


class LetExp(Exp):
    # <(let-exp x e1 body), ρ, κ> -> <e1, ρ, (let-kont x body ρ κ)>_eval
    def __init__(self, var, exp1, body):
        self.var = var
        self.exp1 = exp1
        self.body = body

    def eval_step(self, env, kont):
        return EvalState(self.exp1, env, LetKont(self.var, self.body, env, kont))

    def to_string(self):
        return "let(%s)" % (self.var,)


class DiffExp(Exp):
    # <(diff-exp e1 e2), ρ, κ> -> <e1, ρ, (diff1-kont e2 ρ κ)>_eval
    def __init__(self, exp1, exp2):
        self.exp1 = exp1
        self.exp2 = exp2

    def eval_step(self, env, kont):
        return EvalState(self.exp1, env, Diff1Kont(self.exp2, env, kont))

    def to_string(self):
        return "diff"


class CallExp(Exp):
    # <(call-exp rator rand), ρ, κ> -> <rator, ρ, (rator-kont rand ρ κ)>_eval
    def __init__(self, rator, rand):
        self.rator = rator
        self.rand = rand

    def eval_step(self, env, kont):
        return EvalState(self.rator, env, RatorKont(self.rand, env, kont))

    def to_string(self):
        return "call"


class PrintExp(Exp):
    # 独自拡張: <(print-exp e1), ρ, κ> -> <e1, ρ, (print1-kont κ)>_eval
    def __init__(self, exp1):
        self.exp1 = exp1

    def eval_step(self, env, kont):
        return EvalState(self.exp1, env, Print1Kont(kont))

    def to_string(self):
        return "print"


class LetRecExp(Exp):
    # <(letrec-exp p b p-body body), ρ, κ> -> <body, (extend-env-rec ...), κ>_eval
    # 継続を積まずに環境だけを伸ばす、唯一の Eval -> Eval 遷移。
    def __init__(self, p_name, b_var, p_body, letrec_body):
        self.p_name = p_name
        self.b_var = b_var
        self.p_body = p_body
        self.letrec_body = letrec_body

    def eval_step(self, env, kont):
        new_env = env.extend_env_rec(self.p_name, self.b_var, self.p_body)
        return EvalState(self.letrec_body, new_env, kont)

    def to_string(self):
        return "letrec(%s)" % (self.p_name,)
