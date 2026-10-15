# -*- coding: utf-8 -*-
# CEK機械が扱う「値」(ExpVal/DenVal)の定義。
# 隣の continuation_passing_interpreter/classes.py に対応するファイルだが、
# 決定的な違いが2つある:
#
#   1. Bounce / ApplyProcBounce が無い。
#      CPS版は「手続き呼び出しだけ」をトランポリンで跳ね返していたが、
#      CEK機械では *すべての* 簡約ステップが状態遷移 (state.py の State) なので、
#      「まだ実行していない計算」を表す専用の型は State に一本化される。
#   2. ProcVal に apply_procedure_k が無い。
#      手続き適用は「値の側のメソッド」ではなく、機械の遷移規則
#      (cont_representation.RandKont.apply_kont) そのものになる。
#
# RPython(Python2のサブセット)で翻訳するため、@dataclass / abc.ABC /
# 引数注釈 / f-string は使わず、素の __init__ を持つクラスだけで構成する。
# 依存関係の起点となるファイルなので、他の自作モジュールはimportしない。


class Value(object):
    # ExpVal/DenVal の基底クラス (EOPL p61 ExpVal = Int + Bool + Proc)
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


class ProcVal(Value):
    # クロージャを表す型 (EOPL p147 procedure : Var x Exp x Env -> Proc)
    # CEK機械の "E" (環境) を閉じ込めているのがこのクラス。
    # 呼び出し規則は RandKont.apply_kont 側にあるので、ここにメソッドは持たない
    # (CPS版の apply_procedure_k に相当するものが機械の遷移規則へ移動した)。
    def __init__(self, var, body, env):
        self.var = var
        self.body = body
        self.env = env

    def to_string(self):
        return "proc(%s)" % (self.var,)


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


# EOPLにおけるVarは識別子(シンボル)であり、単なる文字列として扱えばよい。
Var = str

# EOPL p143 FinalAnswer = ExpVal
FinalAnswer = Value


