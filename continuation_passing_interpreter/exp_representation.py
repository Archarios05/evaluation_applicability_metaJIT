# EOPL 3章/5章 抽象構文木(Expression)の定義。
# 各 Exp サブクラスが eval_cps(env, cont) を持ち、EOPL p154-155 図5.4/5.5の
# value-of/k の各ケースに対応する(オブジェクト指向の仮想メソッドディスパッチ)。
#
# LETRECの最小構成として、EOPL 5.1節で扱う9種の式
# (const-exp, var-exp, proc-exp, zero?-exp, if-exp, let-exp, diff-exp,
#  call-exp, letrec-exp) をすべて実装する。
from __future__ import annotations
from classes import NumVal, ProcVal
from cont_representation import (
    Zero1Cont,
    IfTestCont,
    LetExpCont,
    Diff1Cont,
    RatorCont,
)


class Exp(object):
    def eval_cps(self, env, cont):
        raise NotImplementedError


class ConstExp(Exp):
    # EOPL p154: (const-exp num) -> (apply-cont cont (num-val num))
    def __init__(self, num):
        self.num = num

    def eval_cps(self, env, cont):
        return cont.apply_cont(NumVal(self.num))


class VarExp(Exp):
    # EOPL p154: (var-exp var) -> (apply-cont cont (apply-env env var))
    def __init__(self, var):
        self.var = var

    def eval_cps(self, env, cont):
        val = env.lookup_variable_value(self.var)
        return cont.apply_cont(val)


class ProcExp(Exp):
    # EOPL p154: (proc-exp var body) -> (apply-cont cont (proc-val (procedure var body env)))
    def __init__(self, var, body):
        self.var = var
        self.body = body

    def eval_cps(self, env, cont):
        return cont.apply_cont(ProcVal(self.var, self.body, env))


class ZeroExp(Exp):
    # EOPL p154: (zero?-exp exp1) -> (value-of/k exp1 env (zero1-cont cont))
    def __init__(self, exp1):
        self.exp1 = exp1

    def eval_cps(self, env, cont):
        return self.exp1.eval_cps(env, Zero1Cont(cont))


class IfExp(Exp):
    # EOPL p154: (if-exp exp1 exp2 exp3)
    #   -> (value-of/k exp1 env (if-test-cont exp2 exp3 env cont))
    def __init__(self, exp1, exp2, exp3):
        self.exp1 = exp1
        self.exp2 = exp2
        self.exp3 = exp3

    def eval_cps(self, env, cont):
        return self.exp1.eval_cps(env, IfTestCont(self.exp2, self.exp3, env, cont))


class LetExp(Exp):
    # EOPL p154: (let-exp var exp1 body)
    #   -> (value-of/k exp1 env (let-exp-cont var body env cont))
    def __init__(self, var, exp1, body):
        self.var = var
        self.exp1 = exp1
        self.body = body

    def eval_cps(self, env, cont):
        return self.exp1.eval_cps(env, LetExpCont(self.var, self.body, env, cont))


class DiffExp(Exp):
    # EOPL p154: (diff-exp exp1 exp2)
    #   -> (value-of/k exp1 env (diff1-cont exp2 env cont))
    def __init__(self, exp1, exp2):
        self.exp1 = exp1
        self.exp2 = exp2

    def eval_cps(self, env, cont):
        return self.exp1.eval_cps(env, Diff1Cont(self.exp2, env, cont))


class CallExp(Exp):
    # EOPL p154: (call-exp rator rand)
    #   -> (value-of/k rator env (rator-cont rand env cont))
    def __init__(self, rator, rand):
        self.rator = rator
        self.rand = rand

    def eval_cps(self, env, cont):
        return self.rator.eval_cps(env, RatorCont(self.rand, env, cont))


class LetRecExp(Exp):
    # EOPL p154: (letrec-exp p-name b-var p-body letrec-body)
    #   -> (value-of/k letrec-body (extend-env-rec p-name b-var p-body env) cont)
    def __init__(self, p_name, b_var, p_body, letrec_body):
        self.p_name = p_name
        self.b_var = b_var
        self.p_body = p_body
        self.letrec_body = letrec_body

    def eval_cps(self, env, cont):
        new_env = env.extend_env_rec(self.p_name, self.b_var, self.p_body)
        return self.letrec_body.eval_cps(new_env, cont)
