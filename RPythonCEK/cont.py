# -*- coding: utf-8 -*-
# CEK機械の K レジスタ = 継続(Kontinuation)フレームの定義。
# EOPL p148 図5.3 のデータ構造表現をそのまま流用しているので、
# フレームの種類も保存フィールドも continuation_passing_interpreter と同一。
#
# CPS版との唯一にして決定的な違い:
#   CPS版 apply_cont は「次の計算を*自分で呼び出して*その結果を返す」
#       return self.exp2.eval_cps(self.saved_env, self.saved_cont)   # ← 再帰呼び出し
#   CEK版 apply_kont は「次の*状態*を作って返すだけ」
#       return EvalState(self.exp2, self.saved_env, self.saved_kont) # ← 呼び出さない
# これによりホストの呼び出しスタックが伸びず、機械のループ(machine.py)だけが回る。
#
# 継続は「構築時に確定している情報」だけをフィールドに保存し、
# apply_kont は評価結果の val ひとつだけを受け取る(EOPL p148 の設計原則)。
import os
from classes import NumVal, BoolVal, ProcVal, expval_to_num, expval_to_bool
from state import EvalState, ContState, HaltState


class Kont(object):
    def apply_kont(self, val):
        # <val, self>_cont から次の状態への遷移規則。State を返すだけ。
        raise NotImplementedError

    def to_string(self):
        return "kont"


class EndKont(Kont):
    # EOPL p143 (end-cont)
    # (apply-cont (end-cont) val) = (begin (printf "End of computation.") val)
    # CEKでは「機械を停止させる」フレームであり、HaltState を返す。
    #
    # print() はCPythonの完全なI/Oスタックに依存し、RPython翻訳対象コードでは
    # 避けるのが定石なので os.write に統一する(CPS版と同じ)。
    def apply_kont(self, val):
        os.write(1, "End of computation.\n")
        return HaltState(val)

    def to_string(self):
        return "end"


class Zero1Kont(Kont):
    # EOPL p145
    # <v, (zero1-kont κ)>_cont -> <(bool-val (zero? v)), κ>_cont
    def __init__(self, saved_kont):
        self.saved_kont = saved_kont

    def apply_kont(self, val):
        return ContState(BoolVal(expval_to_num(val) == 0), self.saved_kont)

    def to_string(self):
        return "zero1"


class IfTestKont(Kont):
    # EOPL p146
    # <v, (if-test-kont e2 e3 ρ κ)>_cont
    #   -> <e2, ρ, κ>_eval  (v が真)
    #   -> <e3, ρ, κ>_eval  (v が偽)
    def __init__(self, exp2, exp3, saved_env, saved_kont):
        self.exp2 = exp2
        self.exp3 = exp3
        self.saved_env = saved_env
        self.saved_kont = saved_kont

    def apply_kont(self, val):
        if expval_to_bool(val):
            return EvalState(self.exp2, self.saved_env, self.saved_kont)
        else:
            return EvalState(self.exp3, self.saved_env, self.saved_kont)

    def to_string(self):
        return "if-test"


class LetKont(Kont):
    # EOPL p146
    # <v, (let-kont x body ρ κ)>_cont -> <body, ρ[x=v], κ>_eval
    def __init__(self, var, body, saved_env, saved_kont):
        self.var = var
        self.body = body
        self.saved_env = saved_env
        self.saved_kont = saved_kont

    def apply_kont(self, val):
        new_env = self.saved_env.extend_env([self.var], [val])
        return EvalState(self.body, new_env, self.saved_kont)

    def to_string(self):
        return "let"


class Diff1Kont(Kont):
    # EOPL p149
    # <v1, (diff1-kont e2 ρ κ)>_cont -> <e2, ρ, (diff2-kont v1 κ)>_eval
    def __init__(self, exp2, saved_env, saved_kont):
        self.exp2 = exp2
        self.saved_env = saved_env
        self.saved_kont = saved_kont

    def apply_kont(self, val1):
        return EvalState(self.exp2, self.saved_env, Diff2Kont(val1, self.saved_kont))

    def to_string(self):
        return "diff1"


class Diff2Kont(Kont):
    # EOPL p149
    # <v2, (diff2-kont v1 κ)>_cont -> <(num-val (- v1 v2)), κ>_cont
    def __init__(self, val1, saved_kont):
        self.val1 = val1
        self.saved_kont = saved_kont

    def apply_kont(self, val2):
        num1 = expval_to_num(self.val1)
        num2 = expval_to_num(val2)
        return ContState(NumVal(num1 - num2), self.saved_kont)

    def to_string(self):
        return "diff2"


class Print1Kont(Kont):
    # 独自拡張: <v, (print1-kont κ)>_cont -> (副作用で v を出力) -> <v, κ>_cont
    # 値そのものは変えずに継続へ渡す。
    def __init__(self, saved_kont):
        self.saved_kont = saved_kont

    def apply_kont(self, val):
        os.write(1, "%d\n" % (expval_to_num(val),))
        return ContState(val, self.saved_kont)

    def to_string(self):
        return "print1"


class RatorKont(Kont):
    # EOPL p151
    # <v1, (rator-kont rand ρ κ)>_cont -> <rand, ρ, (rand-kont v1 κ)>_eval
    def __init__(self, rand, saved_env, saved_kont):
        self.rand = rand
        self.saved_env = saved_env
        self.saved_kont = saved_kont

    def apply_kont(self, val1):
        return EvalState(self.rand, self.saved_env, RandKont(val1, self.saved_kont))

    def to_string(self):
        return "rator"


class RandKont(Kont):
    # EOPL p152 / CEK機械の β 規則(手続き適用)そのもの。
    # <v2, (rand-kont (closure x body ρ') κ)>_cont -> <body, ρ'[x=v2], κ>_eval
    #
    # ここがCPS版との一番大きな差:
    #   CPS版は proc.apply_procedure_k(val2, cont) を呼び、その中で
    #   ApplyProcBounce を作ってトランポリンに戻す、という2段構えだった。
    #   CEK版では「クロージャの本体へ制御を移す」ことが単なる1状態遷移なので、
    #   Bounce のような専用の中間表現がそもそも要らない。
    def __init__(self, val1, saved_kont):
        self.val1 = val1
        self.saved_kont = saved_kont

    def apply_kont(self, val2):
        proc1 = self.val1
        if not isinstance(proc1, ProcVal):
            raise TypeError(
                "RandKont.apply_kont: 呼び出そうとした値がProcValではありません: %s"
                % (proc1.to_string(),)
            )
        new_env = proc1.env.extend_env([proc1.var], [val2])
        return EvalState(proc1.body, new_env, self.saved_kont)

    def to_string(self):
        return "rand"
