# -*- coding: utf-8 -*-
# CEK機械が扱う値 (仕様書 8.3節 E = Z + Ep + M + F) のうち手続き以外の定義。
# 手続きは proc.py。依存関係の起点なので他の自作モジュールはimportしない。
from rpy import dont_look_inside


class SchemeError(Exception):
    # 仕様書 9.1節: エラーの種類は区別しない
    pass


class Value(object):
    def apply_procedure(self, args, kont):
        # 手続きでない値の適用 (仕様書 4.3節)
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
    # define の変数に値が格納される前の状態 (仕様書 5.2節)
    def to_string(self):
        return "#<undefined>"


UNDEFINED = UndefinedVal()


class PairVal(Value):
    # ペアは書換え不可能 (仕様書 3.5節)
    _immutable_fields_ = ["car", "cdr"]

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def to_string(self):
        return show(self)


@dont_look_inside
def show(val):
    # 仕様書 8.8節 show
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
