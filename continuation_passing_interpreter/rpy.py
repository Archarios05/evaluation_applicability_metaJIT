# -*- coding: utf-8 -*-
# RPython 依存部分。CPython で動かすときはダミーに差し替える
import sys

try:
    MAXINT = sys.maxint
except AttributeError:
    MAXINT = sys.maxsize

try:
    from rpython.rlib.jit import JitDriver, dont_look_inside, unroll_safe
    from rpython.rlib.rarithmetic import ovfcheck
    from rpython.rlib.rstackovf import StackOverflow
except ImportError:
    class JitDriver(object):
        def __init__(self, **kw):
            pass

        def jit_merge_point(self, **kw):
            pass

        def can_enter_jit(self, **kw):
            pass

    def dont_look_inside(func):
        return func

    def unroll_safe(func):
        return func

    def ovfcheck(x):
        if x > MAXINT or x < -MAXINT - 1:
            raise OverflowError
        return x

    try:
        StackOverflow = RecursionError
    except NameError:
        StackOverflow = RuntimeError
