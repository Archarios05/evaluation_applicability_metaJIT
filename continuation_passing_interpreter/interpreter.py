import sys
import os
from __future__ import annotations
from abc import ABC
from dataclasses import dataclass
from classes import *
from continuation_passing_interpreter.cont_representation import Cont
from continuation_passing_interpreter.env_representation import Env

def valueofk(exp : Exp , env : Env, cont : Cont) -> FinalAnswer:
    match exp:
        case ConstExp(num : int):
            cont.apply_cont(NumVal(num))
        case VarExp(var : Var):
            val = env.lookup_variable_value(var)
            cont.apply_cont(val)
        case ProcExp(var : Var, body : Exp):
            cont.apply_cont(ProcVal(var, body, env))
            