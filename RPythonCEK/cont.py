# -*- coding: utf-8 -*-
# CEK機械の K レジスタ = 継続フレームの定義。
# フレームの種類は CPS版 (continuation_passing_interpreter/cont.py) と同じ。
#
# CPS版との違い:
#   CPS版 apply_cont は次の計算を自分で呼び出す
#       return self.conseq.eval_cps(self.env, self.cont)
#   CEK版 apply_kont は次の状態を返すだけ
#       return EvalState(self.conseq, self.env, self.kont)
# これによりホストの呼び出しスタックが伸びず、machine.py のループだけが回る。
#
# 継続は構築時に確定している情報だけを持ち、apply_kont は値 val だけを受け取る。
from value import SchemeError, FALSE, UNSPECIFIED, UNDEFINED
from env import assign
from state import EvalState, ContState, HaltState


class Kont(object):
    def apply_kont(self, val):
        # <val, self>_cont から次の状態への遷移規則
        raise NotImplementedError

    def to_string(self):
        return "kont"


class EndKont(Kont):
    # 初期継続 κ0。主式の値は出力しない
    def apply_kont(self, val):
        return HaltState(val)

    def to_string(self):
        return "end"


class IfKont(Kont):
    # <v, (if conseq alt ρ κ)>_cont -> <conseq, ρ, κ> (v が #f 以外) / <alt, ρ, κ>
    _immutable_fields_ = ["conseq", "alt", "env", "kont"]

    def __init__(self, conseq, alt, env, kont):
        self.conseq = conseq
        self.alt = alt
        self.env = env
        self.kont = kont

    def apply_kont(self, val):
        if val is not FALSE:
            return EvalState(self.conseq, self.env, self.kont)
        return EvalState(self.alt, self.env, self.kont)

    def to_string(self):
        return "if"


class AppKont(Kont):
    # 手続き呼出しの演算子・オペランドを左から右へ評価する途中。
    # vals はここまでに求めた値 (vals[0] が演算子)
    #   <v, (app e* vals ρ κ)>_cont -> <e_i, ρ, (app e* vals§⟨v⟩ ρ κ)>  (残りがある)
    #                                -> vals§⟨v⟩ を適用                (残りがない)
    _immutable_fields_ = ["app", "vals[*]", "env", "kont"]

    def __init__(self, app, vals, env, kont):
        self.app = app
        self.vals = vals
        self.env = env
        self.kont = kont

    def apply_kont(self, val):
        # 継続は何度でも呼ばれうるので vals は書き換えずに作り直す
        vals = self.vals + [val]
        rands = self.app.rands
        i = len(vals) - 1
        if i < len(rands):
            return EvalState(rands[i], self.env, AppKont(self.app, vals, self.env, self.kont))
        return vals[0].apply_procedure(vals[1:], self.kont)

    def to_string(self):
        return "app"


class SetLocalKont(Kont):
    # <v, (set! (depth index) ρ κ)>_cont -> <unspecified, κ>  (場所に v を格納)
    _immutable_fields_ = ["depth", "index", "env", "kont"]

    def __init__(self, depth, index, env, kont):
        self.depth = depth
        self.index = index
        self.env = env
        self.kont = kont

    def apply_kont(self, val):
        assign(self.env, self.depth, self.index, val)
        return ContState(UNSPECIFIED, self.kont)

    def to_string(self):
        return "set!"


class SetGlobalKont(Kont):
    # define の変数への set!。値が格納される前ならエラー
    _immutable_fields_ = ["cell", "kont"]

    def __init__(self, cell, kont):
        self.cell = cell
        self.kont = kont

    def apply_kont(self, val):
        if self.cell.value is UNDEFINED:
            raise SchemeError()
        self.cell.value = val
        return ContState(UNSPECIFIED, self.kont)

    def to_string(self):
        return "set!"


class DefineKont(Kont):
    # 値を格納してから残りの定義と主式 rest に進む
    #   <v, (define cell rest κ)>_cont -> <rest, ρ, κ>
    _immutable_fields_ = ["cell", "rest", "kont"]

    def __init__(self, cell, rest, kont):
        self.cell = cell
        self.rest = rest
        self.kont = kont

    def apply_kont(self, val):
        self.cell.value = val
        return EvalState(self.rest, None, self.kont)

    def to_string(self):
        return "define"
