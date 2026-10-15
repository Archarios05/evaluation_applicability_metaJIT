# -*- coding: utf-8 -*-
# 手続き値 (クロージャ) の定義。
# 呼び出し規則は RandKont.apply_kont 側にあるので、ここにメソッドは持たない。

from value import Value


class ProcVal(Value):
    # EOPL p147 procedure : Var x Exp x Env -> Proc
    def __init__(self, var, body, env):
        self.var = var
        self.body = body
        self.env = env

    def to_string(self):
        return "proc(%s)" % (self.var,)
