"EPL p147"
"figure 5.2"


from multiprocessing.sharedctypes import Value
import sys
import os
from __future__ import annotations
from abc import ABC
from dataclasses import dataclass
from types import *

from interpreter import valueofk



def endofcont()-> Continuation:
    print("end of continuation")
    return Continuation()

def zero1cont(cont : Continuation) -> Continuation:
    cont.apply(NumVal(0))
    return Continuation()

def let_exp_cont(var : Var, body : Exp, env : Env, cont : Continuation) -> Continuation:
    val : value 
    return valueofk(body, extend_env(var, val  , env), cont)
