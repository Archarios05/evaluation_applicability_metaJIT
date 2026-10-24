# -*- coding: utf-8 -*-
# 環境 (CPSインタプリタの env 引数)。
# 変数は変換時に字句アドレス (depth, index) に置き換えてあるので (convert.py)、
# 実行時は名前で探さずフレームを depth 枚たどって vals[index] を読む (EOPL 3.7節)。
# フレームの各要素がR5RSの「場所」に当たる。set! はここを書き換え、
# 同じフレームを持つクロージャすべてから見える。
# トップ・レベルの環境は None。define の変数はフレームではなく GlobalCell に置く。
from rpy import unroll_safe


class Frame(object):
    _immutable_fields_ = ["parent"]

    def __init__(self, vals, parent):
        self.vals = vals
        self.parent = parent


@unroll_safe
def frame_at(env, depth):
    for i in range(depth):
        env = env.parent
    return env


def lookup(env, depth, index):
    return frame_at(env, depth).vals[index]


def assign(env, depth, index, val):
    frame_at(env, depth).vals[index] = val


class GlobalCell(object):
    # define の変数 1 個ぶんの場所。初期値は UNDEFINED
    def __init__(self, name, value):
        self.name = name
        self.value = value
