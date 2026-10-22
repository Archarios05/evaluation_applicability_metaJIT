# -*- coding: utf-8 -*-
# トランポリンの Bounce (EOPL p159 Bounce = ExpVal ∪ (() -> Bounce))。
# 最終値の側は value.Value が Bounce を継承して表す。
# 依存関係の起点にした

class Bounce(object):
    # Scheme のクロージャ (lambda () ...) の代わりに、
    # まだ実行していない計算をデータとして持つ
    pass


class ApplyProcBounce(Bounce):
    # クロージャ適用の (lambda () (value-of/k body (extend-env ...) cont))。
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
