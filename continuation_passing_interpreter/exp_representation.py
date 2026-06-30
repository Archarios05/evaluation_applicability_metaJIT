import sys
import os
from __future__ import annotations
from dataclasses import dataclass
from classes import *
from continuation_passing_interpreter.cont_representation import Cont, IfTestCont
from env_representation import Env
from interpreter import valueofk

class Exp(object):
    def __init__(self):
        pass
    
    def eval_cps(self, env : Env, cont : Cont) -> FinalAnswer:
        raise NotImplementedError("eval_cps method must be implemented in subclasses of Exp.")
    
class ConstExp(Exp):
    def __init__(self, num : int):
        self.num = num
    def eval_cps(self, env : Env, cont : Cont) -> FinalAnswer:
        cont.apply_cont(NumVal(self.num))

class VarExp(Exp):
    def __init__(self, var : Var):
        self.var = var
    def eval_cps(self, env : Env, cont : Cont) -> FinalAnswer:
        val = env.lookup_variable_value(self.var)
        cont.apply_cont(val)

class IfExp(Exp):
    def __init__(self, exp1 : Exp, exp2 : Exp, exp3 : Exp):
        self.exp1 = exp1
        self.exp2 = exp2
        self.exp3 = exp3
    def eval_cps(self, env : Env, cont : Cont) -> FinalAnswer:
        valueofk(self.exp1, env, IfTestCont(self.exp2, self.exp3, env, cont))