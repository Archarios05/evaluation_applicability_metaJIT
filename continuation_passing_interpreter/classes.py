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
# JitDriver: トランポリン化はせず、再帰呼び出し(apply_procedure_k)そのものを
# ループの目印にする。CPythonから直接実行する場合はrpython.rlib.jitが
# 存在しないため、pypy-tutorial-jp/example5.pyと同様にダミークラスへ
# フォールバックする。
try:
    from rpython.rlib.jit import JitDriver
except ImportError:
    class JitDriver(object):
        def __init__(self, **kw):
            pass

        def jit_merge_point(self, **kw):
            pass

        def can_enter_jit(self, **kw):
            pass


def get_location(proc):
    return "call proc(%s)" % (proc.var,)


# greens=proc: 同じ手続き(同じvar/body/env)を指す間はホットループ候補とみなす。
# reds=val, cont: 呼び出しごとに変わる実引数値と継続。
jitdriver = JitDriver(greens=['proc'], reds=['val', 'cont'],
                       get_printable_location=get_location)


class Value(object):
    # ExpVal/DenVal の基底クラス (EOPL p61 ExpVal = Int+Bool+Proc)
    pass


class NumVal(Value):
    def __init__(self, num):
        self.num = num


class BoolVal(Value):
    def __init__(self, value):
        self.value = value


class ProcVal(Value):
    # クロージャを表す型 (EOPL p147 procedure : Var x Exp x Env -> Proc)
    def __init__(self, var, body, env):
        self.var = var
        self.body = body
        self.env = env

    def apply_procedure_k(self, val, cont):
        # EOPL p152 apply-procedure/k : Proc x ExpVal x Cont -> FinalAnswer
        # トランポリンは使わず、この関数自身への再入(再帰呼び出し)を
        # ホットループの目印としてjit_merge_pointに渡す。
        jitdriver.jit_merge_point(proc=self, val=val, cont=cont)
        new_env = self.env.extend_env([self.var], [val])
        jitdriver.can_enter_jit(proc=self, val=val, cont=cont)
        return self.body.eval_cps(new_env, cont)


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
