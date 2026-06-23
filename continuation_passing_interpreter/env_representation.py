"EPL p38"
""
from types import Var, Value
from continuation_interpreter.types import Env


def empty_env() -> Env:
    return {}

def extend_env(var : Var, val : Value, env : Env) -> Env:
    new_env = env.copy()
    new_env[var] = val
    return new_env