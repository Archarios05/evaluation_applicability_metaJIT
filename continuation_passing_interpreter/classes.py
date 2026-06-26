from __future__ import annotations
from abc import ABC #Abstract Base Class: 抽象基底クラス
from dataclasses import dataclass

from env_representation import define_variable

class Exp:
    
    pass

@dataclass(frozen=True)
class Value:
    
    pass


@dataclass(frozen=True)
class Continuation:
    pass


@dataclass(frozen=True)
class Var:
    
    name: str
