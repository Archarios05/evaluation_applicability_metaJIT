# -*- coding: utf-8 -*-
# 構文木 -> 平坦なコード。3imp-4.3+4.4+4.5.scm の preprocess + 3imp-compile に相当
#
# スタック上の呼出しの並び (下が古い):
#   [frame (ret f c)] [手続き] [引数0] ... [引数n-1]
#                               ^ f
# 末尾文脈では k = 捨てるスロット数 (手続き + 引数、末尾位置の slambda はその外側の分も足す)
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s-reader"))

from syntax import (IntExp, BoolExp, NilExp, VarExp, LambdaExp, IfExp, SetExp, LetrecExp,
                    AppExp, PRIMITIVES)
from RPython_3imp.value import (W_Int, W_TRUE, W_FALSE, W_NIL, W_UNDEFINED, W_Primitive)
from RPython_3imp.primitives import ARITY
from RPython_3imp.opcodes import (HALT, CONSTANT, REFER, REFER_FREE, REFER_GLOBAL, INDIRECT,
                     FUNCTIONAL, CLOSE, BOX, TEST, JUMP, ASSIGN, ASSIGN_GLOBAL,
                     FRAME, ARGUMENT, SHIFT, APPLY, RETURN, ASSIGN_FREE, DEFINE_GLOBAL,
                     describe)


class Code(object):
    _immutable_fields_ = ["ops[*]", "consts[*]", "global_names[*]", "initial_globals[*]"]

    def __init__(self, ops, consts, global_names, initial_globals):
        self.ops = ops
        self.consts = consts
        self.global_names = global_names
        self.initial_globals = initial_globals

    def describe(self, pc):
        return describe(self, pc)


class Binding(object):
    def __init__(self, name, boxed):
        self.name = name
        self.boxed = boxed


class CEnv(object):
    # ribs: 今のクロージャ本体の中で静的リンクでたどれる変数 (内側から)
    # free: 今のクロージャの自由変数。3imp の CB より外側にあたる
    def __init__(self, ribs, free):
        self.ribs = ribs
        self.free = free


LOCAL = 0
FREE = 1
GLOBAL = 2


class Loc(object):
    def __init__(self, kind, n, m, boxed):
        self.kind = kind
        self.n = n
        self.m = m
        self.boxed = boxed


def make_rib(names, boxed):
    return [Binding(name, boxed) for name in names]


def make_param_rib(params, body):
    # set! される仮引数だけ box に入れる (3imp の find-sets)
    sets = []
    find_sets(body, params, sets)
    return [Binding(name, name in sets) for name in params]


def emit_boxes(comp, rib):
    for m in range(len(rib)):
        if rib[m].boxed:
            comp.emit1(BOX, m)


def find_free(exp, bound, acc):
    if isinstance(exp, VarExp):
        if exp.name not in bound and exp.name not in acc:
            acc.append(exp.name)
    elif isinstance(exp, LambdaExp):
        find_free(exp.body, bound + exp.params, acc)
    elif isinstance(exp, IfExp):
        find_free(exp.test, bound, acc)
        find_free(exp.conseq, bound, acc)
        find_free(exp.alt, bound, acc)
    elif isinstance(exp, SetExp):
        if exp.name not in bound and exp.name not in acc:
            acc.append(exp.name)
        find_free(exp.exp, bound, acc)
    elif isinstance(exp, LetrecExp):
        inner = bound + exp.names
        for lam in exp.lambdas:
            find_free(lam, inner, acc)
        find_free(exp.body, inner, acc)
    elif isinstance(exp, AppExp):
        find_free(exp.rator, bound, acc)
        for rand in exp.rands:
            find_free(rand, bound, acc)


def find_sets(exp, names, acc):
    # names のうち exp の中で set! されるもの。内側で束縛し直された名前は除く
    if isinstance(exp, SetExp):
        if exp.name in names and exp.name not in acc:
            acc.append(exp.name)
        find_sets(exp.exp, names, acc)
    elif isinstance(exp, LambdaExp):
        find_sets(exp.body, [n for n in names if n not in exp.params], acc)
    elif isinstance(exp, IfExp):
        find_sets(exp.test, names, acc)
        find_sets(exp.conseq, names, acc)
        find_sets(exp.alt, names, acc)
    elif isinstance(exp, LetrecExp):
        inner = [n for n in names if n not in exp.names]
        for lam in exp.lambdas:
            find_sets(lam, inner, acc)
        find_sets(exp.body, inner, acc)
    elif isinstance(exp, AppExp):
        find_sets(exp.rator, names, acc)
        for rand in exp.rands:
            find_sets(rand, names, acc)


