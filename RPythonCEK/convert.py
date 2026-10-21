# -*- coding: utf-8 -*-
# s-reader の構文木 -> exp.py の構文木。
# 変数を字句アドレス (depth, index) / GlobalCell / 標準手続きの定数に解決する。
# 静的検査 (仕様書 7.1節) は s-reader が済ませているので、ここでは解決だけを行う。
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s-reader"))

import syntax
from value import IntVal, TRUE, FALSE, NIL, UNDEFINED
from env import GlobalCell
from proc import PrimVal
from primitives import ARITY
from exp import (ConstExp, LocalVarExp, GlobalVarExp, LambdaExp, IfExp, AppExp,
                 SetLocalExp, SetGlobalExp, LetrecExp, DefineExp)

PRIM_VALS = [PrimVal(i, syntax.PRIMITIVES[i], ARITY[i]) for i in range(len(syntax.PRIMITIVES))]


class Scope(object):
    # lambda の仮引数または letrec の変数 1 組 = 実行時のフレーム 1 枚
    def __init__(self, names, parent):
        self.names = names
        self.parent = parent


class Globals(object):
    def __init__(self, cells):
        self.cells = {}
        for cell in cells:
            self.cells[cell.name] = cell


def find_local(scope, name):
    # (depth, index)。見つからなければ depth = -1
    depth = 0
    while scope is not None:
        for i in range(len(scope.names)):
            if scope.names[i] == name:
                return depth, i
        scope = scope.parent
        depth += 1
    return -1, -1


def find_primitive(name):
    for i in range(len(syntax.PRIMITIVES)):
        if syntax.PRIMITIVES[i] == name:
            return i
    return -1


def convert_lambda(lam, scope, glob):
    return LambdaExp(len(lam.params), convert(lam.body, Scope(lam.params, scope), glob))


def convert(e, scope, glob):
    if isinstance(e, syntax.IntExp):
        return ConstExp(IntVal(e.value))
    if isinstance(e, syntax.BoolExp):
        if e.value:
            return ConstExp(TRUE)
        return ConstExp(FALSE)
    if isinstance(e, syntax.NilExp):
        return ConstExp(NIL)
    if isinstance(e, syntax.VarExp):
        depth, index = find_local(scope, e.name)
        if depth >= 0:
            return LocalVarExp(e.name, depth, index)
        if e.name in glob.cells:
            return GlobalVarExp(glob.cells[e.name])
        return ConstExp(PRIM_VALS[find_primitive(e.name)])
    if isinstance(e, syntax.LambdaExp):
        return convert_lambda(e, scope, glob)
    if isinstance(e, syntax.IfExp):
        return IfExp(convert(e.test, scope, glob), convert(e.conseq, scope, glob),
                     convert(e.alt, scope, glob))
    if isinstance(e, syntax.SetExp):
        rhs = convert(e.exp, scope, glob)
        depth, index = find_local(scope, e.name)
        if depth >= 0:
            return SetLocalExp(e.name, depth, index, rhs)
        return SetGlobalExp(glob.cells[e.name], rhs)
    if isinstance(e, syntax.LetrecExp):
        inner = Scope(e.names, scope)
        lambdas = [convert_lambda(lam, inner, glob) for lam in e.lambdas]
        return LetrecExp(lambdas, convert(e.body, inner, glob))
    if isinstance(e, syntax.AppExp):
        rands = [convert(rand, scope, glob) for rand in e.rands]
        return AppExp(convert(e.rator, scope, glob), rands)
    raise ValueError("unknown expression")


def convert_program(program):
    # 定義の列と主式を DefineExp の連鎖 1 本にする
    cells = [GlobalCell(d.name, UNDEFINED) for d in program.defines]
    glob = Globals(cells)
    exp = convert(program.body, None, glob)
    for i in range(len(program.defines) - 1, -1, -1):
        exp = DefineExp(cells[i], convert(program.defines[i].exp, None, glob), exp)
    return exp
