# -*- coding: utf-8 -*-
# 値 (E = Z + Ep + M + F) のうち手続き以外の定義。
# 手続きは proc.py、トランポリンの Bounce は bounce.py。
#
# RPython (Python2 サブセット) 向けに @dataclass や abc.ABC、引数注釈は使わず、
# 素の __init__ を持つクラスのみで構成する。
from rpy import dont_look_inside
from bounce import Bounce


class SchemeError(Exception):
    pass


class Value(Bounce):
    # Bounce のうち計算が終わった最終値の側
    def apply_procedure_k(self, args, cont):
        # 手続きでない値の適用
        raise SchemeError()

    def to_string(self):
        return "#<value>"


class IntVal(Value):
    _immutable_fields_ = ["value"]

    def __init__(self, value):
        self.value = value

    def to_string(self):
        return "%d" % (self.value,)


class BoolVal(Value):
    _immutable_fields_ = ["value"]

    def __init__(self, value):
        self.value = value

    def to_string(self):
        if self.value:
            return "#t"
        return "#f"


TRUE = BoolVal(True)
FALSE = BoolVal(False)


def wrap_bool(b):
    if b:
        return TRUE
    return FALSE


class NilVal(Value):
    def to_string(self):
        return "()"


NIL = NilVal()


class UnspecifiedVal(Value):
    # display / newline / set! の値
    def to_string(self):
        return "#<unspecified>"


UNSPECIFIED = UnspecifiedVal()


class UndefinedVal(Value):
    # define の変数に値が格納される前の状態
    def to_string(self):
        return "#<undefined>"


UNDEFINED = UndefinedVal()


class PairVal(Value):
    # ペアは書換え不可能
    _immutable_fields_ = ["car", "cdr"]

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def to_string(self):
        return show(self)


@dont_look_inside
def show(val):
    if isinstance(val, PairVal):
        parts = ["(", show(val.car)]
        rest = val.cdr
        while isinstance(rest, PairVal):
            parts.append(" ")
            parts.append(show(rest.car))
            rest = rest.cdr
        if rest is not NIL:
            parts.append(" . ")
            parts.append(show(rest))
        parts.append(")")
        return "".join(parts)
    return val.to_string()