class Compiler(object):
    def __init__(self, global_names):
        self.ops = []
        self.consts = []
        self.global_index = {}
        for i in range(len(global_names)):
            self.global_index[global_names[i]] = i

    def here(self):
        return len(self.ops)

    def emit0(self, op):
        self.ops.append(op)

    def emit1(self, op, x):
        self.ops.append(op)
        self.ops.append(x)
        return len(self.ops) - 1

    def emit2(self, op, x, y):
        self.ops.append(op)
        self.ops.append(x)
        self.ops.append(y)
        return len(self.ops) - 1

    def emit3(self, op, x, y, z):
        self.ops.append(op)
        self.ops.append(x)
        self.ops.append(y)
        self.ops.append(z)
        return len(self.ops) - 1

    def patch(self, pos):
        self.ops[pos] = len(self.ops)

    def emit_constant(self, w):
        self.consts.append(w)
        self.emit1(CONSTANT, len(self.consts) - 1)

    def lookup(self, name, env):
        for n in range(len(env.ribs)):
            rib = env.ribs[n]
            for m in range(len(rib)):
                if rib[m].name == name:
                    return Loc(LOCAL, n, m, rib[m].boxed)
        for i in range(len(env.free)):
            if env.free[i].name == name:
                return Loc(FREE, i, 0, env.free[i].boxed)
        return Loc(GLOBAL, self.global_index[name], 0, False)

    def emit_refer(self, loc):
        if loc.kind == LOCAL:
            self.emit2(REFER, loc.n, loc.m)
        elif loc.kind == FREE:
            self.emit1(REFER_FREE, loc.n)
        else:
            self.emit1(REFER_GLOBAL, loc.n)

    def emit_return(self, tail, k):
        if tail:
            self.emit1(RETURN, k)

    def compile(self, exp, env, tail, k):
        if isinstance(exp, IntExp):
            self.emit_constant(W_Int(exp.value))
            self.emit_return(tail, k)
        elif isinstance(exp, BoolExp):
            if exp.value:
                self.emit_constant(W_TRUE)
            else:
                self.emit_constant(W_FALSE)
            self.emit_return(tail, k)
        elif isinstance(exp, NilExp):
            self.emit_constant(W_NIL)
            self.emit_return(tail, k)
        elif isinstance(exp, VarExp):
            loc = self.lookup(exp.name, env)
            self.emit_refer(loc)
            if loc.boxed:
                self.emit0(INDIRECT)
            self.emit_return(tail, k)
        elif isinstance(exp, LambdaExp):
            self.compile_close(exp, env)
            self.emit_return(tail, k)
        elif isinstance(exp, IfExp):
            self.compile_if(exp, env, tail, k)
        elif isinstance(exp, SetExp):
            self.compile_set(exp, env, tail, k)
        elif isinstance(exp, LetrecExp):
            self.compile_letrec(exp, env, tail, k)
        elif isinstance(exp, AppExp):
            rator = exp.rator
            if isinstance(rator, LambdaExp):
                self.compile_functional_call(rator, exp.rands, env, tail, k)
            else:
                self.compile_call(exp, env, tail, k)
        else:
            assert False

    def compile_if(self, exp, env, tail, k):
        self.compile(exp.test, env, False, 0)
        to_else = self.emit1(TEST, 0)
        self.compile(exp.conseq, env, tail, k)
        if tail:
            self.patch(to_else)
            self.compile(exp.alt, env, tail, k)
        else:
            to_end = self.emit1(JUMP, 0)
            self.patch(to_else)
            self.compile(exp.alt, env, tail, k)
            self.patch(to_end)

    def compile_set(self, exp, env, tail, k):
        self.compile(exp.exp, env, False, 0)
        loc = self.lookup(exp.name, env)
        if loc.kind == LOCAL:
            assert loc.boxed
            self.emit2(ASSIGN, loc.n, loc.m)
        elif loc.kind == FREE:
            assert loc.boxed
            self.emit1(ASSIGN_FREE, loc.n)
        else:
            self.emit1(ASSIGN_GLOBAL, loc.n)
        self.emit_return(tail, k)

    def compile_close(self, lam, env):
        # clambda: 自由変数の値を積んで close (3imp の collect-free)
        names = []
        find_free(lam.body, lam.params, names)
        free = []
        for name in names:
            loc = self.lookup(name, env)
            if loc.kind == GLOBAL:
                continue
            self.emit_refer(loc)
            self.emit0(ARGUMENT)
            free.append(Binding(name, loc.boxed))
        nparams = len(lam.params)
        to_end = self.emit3(CLOSE, len(free), nparams, 0)
        rib = make_param_rib(lam.params, lam.body)
        inner = CEnv([rib], free)
        emit_boxes(self, rib)
        self.compile(lam.body, inner, True, nparams + 1)
        self.patch(to_end)

    def compile_call(self, exp, env, tail, k):
        n = len(exp.rands)
        ret = 0
        if not tail:
            ret = self.emit1(FRAME, 0)
        self.compile(exp.rator, env, False, 0)
        self.emit0(ARGUMENT)
        for rand in exp.rands:
            self.compile(rand, env, False, 0)
            self.emit0(ARGUMENT)
        if tail:
            self.emit2(SHIFT, n + 1, k)
        self.emit1(APPLY, n)
        if not tail:
            self.patch(ret)

    def compile_functional_call(self, lam, rands, env, tail, k):
        # slambda: 関数位置の lambda。末尾位置なら frame を積まず、外側のフレームの上に重ねる
        nparams = len(lam.params)
        ret = 0
        body_k = nparams + 1
        if tail:
            body_k += k
        else:
            ret = self.emit1(FRAME, 0)
        to_end = self.emit2(FUNCTIONAL, nparams, 0)
        rib = make_param_rib(lam.params, lam.body)
        inner = CEnv([rib] + env.ribs, env.free)
        emit_boxes(self, rib)
        self.compile(lam.body, inner, True, body_k)
        self.patch(to_end)
        self.emit0(ARGUMENT)
        for rand in rands:
            self.compile(rand, env, False, 0)
            self.emit0(ARGUMENT)
        self.emit1(APPLY, len(rands))
        if not tail:
            self.patch(ret)

    def compile_letrec(self, exp, env, tail, k):
        # ((lambda (v ...) (set! v L) ... body) undefined ...) と同じ。v は box に入れる
        n = len(exp.names)
        ret = 0
        body_k = n + 1
        if tail:
            body_k += k
        else:
            ret = self.emit1(FRAME, 0)
        to_end = self.emit2(FUNCTIONAL, n, 0)
        inner = CEnv([make_rib(exp.names, True)] + env.ribs, env.free)
        for i in range(n):
            self.emit1(BOX, i)
        for i in range(n):
            self.compile_close(exp.lambdas[i], inner)
            self.emit2(ASSIGN, 0, i)
        self.compile(exp.body, inner, True, body_k)
        self.patch(to_end)
        self.emit0(ARGUMENT)
        for i in range(n):
            self.emit_constant(W_UNDEFINED)
            self.emit0(ARGUMENT)
        self.emit1(APPLY, n)
        if not tail:
            self.patch(ret)


def freeze_ints(lst):
    res = [0] * len(lst)
    for i in range(len(lst)):
        res[i] = lst[i]
    return res


def compile_program(program):
    defined = {}
    for d in program.defines:
        defined[d.name] = True
    names = []
    initial = []
    for pid in range(len(PRIMITIVES)):
        name = PRIMITIVES[pid]
        if name not in defined:
            names.append(name)
            initial.append(W_Primitive(pid, name, ARITY[pid]))
    for d in program.defines:
        names.append(d.name)
        initial.append(W_UNDEFINED)

    comp = Compiler(names)
    top = CEnv([], [])
    for d in program.defines:
        comp.compile(d.exp, top, False, 0)
        comp.emit1(DEFINE_GLOBAL, comp.global_index[d.name])
    comp.compile(program.body, top, False, 0)
    comp.emit0(HALT)

    consts = [None] * len(comp.consts)
    for i in range(len(comp.consts)):
        consts[i] = comp.consts[i]
    global_names = [""] * len(names)
    initial_globals = [None] * len(initial)
    for i in range(len(names)):
        global_names[i] = names[i]
        initial_globals[i] = initial[i]
    return Code(freeze_ints(comp.ops), consts, global_names, initial_globals)
