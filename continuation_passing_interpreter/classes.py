# -*- coding: utf-8 -*-
# EOPL p148 図5.3のデータ構造表現に登場する値(ExpVal/DenVal)の定義。
# Exp/Cont以外の「値」に関する型はすべてここにまとめる。
# RPython(Python2のサブセット)向けに @dataclass や abc.ABC、Python3の
# 引数注釈構文(from __future__ import annotationsを含む)は使わず、
# 素の __init__ を持つクラスのみで構成する
# (dataclassは__init__をランタイムに合成するためRPythonのアノテータが解析できない。
#  引数注釈はPython2の文法に存在しないため、postponed evaluationでも回避できない)。
# 依存関係の起点となるファイルなので、他の自作モジュールはimportしない。
#
# JitDriver/トランポリン本体はinterpreter.pyのtrampoline()に置く
# (EOPL p159 図5.7)。ここではapply_procedure_kがBounce(ApplyProcBounce)を
# 返すだけにして、実際の評価(eval_cps呼び出し)は行わない。


class Bounce(object):
    # EOPL p159 Bounce = ExpVal ∪ (() -> Bounce)
    # Schemeのクロージャ(lambda () ...)の代わりに、
    # 「まだ実行していない apply_procedure_k 呼び出し」をデータとして
    # 保持するデータ構造表現を採用する(EOPL演習5.18)。
    pass


class Value(Bounce):
    # ExpVal/DenVal の基底クラス (EOPL p61 ExpVal = Int+Bool+Proc)
    # BounceのうちExpVal側(=もう計算が終わった最終値)に相当する。
    pass


class NumVal(Value):
    def __init__(self, num):
        self.num = num


class BoolVal(Value):
    def __init__(self, value):
        self.value = value


class ApplyProcBounce(Bounce):
    # EOPL p159 図5.7: apply-procedure/k の本体を包む (lambda () ...) に相当。
    # 「proc に val を渡して cont のもとで呼び出す」という、まだ実行していない
    # 計算をデータとして保持するだけで、ここでは一切評価しない。
    def __init__(self, proc, val, cont):
        self.proc = proc
        self.val = val
        self.cont = cont


class ProcVal(Value):
    # クロージャを表す型 (EOPL p147 procedure : Var x Exp x Env -> Proc)
    def __init__(self, var, body, env):
        self.var = var
        self.body = body
        self.env = env

    def apply_procedure_k(self, val, cont):
        # EOPL p152 apply-procedure/k : Proc x ExpVal x Cont -> Bounce (p159以降)
        # トランポリン化: ここでは評価(eval_cps呼び出し)を一切行わず、
        # 「次にやるべき計算」をApplyProcBounceとして返すだけにする。
        # これにより、この呼び出し自体はPythonの呼び出しスタックを消費しない。
        # 実際の評価はinterpreter.pyのtrampoline()が行う。
        return ApplyProcBounce(self, val, cont)


def expval_to_num(val):
    # EOPL p61 expval->num : ExpVal -> Int
    if not isinstance(val, NumVal):
        raise TypeError("expval_to_num: NumVal ではありません: %r" % (val,))
    return val.num


def expval_to_bool(val):
    # EOPL p61 expval->bool : ExpVal -> Bool
    if not isinstance(val, BoolVal):
        raise TypeError("expval_to_bool: BoolVal ではありません: %r" % (val,))
    return val.value


# EOPLにおけるVarは識別子(シンボル)であり、単なる文字列として扱えばよい。
# (専用クラスにすると__eq__/__hash__を自前で用意しない限り、
#  同名変数が別オブジェクト扱いになり環境の辞書検索が壊れるため)
Var = str

# EOPL p143 FinalAnswer = ExpVal
FinalAnswer = Value
