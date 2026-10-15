# -*- coding: utf-8 -*-
# CEK機械が扱う値 (ExpVal/DenVal) のうち手続き以外の定義。
# 依存関係の起点なので他の自作モジュールはimportしない。


class Value(object):
    # EOPL p61 ExpVal = Int + Bool + Proc
    def to_string(self):
        return "value"


class NumVal(Value):
    def __init__(self, num):
        self.num = num

    def to_string(self):
        return "%d" % (self.num,)


class BoolVal(Value):
    def __init__(self, value):
        self.value = value

    def to_string(self):
        if self.value:
            return "#t"
        return "#f"


def expval_to_num(val):
    # EOPL p61 expval->num : ExpVal -> Int
    if not isinstance(val, NumVal):
        raise TypeError("expval_to_num: NumVal ではありません: %s" % (val.to_string(),))
    return val.num


def expval_to_bool(val):
    # EOPL p61 expval->bool : ExpVal -> Bool
    if not isinstance(val, BoolVal):
        raise TypeError("expval_to_bool: BoolVal ではありません: %s" % (val.to_string(),))
    return val.value


Var = str

# EOPL p143 FinalAnswer = ExpVal
FinalAnswer = Value
