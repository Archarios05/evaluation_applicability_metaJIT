"EPL p38"
"フレームで環境を管理する"

from __future__ import annotations
from abc import ABC #Abstract Base Class: 抽象基底クラス
from dataclasses import dataclass

from env_representation import define_variable

from classes import Var, Value
from classes import Env

@dataclass(frozen=True)#SICPの3.2を参考に実装
class Env:
    def __init__(self:Env, enclosing_env : Env = None):
        self.frame = {}
        self.enclosing_env = enclosing_env
    def lookup_variable_value(self, var : Var) -> Value:
        #環境でvarに束縛されている値を返す、束縛されていない場合はエラー
        if  var in self.frame:
            return self.frame[var]
        elif self.enclosing_env is not None:
            return self.enclosing_env.lookup_variable_value(var)

    def extend_env(self, var : Var, val : Value) -> Env: 
        # returns a new environment, consisting of a new frame in whichthe symbols in the list ⟨variables⟩ are bound to the corresponding elements in the list ⟨values⟩, where the enclosing environment is the environment ⟨base-env ⟩
        if len(var) != len(val):
            if len(var)< len(val):
                raise ValueError("The number of variables is less than the number of values.")
            else:
                raise ValueError("The number of variables is greater than the number of values.")
        new_env = Env(self)
        for v, v_val in zip(var, val):
            define_variable(v, v_val, new_env)
        return new_env

    def define_variable(var : Var, val : Value, env : Env) -> None:
        # adds to the first frame in the environment ⟨env ⟩ a new binding that associates the variable ⟨var⟩ with the value ⟨value ⟩
        env.frame[var] = val

    def set_variable_value(var : Var, val : Value, env : Env) -> None:
        #changes the binding of the variable ⟨var⟩in the environment⟨env ⟩ so that the variable is now bound to the value ⟨value ⟩, or signals an error if the variable is unbound.
        if var in env.frame:
            env.frame[var] = val
        elif env.enclosing_env is not None:
            env.enclosing_env.set_variable_value(var, val, env)

