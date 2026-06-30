#Essential of Programming Languages p148 Figure 5.3 Data structure representation of continuations
#本文中だと先にdatastructure representationを定義し、apply-continuationでcaseごとに振り分けているが、ここではclass内のメソッドとして実装する
import sys
import os
from __future__ import annotations
from abc import ABC
from dataclasses import dataclass
from classes import *
from env_representation import Env
from interpreter import valueofk


from interpreter import valueofk
class Cont(ABC):
    def apply_cont(self, val : Value) -> FinalAnswer:#後で書く
        pass

@dataclass(frozen=True)
class EndCont(Cont):
    def apply_cont(self, val : Value) -> FinalAnswer:
        return val#valを返す、もうこれ以上の継続はないので、valを返す
    
@dataclass(frozen=True)
class Zero1Cont(Cont):
    _saved_cont : Cont
    def apply_cont(self, saved_cont : Cont, val : Value) -> FinalAnswer:
        # val を数値として取り出し、ゼロ判定を行う (ExpVal -> bool)
        # 判定結果を新しい Value (BoolVal) としてラップする
        # self._saved_cont.apply_cont() にその値を渡す
        saved_cont.apply_cont(BoolVal(val == 0))
@dataclass(frozen=True)
class LetExpCont(Cont):
    _var : Var
    _saved_env : Env
    _saved_cont : Cont
    _body : str
    _val : Value
    def apply_cont(self, saved_cont : Cont, saved_env : Env,var : Var, body : str) -> FinalAnswer:
        valueofk(body, saved_env.extend_env(var, self._val), saved_cont)

@dataclass(frozen=True)
class IfTestCont(Cont):
    _exp2 : Exp
    _exp3 : Exp
    _saved_env : Env
    _saved_cont : Cont
    def apply_cont(self, saved_cont : Cont, saved_env : Env, exp2 : Exp, exp3 : Exp, val : Value) -> FinalAnswer:
        if val == True:
            valueofk(exp2, saved_env, saved_cont)
        else:
            valueofk(exp3, saved_env, saved_cont)



#tailcallが最適化されるかどうかを考えなきゃいけない
