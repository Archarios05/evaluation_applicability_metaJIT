from __future__ import annotations
from abc import ABC #Abstract Base Class: 抽象基底クラス
from dataclasses import dataclass

class Exp:
    
    pass

@dataclass(frozen=True)
class Value:
    
    pass


@dataclass(frozen=True)
class Continuation:
    pass

@dataclass(frozen=True)#SICPの3.2を参考に実装
class Env:
    def __init__(self:Env, enclosing_env : Env = None):
        self.frame = {}
        self.enclosing_env = enclosing_env
    def lookup_variable_value(var : Var, env : Env) -> Value:
        #環境でvarに束縛されている値を返す、束縛されていない場合はエラー
        if 

    def extend_env(var : Var, val : Value, env : Env) -> Env: 
        # returns a new environment, consisting of a new frame in whichthe symbols in the list ⟨variables⟩ are bound to the corresponding elements in the list ⟨values⟩, where the enclosing environment is the environment ⟨base-env ⟩
        pass

    def define_variable(var : Var, val : Value, env : Env) -> None:
        # adds to the first frame in the environment ⟨env ⟩ a new binding that associates the variable ⟨var⟩ with the value ⟨value ⟩
        pass

    def set_variable_value(var : Var, val : Value, env : Env) -> None:
        #changes the binding of the variable ⟨var⟩in the environment⟨env ⟩ so that the variable is now bound to the value ⟨value ⟩, or signals an error if the variable is unbound.

@dataclass(frozen=True)
class Var:
    
    name: str
