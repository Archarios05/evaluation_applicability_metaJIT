from __future__ import annotations
from abc import ABC #Abstract Base Class: 抽象基底クラス
from dataclasses import dataclass

class Exp(ABC):
    """式の抽象基底クラス"""
    pass

@dataclass(frozen=True)
class Value(ABC):
    """値を表す抽象基底クラス"""
    pass


@dataclass(frozen=True)
class Continuation(ABC):
    """継続を表す抽象基底クラス"""
    pass

@dataclass(frozen=True)
class Env(ABC):
    """環境を表す抽象基底クラス"""
    pass

@dataclass(frozen=True)
class Variable(Exp):
    """変数を表す式"""
    name: str
