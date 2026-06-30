from __future__ import annotations
from abc import ABC #Abstract Base Class: 抽象基底クラス
from dataclasses import dataclass
from typing import TypeAlias
from env_representation import define_variable
#envとcont以外はここに書く
class Exp:
    pass

@dataclass(frozen=True)
class Value:
    
    pass

@dataclass(frozen=True)
class Var:
    name: str


FinalAnswer:TypeAlias = Value