# -*- coding: utf-8 -*-
"""EPL p38 フレームで環境を管理する"""

# RPython(Python2のサブセット)で翻訳するため、Python3専用構文
# (from __future__ import annotations, 引数注釈)は使わない。
# Python2には引数注釈(: Type / -> Type)の構文自体が存在しないため、
# postponed evaluationでは回避できない(パース時点でSyntaxErrorになる)。
from classes import ProcVal, NumVal

#SICPの3.2、4.1.3を参考に実装
class Env(object):
    def __init__(self, enclosing_env=None):
        self.frame = {}
        self.enclosing_env = enclosing_env

    def lookup_variable_value(self, var):
        #環境でvarに束縛されている値を返す、束縛されていない場合はエラー
        if  var in self.frame:
            return self.frame[var]
        elif self.enclosing_env is not None:
            return self.enclosing_env.lookup_variable_value(var)

    def extend_env(self, var, val):
        # returns a new environment, consisting of a new frame in whichthe symbols in the list ⟨variables⟩ are bound to the corresponding elements in the list ⟨values⟩, where the enclosing environment is the environment ⟨base-env ⟩
        if len(var) != len(val):
            if len(var)< len(val):
                raise ValueError("The number of variables is less than the number of values.")
            else:
                raise ValueError("The number of variables is greater than the number of values.")
        new_env = Env(self)
        for i in range(len(var)):
            new_env.define_variable(var[i], val[i])
        return new_env

    def define_variable(self, var, val):
        # adds to the first frame in the environment ⟨env ⟩ a new binding that associates the variable ⟨var⟩ with the value ⟨value ⟩
        self.frame[var] = val

    def set_variable_value(self, var, val):
        #changes the binding of the variable ⟨var⟩in the environment⟨env ⟩ so that the variable is now bound to the value ⟨value ⟩, or signals an error if the variable is unbound.
        if var in self.frame:
            self.frame[var] = val
        elif self.enclosing_env is not None:
            self.enclosing_env.set_variable_value(var, val)

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
