# -*- coding: utf-8 -*-
# EOPL p148 図5.3 継続 (Continuation) のデータ構造表現。
# apply-cont の case 分けを各 Cont サブクラスの apply_cont メソッドで表す。
# フレームの種類は CEK版 (RPythonCEK/cont.py) と同じ。
#
# 継続は構築時に確定している情報だけを持ち、apply_cont は値 val だけを受け取る。
# 各 apply_cont は exp.eval_cps(...) / cont.apply_cont(...) を末尾で直接呼ぶ。
# Exp 側のモジュールは import しない (ダックタイピング)。
from classes import SchemeError, FALSE, UNSPECIFIED, UNDEFINED
from env import assign


class Cont(object):
    def apply_cont(self, val):
        raise NotImplementedError


class EndCont(Cont):
    # 初期継続 κ0。最終値をそのまま返して trampoline を止める。
    # 主式の値は出力しない (仕様書 5.3節)
    def apply_cont(self, val):
        return val


class IfCont(Cont):
    # (apply-cont (if-cont conseq alt env cont) val)
    #   = (if val (value-of/k conseq env cont) (value-of/k alt env cont))
    _immutable_fields_ = ["conseq", "alt", "env", "cont"]

    def __init__(self, conseq, alt, env, cont):
        self.conseq = conseq
        self.alt = alt
        self.env = env
        self.cont = cont

    def apply_cont(self, val):
        if val is not FALSE:
            return self.conseq.eval_cps(self.env, self.cont)
        return self.alt.eval_cps(self.env, self.cont)


class AppCont(Cont):
    # 手続き呼出しの演算子・オペランドを左から右へ評価する途中 (仕様書 4.3節)。
    # vals はここまでに求めた値 (vals[0] が演算子)
    #   残りがある: (value-of/k e_i env (app-cont e* vals§⟨val⟩ env cont))
    #   残りがない: (apply-procedure/k vals[0] vals[1:] cont)
    _immutable_fields_ = ["app", "vals[*]", "env", "cont"]

    def __init__(self, app, vals, env, cont):
        self.app = app
        self.vals = vals
        self.env = env
        self.cont = cont

    def apply_cont(self, val):
        # 継続は何度でも呼ばれうるので vals は書き換えずに作り直す
        vals = self.vals + [val]
        rands = self.app.rands
        i = len(vals) - 1
        if i < len(rands):
            return rands[i].eval_cps(self.env, AppCont(self.app, vals, self.env, self.cont))
        return vals[0].apply_procedure_k(vals[1:], self.cont)


class SetLocalCont(Cont):
    # (apply-cont (set-cont (depth index) env cont) val)
    #   = (begin (setref! ...) (apply-cont cont unspecified))
    _immutable_fields_ = ["depth", "index", "env", "cont"]

    def __init__(self, depth, index, env, cont):
        self.depth = depth
        self.index = index
        self.env = env
        self.cont = cont

    def apply_cont(self, val):
        assign(self.env, self.depth, self.index, val)
        return self.cont.apply_cont(UNSPECIFIED)


class SetGlobalCont(Cont):
    # define の変数への set!。値が格納される前ならエラー (仕様書 4.7節)
    _immutable_fields_ = ["cell", "cont"]

    def __init__(self, cell, cont):
        self.cell = cell
        self.cont = cont

    def apply_cont(self, val):
        if self.cell.value is UNDEFINED:
            raise SchemeError()
        self.cell.value = val
        return self.cont.apply_cont(UNSPECIFIED)


class DefineCont(Cont):
    # 仕様書 8.4節 𝒟: 値を格納してから残りの定義と主式 rest に進む
    _immutable_fields_ = ["cell", "rest", "cont"]

    def __init__(self, cell, rest, cont):
        self.cell = cell
        self.rest = rest
        self.cont = cont

    def apply_cont(self, val):
        self.cell.value = val
        return self.rest.eval_cps(None, self.cont)
