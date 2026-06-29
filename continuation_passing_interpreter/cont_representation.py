"EPL p147"
"figure 5.2"


from multiprocessing.sharedcclasses import Value
import sys
import os
from __future__ import annotations
from abc import ABC
from dataclasses import dataclass
from classes import *


from interpreter import valueofk
class Cont(ABC):
    def apply_cont(self, val : Value) -> FinalAnswer:
        pass

@dataclass(frozen=True)
class EndCont(Cont):
    def apply_cont(self, val : Value) -> FinalAnswer:
        return val#返すのはvalを返す、もうこれ以上の継続はないので、valを返す
    
@dataclass(frozen=True)
class Zero1Cont(Cont):
    _saved_cont : Cont
    
