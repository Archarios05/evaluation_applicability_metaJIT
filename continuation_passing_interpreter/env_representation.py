"EPL p38"
"フレームで環境を管理する"

from types import Var, Value
from types import Env


def lookup_variable_value(var : Var, env : Env) -> Value:
    #returns the value that is bound to the symbol ⟨var⟩ in the environment ⟨env ⟩, or signals an error if the variable is unbound.
    pass

def extend_env(var : Var, val : Value, env : Env) -> Env: 
    # returns a new environment, consisting of a new frame in whichthe symbols in the list ⟨variables⟩ are bound to the corresponding elements in the list ⟨values⟩, where the enclosing environment is the environment ⟨base-env ⟩
    pass

def define_variable(var : Var, val : Value, env : Env) -> None:
    # adds to the first frame in the environment ⟨env ⟩ a new binding that associates the variable ⟨var⟩ with the value ⟨value ⟩
    pass

def set_variable_value(var : Var, val : Value, env : Env) -> None:
    #changes the binding of the variable ⟨var⟩in the environment⟨env ⟩ so that the variable is now bound to the value ⟨value ⟩, or signals an error if the variable is unbound.