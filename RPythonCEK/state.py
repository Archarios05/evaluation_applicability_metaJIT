# -*- coding: utf-8 -*-
# CEK機械の「状態」の定義。
#
# CEK機械 (Felleisen & Friedman 1986) の状態は3つのレジスタからなる:
#
#     C (Control)      : いま注目している式         -> EvalState.exp
#     E (Environment)  : その式を評価する環境       -> EvalState.env
#     K (Kontinuation) : 残りの計算(継続)           -> *State.kont
#
# EOPL 5章のCPSインタプリタを
#   「継続をデータ構造化 (5.1節) → トランポリン化 (5.2節) → レジスタ化 (5.3節)」
# と進めた終着点がこれに当たる (Danvy らの functional correspondence:
#  評価器をCPS変換して継続を defunctionalize すると抽象機械が現れる)。
#
# 状態は2モードある。EOPLの value-of/k と apply-cont の2つの相互再帰関数が、
# そのまま2種類の状態に対応している:
#
#   EvalState <e, ρ, κ>  ... value-of/k 側。式をこれから評価する。
#   ContState <v, κ>     ... apply-cont 側。値が求まったので継続に渡す。
#   HaltState <v>        ... EndKont に到達し、機械が停止した。
#
# 重要な性質: step() は「次の状態」を*返すだけ*で、自分から次の step() を
# 呼ばない。したがってホスト(Python/C)の呼び出しスタックは一切伸びない。
# CPS版が apply_procedure_k のときだけトランポリンで解決していた問題が、
# CEKでは全ステップについて構造的に解決されている。
#
# このファイルは exp_representation / cont_representation のどちらもimportしない
# (ダックタイピングで exp.eval_step / kont.apply_kont を呼ぶだけ)。
# これにより import の循環が起きない。


class State(object):
    def step(self):
        # 1状態遷移だけ進めて、次の状態を返す。
        raise NotImplementedError

    def to_string(self):
        return "state"


class EvalState(State):
    # <e, ρ, κ>_eval : 式 e を環境 ρ のもとで評価しようとしている状態。
    # EOPL p143 (value-of/k exp env cont) に対応。
    def __init__(self, exp, env, kont):
        self.exp = exp
        self.env = env
        self.kont = kont

    def step(self):
        return self.exp.eval_step(self.env, self.kont)

    def to_string(self):
        return "eval <%s | %s>" % (self.exp.to_string(), self.kont.to_string())


class ContState(State):
    # <v, κ>_cont : 値 v が求まり、継続 κ に渡そうとしている状態。
    # EOPL p143 (apply-cont cont val) に対応。
    # 環境レジスタEはここでは不要 (必要な環境は κ の各フレームが保存している)。
    def __init__(self, val, kont):
        self.val = val
        self.kont = kont

    def step(self):
        return self.kont.apply_kont(self.val)

    def to_string(self):
        return "cont <%s | %s>" % (self.val.to_string(), self.kont.to_string())


class HaltState(State):
    # 停止状態。EndKont に値が渡された時点で機械は止まり、val が最終結果になる。
    def __init__(self, val):
        self.val = val

    def step(self):
        # 停止状態は自分自身へ遷移する(不動点)。
        return self

    def to_string(self):
        return "halt <%s>" % (self.val.to_string(),)
