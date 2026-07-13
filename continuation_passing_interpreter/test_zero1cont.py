# -*- coding: utf-8 -*-
# Zero1Cont (cont_representation.py) の働きを確認するためのスクリプト。
# RPython翻訳は対象外なので、ここでは素のprint()を使う。
#
# EOPL p145: (apply-cont (zero1-cont cont) val)
#              = (apply-cont cont (bool-val (zero? (expval->num val))))
#
# ZeroExp.eval_cps は「exp1を評価してから、その結果(NumVal)をbool値に
# 変換して残りの継続へ渡す」ために Zero1Cont(saved_cont) を作って
# exp1 の評価に渡す。つまり Zero1Cont は「NumVal -> BoolVal への変換だけを
# 行い、あとはsaved_contにそのまま委譲する」継続そのものである。
from exp_representation import ZeroExp, DiffExp, ConstExp, VarExp
from cont_representation import Cont, Zero1Cont
from interpreter import value_of_program
from classes import expval_to_bool


class TraceCont(Cont):
    # Zero1Cont に渡すsaved_cont役。apply_contに来た値をそのまま観察して
    # 表示するだけの継続で、Zero1Contが「何を」渡してくるかを可視化する。
    def __init__(self, label):
        self.label = label

    def apply_cont(self, val):
        print("%s: Zero1Cont から渡された値 = %r (%s)" % (
            self.label, val, val.__class__.__name__,
        ))
        return val


def demo_direct_zero1cont():
    # Zero1Contを直接組み立てて apply_cont に NumVal を渡してみる。
    # ZeroExpを経由せず、Zero1Cont単体の変換規則だけを確認する。
    print("=== Zero1Cont を直接呼び出す ===")
    from classes import NumVal

    cont = Zero1Cont(TraceCont("direct"))
    print("入力: NumVal(0)  (0はzeroなので True になるはず)")
    cont.apply_cont(NumVal(0))

    print("入力: NumVal(7)  (0ではないので False になるはず)")
    cont.apply_cont(NumVal(7))


def demo_zero_exp(name, exp):
    # ZeroExp.eval_cps -> exp1.eval_cps(env, Zero1Cont(cont)) という
    # 実際の評価経路を通して Zero1Cont が使われる様子を確認する。
    print("=== %s ===" % name)
    result = value_of_program(exp)
    print("%s => %r" % (name, expval_to_bool(result)))
    print("")


if __name__ == "__main__":
    demo_direct_zero1cont()
    print("")

    # init_env() = [i=1, v=5, x=10]
    # zero?(-(x,x)) = zero?(10-10) = zero?(0) => True
    demo_zero_exp(
        "zero_true: zero?(-(x,x))",
        ZeroExp(DiffExp(VarExp("x"), VarExp("x"))),
    )

    # zero?(-(x,3)) = zero?(10-3) = zero?(7) => False
    demo_zero_exp(
        "zero_false: zero?(-(x,3))",
        ZeroExp(DiffExp(VarExp("x"), ConstExp(3))),
    )
