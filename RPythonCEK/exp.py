# -*- coding: utf-8 -*-
# 抽象構文木 (CEK機械の C レジスタ)。
# s-reader の構文木を convert.py でこの形に変換してから実行する。
# 変数参照は字句アドレスか GlobalCell に、標準手続きの名前は定数に解決済み。
#
# 各 Exp サブクラスの eval_step(env, kont) が
#   <exp, ρ, κ>_eval -> 次の状態
# という遷移規則1本に対応する
#
# CPS版 (eval_cps) との違いは戻り値だけ:
#   CPS版 : return cont.apply_cont(self.val)      # 呼び出して結果を返す
#   CEK版 : return ContState(self.val, kont)      # 次の状態を返すだけ
from rpy import unroll_safe
from value import SchemeError, UNDEFINED
from env import Frame, lookup
from proc import ClosureVal, PrimVal
from state import EvalState, ContState
from cont import IfKont, AppKont, SetLocalKont, SetGlobalKont, DefineKont


class Exp(object):
    def eval_step(self, env, kont):
        raise NotImplementedError

    def to_string(self):
        return "exp"


class ConstExp(Exp):
    # <K, ρ, κ> -> <𝒦[K], κ>。標準手続きの名前の参照もこれになる
    _immutable_fields_ = ["val"]

    def __init__(self, val):
        self.val = val

    def eval_step(self, env, kont):
        return ContState(self.val, kont)

    def to_string(self):
        val = self.val
        if isinstance(val, PrimVal):
            return "prim(%s)" % (val.name,)
        return "const(%s)" % (val.to_string(),)


class LocalVarExp(Exp):
    # <x, ρ, κ> -> <ρ(x), κ>。lambda / letrec の変数は参照時に必ず値を持つ
    _immutable_fields_ = ["name", "depth", "index"]

    def __init__(self, name, depth, index):
        self.name = name
        self.depth = depth
        self.index = index

    def eval_step(self, env, kont):
        return ContState(lookup(env, self.depth, self.index), kont)

    def to_string(self):
        return "var(%s)" % (self.name,)


class GlobalVarExp(Exp):
    # define の変数。値が格納される前ならエラー 
    _immutable_fields_ = ["cell"]

    def __init__(self, cell):
        self.cell = cell

    def eval_step(self, env, kont):
        val = self.cell.value
        if val is UNDEFINED:
            raise SchemeError()
        return ContState(val, kont)

    def to_string(self):
        return "global(%s)" % (self.cell.name,)


class LambdaExp(Exp):
    # <(lambda (x*) body), ρ, κ> -> <(closure lambda ρ), κ>
    _immutable_fields_ = ["nparams", "body"]

    def __init__(self, nparams, body):
        self.nparams = nparams
        self.body = body

    def eval_step(self, env, kont):
        return ContState(ClosureVal(self, env), kont)

    def to_string(self):
        return "lambda/%d" % (self.nparams,)


class IfExp(Exp):
    # <(if e0 e1 e2), ρ, κ> -> <e0, ρ, (if e1 e2 ρ κ)>
    _immutable_fields_ = ["test", "conseq", "alt"]

    def __init__(self, test, conseq, alt):
        self.test = test
        self.conseq = conseq
        self.alt = alt

    def eval_step(self, env, kont):
        return EvalState(self.test, env, IfKont(self.conseq, self.alt, env, kont))

    def to_string(self):
        return "if"


class AppExp(Exp):
    # <(e0 e*), ρ, κ> -> <e0, ρ, (app e* ⟨⟩ ρ κ)>
    _immutable_fields_ = ["rator", "rands[*]"]

    def __init__(self, rator, rands):
        self.rator = rator
        self.rands = rands

    def eval_step(self, env, kont):
        return EvalState(self.rator, env, AppKont(self, [], env, kont))

    def to_string(self):
        return "app/%d" % (len(self.rands),)


class SetLocalExp(Exp):
    # <(set! x e), ρ, κ> -> <e, ρ, (set! x ρ κ)>
    _immutable_fields_ = ["name", "depth", "index", "exp"]

    def __init__(self, name, depth, index, exp):
        self.name = name
        self.depth = depth
        self.index = index
        self.exp = exp

    def eval_step(self, env, kont):
        return EvalState(self.exp, env, SetLocalKont(self.depth, self.index, env, kont))

    def to_string(self):
        return "set!(%s)" % (self.name,)


class SetGlobalExp(Exp):
    _immutable_fields_ = ["cell", "exp"]

    def __init__(self, cell, exp):
        self.cell = cell
        self.exp = exp

    def eval_step(self, env, kont):
        return EvalState(self.exp, env, SetGlobalKont(self.cell, kont))

    def to_string(self):
        return "set!(%s)" % (self.cell.name,)


class LetrecExp(Exp):
    # <(letrec ((x L)*) body), ρ, κ> -> <body, ρ', κ>
    #   ρ' = ρ[x*=(closure L* ρ')]
    # 初期値は lambda 式なので評価に継続が要らず、継続を積まない Eval -> Eval 遷移になる
    _immutable_fields_ = ["lambdas[*]", "body"]

    def __init__(self, lambdas, body):
        self.lambdas = lambdas
        self.body = body

    @unroll_safe
    def eval_step(self, env, kont):
        n = len(self.lambdas)
        frame = Frame([UNDEFINED] * n, env)
        for i in range(n):
            frame.vals[i] = ClosureVal(self.lambdas[i], frame)
        return EvalState(self.body, frame, kont)

    def to_string(self):
        return "letrec/%d" % (len(self.lambdas),)


class DefineExp(Exp):
    # (define x e) の後に rest (残りの定義と主式) が続く。
    #   <(define x e) rest, ρ, κ> -> <e, ρ, (define x rest κ)>
    _immutable_fields_ = ["cell", "exp", "rest"]

    def __init__(self, cell, exp, rest):
        self.cell = cell
        self.exp = exp
        self.rest = rest

    def eval_step(self, env, kont):
        return EvalState(self.exp, env, DefineKont(self.cell, self.rest, kont))

    def to_string(self):
        return "define(%s)" % (self.cell.name,)
