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


@dataclass(frozen=True)
class Cont:
    def endofcont()-> Cont:
        print("end of Cont")
        return Cont()

    def zero1cont(cont : Cont) -> Cont:
        cont.apply(NumVal(0))
        return Cont()

    def let_exp_cont(var : Var, body : Exp, env : Env, cont : Cont) -> Cont:
        val : Value 
        return valueofk(body, extend_env(var, val , cont))

        #tailcallが最適化されるかどうかを考えなきゃいけない
