# -*- coding: utf-8 -*-
# 値 (仕様書 8.3節 E = Z + Ep + M + F) のうち手続き以外の定義と、トランポリンの Bounce。
# 手続きは proc.py。依存関係の起点なので他の自作モジュールはimportしない。
#
# RPython (Python2 サブセット) 向けに @dataclass や abc.ABC、引数注釈は使わず、
# 素の __init__ を持つクラスのみで構成する。
from rpy import dont_look_inside


class SchemeError(Exception):
    # 仕様書 9.1節: エラーの種類は区別しない
    pass


class Bounce(object):
    # EOPL p159 Bounce = ExpVal ∪ (() -> Bounce)
    # Scheme のクロージャ (lambda () ...) の代わりに、
    # まだ実行していない計算をデータとして持つ (EOPL 演習5.18)。
    pass


class ApplyProcBounce(Bounce):
    # クロージャ適用の (lambda () (value-of/k body (extend-env ...) cont))。
    # 環境はもう拡張してあり、残りは本体を評価するだけ
    def __init__(self, body, env, cont):
        self.body = body
        self.env = env
        self.cont = cont


class ApplyContBounce(Bounce):
    # 継続手続きの適用 (lambda () (apply-cont cont val))。
    # 今の継続を捨てるので、ホストのスタックもここで巻き戻す
    def __init__(self, cont, val):
        self.cont = cont
        self.val = val


class Value(Bounce):
    # Bounce のうち計算が終わった最終値の側
    def apply_procedure_k(self, args, cont):
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
