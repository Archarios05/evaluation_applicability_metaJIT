# -*- coding: utf-8 -*-
# 標準手続き (仕様書 6章)。番号は syntax.PRIMITIVES の並びと同じ
# call-with-current-continuation はスタックを触るので vm.py の apply で扱う
import os
from RPython_3imp.rpy import ovfcheck
from RPython_3imp.value import (SchemeError, W_Int, W_Pair, W_NIL, W_FALSE, W_UNSPECIFIED,
                   wrap_bool, show)

P_ADD = 0
P_SUB = 1
P_MUL = 2
P_QUOTIENT = 3
P_REMAINDER = 4
P_MODULO = 5
P_NUM_EQ = 6
P_LT = 7
P_GT = 8
P_LE = 9
P_GE = 10
P_ZEROP = 11
P_NOT = 12
P_EQP = 13
P_CONS = 14
P_CAR = 15
P_CDR = 16
P_NULLP = 17
P_PAIRP = 18
P_DISPLAY = 19
P_NEWLINE = 20
P_CWCC = 21

ARITY = [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 0, 1]


def write_out(s):
    os.write(1, s)


def int_of(w):
    if not isinstance(w, W_Int):
        raise SchemeError()
    return w.value


def pair_of(w):
    if not isinstance(w, W_Pair):
        raise SchemeError()
    return w


def eq(x, y):
    if isinstance(x, W_Int) and isinstance(y, W_Int):
        return x.value == y.value
    return x is y


def quotient(x, y):
    if y == -1:
        try:
            return ovfcheck(0 - x)
        except OverflowError:
            raise SchemeError()
    q = x // y
    if x % y != 0 and (x < 0) != (y < 0):
        q += 1
    return q


def remainder(x, y):
    if y == -1:
        return 0
    r = x % y
    if r != 0 and (x < 0) != (y < 0):
        r -= y
    return r


def modulo(x, y):
    if y == -1:
        return 0
    return x % y


def arith(pid, x, y):
    try:
        if pid == P_ADD:
            return ovfcheck(x + y)
        if pid == P_SUB:
            return ovfcheck(x - y)
        if pid == P_MUL:
            return ovfcheck(x * y)
    except OverflowError:
        raise SchemeError()
    if y == 0:
        raise SchemeError()
    if pid == P_QUOTIENT:
        return quotient(x, y)
    if pid == P_REMAINDER:
        return remainder(x, y)
    return modulo(x, y)


def compare(pid, x, y):
    if pid == P_NUM_EQ:
        return x == y
    if pid == P_LT:
        return x < y
    if pid == P_GT:
        return x > y
    if pid == P_LE:
        return x <= y
    return x >= y


def call_primitive(pid, stack, base):
    # 引数は stack[base], stack[base + 1]。個数は呼出し側で検査済み
    if pid == P_NEWLINE:
        write_out("\n")
        return W_UNSPECIFIED
    x = stack[base]
    if pid == P_ZEROP:
        return wrap_bool(int_of(x) == 0)
    if pid == P_NOT:
        return wrap_bool(x is W_FALSE)
    if pid == P_CAR:
        return pair_of(x).car
    if pid == P_CDR:
        return pair_of(x).cdr
    if pid == P_NULLP:
        return wrap_bool(x is W_NIL)
    if pid == P_PAIRP:
        return wrap_bool(isinstance(x, W_Pair))
    if pid == P_DISPLAY:
        write_out(show(x))
        return W_UNSPECIFIED
    y = stack[base + 1]
    if pid == P_EQP:
        return wrap_bool(eq(x, y))
    if pid == P_CONS:
        return W_Pair(x, y)
    if pid <= P_MODULO:
        return W_Int(arith(pid, int_of(x), int_of(y)))
    if pid <= P_GE:
        return wrap_bool(compare(pid, int_of(x), int_of(y)))
    raise SchemeError()
