# -*- coding: utf-8 -*-
# 手続き値 。apply_procedure_k : Proc x ExpVal* x Cont -> Bounce
#
# トランポリン化 (EOPL p159): クロージャと継続手続きの適用は評価を行わず、
# 次にやるべき計算を Bounce として返すだけにする。Bounce は eval_cps / apply_cont の
# 呼出しの連鎖をそのまま戻って interpreter.trampoline に届き、ホストのスタックが巻き戻る。
# 標準手続きは呼び返しをしないので、その場で計算して継続に渡す。
from value import Value, SchemeError
from bounce import ApplyProcBounce, ApplyContBounce
from env import Frame
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

    def apply_procedure_k(self, args, cont):
        if len(args) != self.lam.nparams:
            raise SchemeError()
        return ApplyProcBounce(self.lam.body, Frame(args, self.env), cont)


class PrimVal(ProcVal):
    _immutable_fields_ = ["pid", "name", "arity"]

    def __init__(self, pid, name, arity):
        self.pid = pid
        self.name = name
        self.arity = arity

    def apply_procedure_k(self, args, cont):
        if len(args) != self.arity:
            raise SchemeError()
        if self.pid == P_CWCC:
            # proc を継続 cont のまま呼ぶ = 末尾呼出し 
            return args[0].apply_procedure_k([ContVal(cont)], cont)
        return cont.apply_cont(call_primitive(self.pid, args))


class ContVal(ProcVal):
    # 継続手続き。
    _immutable_fields_ = ["cont"]

    def __init__(self, cont):
        self.cont = cont

    def apply_procedure_k(self, args, cont):
        # 今の継続 cont は捨てる
        if len(args) != 1:
            raise SchemeError()
        return ApplyContBounce(self.cont, args[0])
