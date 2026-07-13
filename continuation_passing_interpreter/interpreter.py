# -*- coding: utf-8 -*-
# EOPL p143 value-of-program / value-of/k のエントリポイント。
#
# 実際のディスパッチは各Exp/Contのメソッド(eval_cps/apply_cont)が担うので、
# ここでの valueofk は本文のcontractとの対応を残すために残してるのであまり意味はないと思う
# JIT化するためにはexample5.pyのようにjitdriverを置く必要があるが、ここではやっていない。
from env_representation import init_env
from cont_representation import EndCont


def valueofk(exp, env, cont):
    # EOPL p143 value-of/k : Exp x Env x Cont -> FinalAnswer
    return exp.eval_cps(env, cont)


def value_of_program(exp):
    # EOPL p143 value-of-program : Program -> FinalAnswer
    # (a-programによるラップは省略し、Exp自体をプログラムとして扱う)
    return valueofk(exp, init_env(), EndCont())
    #endcontを渡すことで、最終的に計算結果を返すようにする


def run(exp):
    return value_of_program(exp)
