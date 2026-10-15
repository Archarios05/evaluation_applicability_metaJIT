# -*- coding: utf-8 -*-
"""EOPL p38 / SICP 3.2, 4.1.3 のフレーム方式で環境(CEKの E レジスタ)を管理する。

continuation_passing_interpreter/env_representation.py とほぼ同じ。
違いは lookup_variable_value が未束縛変数で None を返さずエラーにする点だけ

"""
from value import NumVal
from proc import ProcVal


class Env(object):
    def __init__(self, enclosing_env=None):
        self.frame = {}
        self.enclosing_env = enclosing_env

    def lookup_variable_value(self, var):
        # 環境で var に束縛されている値を返す。束縛されていない場合はエラー。
        env = self
        while env is not None:
            if var in env.frame:
                return env.frame[var]
            env = env.enclosing_env
        raise ValueError("unbound variable: %s" % (var,))

    def extend_env(self, var, val):
        # 新しいフレームを1枚積んだ環境を返す (base-env は self)。
        if len(var) != len(val):
            if len(var) < len(val):
                raise ValueError("The number of variables is less than the number of values.")
            else:
                raise ValueError("The number of variables is greater than the number of values.")
        new_env = Env(self)
        for i in range(len(var)):
            new_env.define_variable(var[i], val[i])
        return new_env

    def define_variable(self, var, val):
        # 先頭フレームに var -> val の束縛を追加する。
        self.frame[var] = val

    def set_variable_value(self, var, val):
        # 既存の束縛を書き換える。未束縛ならエラー。
        env = self
        while env is not None:
            if var in env.frame:
                env.frame[var] = val
                return
            env = env.enclosing_env
        raise ValueError("unbound variable: %s" % (var,))

    def extend_env_rec(self, p_name, b_var, p_body):
        # EOPL p154 letrec-exp: extend-env-rec p-name b-var p-body env
        # p_name が (proc (b_var) p_body) を指す手続きに束縛された新しい環境を返す。
        # その手続きの「保存環境」として new_env 自身を使うことで、
        # p_body の中から p_name を再帰的に呼び出せるようにする。
        new_env = Env(self)
        proc_val = ProcVal(b_var, p_body, new_env)
        new_env.define_variable(p_name, proc_val)
        return new_env


def init_env():
    # EOPL p69 init-env : () -> Env  usage: (init-env) = [i=1,v=5,x=10]
    env = Env()
    env = env.extend_env(["i"], [NumVal(1)])
    env = env.extend_env(["v"], [NumVal(5)])
    env = env.extend_env(["x"], [NumVal(10)])
    return env
