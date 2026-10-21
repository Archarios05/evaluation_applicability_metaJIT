# -*- coding: utf-8 -*-
# 抽象構文木。s-reader の構文木を convert.py でこの形に変換してから実行する。
# 変数参照は字句アドレスか GlobalCell に、標準手続きの名前は定数に解決済み。
#
# 各 Exp サブクラスの eval_cps(env, cont) が value-of/k の 1 つの場合に当たる
# (仕様書 8.4節 ℰ の各場合)。RPython は match 文を使えないので、
# 場合分けは仮想メソッドディスパッチで表す。
from rpy import unroll_safe
from classes import SchemeError, UNDEFINED
from env import Frame, lookup
from proc import ClosureVal, PrimVal
from cont import IfCont, AppCont, SetLocalCont, SetGlobalCont, DefineCont


class Exp(object):
    def eval_cps(self, env, cont):
        raise NotImplementedError

    def to_string(self):
        return "exp"


class ConstExp(Exp):
    # (value-of/k K env cont) = (apply-cont cont 𝒦[K])。標準手続きの名前の参照もこれになる
    _immutable_fields_ = ["val"]

    def __init__(self, val):
        self.val = val

    def eval_cps(self, env, cont):
        return cont.apply_cont(self.val)

    def to_string(self):
        val = self.val
        if isinstance(val, PrimVal):
            return "prim(%s)" % (val.name,)
        return "const(%s)" % (val.to_string(),)


class LocalVarExp(Exp):
    # lambda / letrec の変数は参照時に必ず値を持つ
    _immutable_fields_ = ["name", "depth", "index"]

    def __init__(self, name, depth, index):
        self.name = name
        self.depth = depth
        self.index = index

    def eval_cps(self, env, cont):
        return cont.apply_cont(lookup(env, self.depth, self.index))

    def to_string(self):
        return "var(%s)" % (self.name,)


class GlobalVarExp(Exp):
    # define の変数。値が格納される前ならエラー (仕様書 5.2節)
    _immutable_fields_ = ["cell"]

    def __init__(self, cell):
        self.cell = cell

    def eval_cps(self, env, cont):
        val = self.cell.value
        if val is UNDEFINED:
            raise SchemeError()
        return cont.apply_cont(val)

    def to_string(self):
        return "global(%s)" % (self.cell.name,)


class LambdaExp(Exp):
    _immutable_fields_ = ["nparams", "body"]

    def __init__(self, nparams, body):
        self.nparams = nparams
        self.body = body

    def eval_cps(self, env, cont):
        return cont.apply_cont(ClosureVal(self, env))

    def to_string(self):
        return "lambda/%d" % (self.nparams,)


class IfExp(Exp):
    # (value-of/k test env (if-cont conseq alt env cont))
    _immutable_fields_ = ["test", "conseq", "alt"]

    def __init__(self, test, conseq, alt):
        self.test = test
        self.conseq = conseq
        self.alt = alt

    def eval_cps(self, env, cont):
        return self.test.eval_cps(env, IfCont(self.conseq, self.alt, env, cont))

    def to_string(self):
        return "if"


class AppExp(Exp):
    # (value-of/k rator env (app-cont rands ⟨⟩ env cont))
    _immutable_fields_ = ["rator", "rands[*]"]

    def __init__(self, rator, rands):
        self.rator = rator
        self.rands = rands

    def eval_cps(self, env, cont):
        return self.rator.eval_cps(env, AppCont(self, [], env, cont))

    def to_string(self):
        return "app/%d" % (len(self.rands),)


class SetLocalExp(Exp):
    _immutable_fields_ = ["name", "depth", "index", "exp"]

    def __init__(self, name, depth, index, exp):
        self.name = name
        self.depth = depth
        self.index = index
        self.exp = exp

    def eval_cps(self, env, cont):
        return self.exp.eval_cps(env, SetLocalCont(self.depth, self.index, env, cont))

    def to_string(self):
        return "set!(%s)" % (self.name,)


class SetGlobalExp(Exp):
    _immutable_fields_ = ["cell", "exp"]

    def __init__(self, cell, exp):
        self.cell = cell
        self.exp = exp

    def eval_cps(self, env, cont):
        return self.exp.eval_cps(env, SetGlobalCont(self.cell, cont))

    def to_string(self):
        return "set!(%s)" % (self.cell.name,)


class LetrecExp(Exp):
    # (value-of/k body (extend-env-rec names lambdas env) cont)
    # 初期値は lambda 式なので評価に継続が要らない
    _immutable_fields_ = ["lambdas[*]", "body"]

    def __init__(self, lambdas, body):
        self.lambdas = lambdas
        self.body = body

    @unroll_safe
    def eval_cps(self, env, cont):
        n = len(self.lambdas)
        frame = Frame([UNDEFINED] * n, env)
        for i in range(n):
            frame.vals[i] = ClosureVal(self.lambdas[i], frame)
        return self.body.eval_cps(frame, cont)

    def to_string(self):
        return "letrec/%d" % (len(self.lambdas),)


class DefineExp(Exp):
    # (define x e) の後に rest (残りの定義と主式) が続く。仕様書 8.4節 𝒟
    _immutable_fields_ = ["cell", "exp", "rest"]

    def __init__(self, cell, exp, rest):
        self.cell = cell
        self.exp = exp
        self.rest = rest

    def eval_cps(self, env, cont):
        return self.exp.eval_cps(env, DefineCont(self.cell, self.rest, cont))

    def to_string(self):
        return "define(%s)" % (self.cell.name,)
