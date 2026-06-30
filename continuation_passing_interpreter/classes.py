from __future__ import annotations
from abc import ABC #Abstract Base Class: 抽象基底クラス
from dataclasses import dataclass
from typing import TypeAlias
from env_representation import define_variable
#envとcont以外はここに書く
#EPLのp148の図5.3のデータ構造表現に沿って書くための、classの定義
class Exp:
    pass

@dataclass(frozen=True)
class Value:
    
    pass

@dataclass(frozen=True)
class Var:
    name: str

@dataclass(frozen=True)
class BoolVal(Value):
    value: bool

FinalAnswer:TypeAlias = Value