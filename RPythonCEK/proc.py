# -*- coding: utf-8 -*-
# 手続き値 (仕様書 8.3節 F)。apply_procedure が手続き適用の遷移規則
#   <v0 v1 ... vn を適用, κ> -> 次の状態
# に当たり、状態を返すだけで自分からは評価しない。
from value import Value, SchemeError
from env import Frame
from state import EvalState, ContState
from primitives import P_CWCC, call_primitive


class ProcVal(Value):
    def to_string(self):
        return "#<procedure>"


class ClosureVal(ProcVal):
    # lambda 式の値。lam は exp.LambdaExp
    _immutable_fields_ = ["lam", "env"]

    def __init__(self, lam, env):
        self.lam = lam
        self.env = env

    def apply_procedure(self, args, kont):
        # β規則: <body, ρ'[x*=v*], κ>
        if len(args) != self.lam.nparams:
            raise SchemeError()
        return EvalState(self.lam.body, Frame(args, self.env), kont)


class PrimVal(ProcVal):
    _immutable_fields_ = ["pid", "name", "arity"]

    def __init__(self, pid, name, arity):
        self.pid = pid
        self.name = name
        self.arity = arity

    def apply_procedure(self, args, kont):
        if len(args) != self.arity:
            raise SchemeError()
        if self.pid == P_CWCC:
            # proc を継続 κ のまま呼ぶ = 末尾呼出し (仕様書 6.7節)
            return args[0].apply_procedure([ContVal(kont)], kont)
        return ContState(call_primitive(self.pid, args), kont)


class ContVal(ProcVal):
    # 継続手続き。K レジスタの値をそのまま持つので何度でも呼べる
    _immutable_fields_ = ["kont"]

    def __init__(self, kont):
        self.kont = kont

    def apply_procedure(self, args, kont):
        # 今の継続 kont は捨てる
        if len(args) != 1:
            raise SchemeError()
        return ContState(args[0], self.kont)
