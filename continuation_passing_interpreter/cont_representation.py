# EOPL p148 図5.3 継続(Continuation)のデータ構造表現。
# 本文では apply-continuation が cont の種類ごとに case で振り分けるが、
# ここでは各 Cont サブクラスの apply_cont メソッドとして実装する
# (オブジェクト指向の仮想メソッドディスパッチ)。RPythonはmatch文を
# サポートしないため、この方式に一本化する。
#
# 設計原則: 継続は「構築時に確定している情報」だけをフィールドに保存し、
# apply_cont は評価結果の val ひとつだけを受け取って続きを実行する
# (val はcont構築時にはまだ計算されていないため、コンストラクタでは受け取らない)。
#
# 各 apply_cont は exp.eval_cps(...) / cont.apply_cont(...) を末尾で
# 呼ぶだけなので、Exp側のモジュールをimportする必要はない(ダックタイピング)。
# これにより interpreter.py <-> cont_representation.py の循環importも解消される。
from __future__ import annotations
import os
from classes import NumVal, BoolVal, ProcVal, expval_to_num, expval_to_bool


class Cont(object):
    def apply_cont(self, val):
        raise NotImplementedError


class EndCont(Cont):
    # EOPL p143
    # (apply-cont (end-cont) val) = (begin (eopl:printf "End of computation.~%") val)
    #
    # print()はCPythonの完全なI/Oスタックに依存し、RPython翻訳対象コードでは
    # 避けるのが定石(pypy-tutorial-jp/example5.pyのmainloopもos.writeを使用)。
    # os.write(fd, bytes)はRPythonでもCPython(このファイルを直接動かす場合)でも
    # 同じように動くため、これに統一する。
    def apply_cont(self, val):
        os.write(1, b"End of computation.\n")
        return val


class Zero1Cont(Cont):
    # EOPL p145
    # (apply-cont (zero1-cont cont) val)
    #   = (apply-cont cont (bool-val (zero? (expval->num val))))
    def __init__(self, saved_cont):
        self.saved_cont = saved_cont

    def apply_cont(self, val):
        return self.saved_cont.apply_cont(BoolVal(expval_to_num(val) == 0))


class IfTestCont(Cont):
    # EOPL p146
    # (apply-cont (if-test-cont exp2 exp3 env cont) val)
    #   = (if (expval->bool val)
    #         (value-of/k exp2 env cont)
    #         (value-of/k exp3 env cont))
    def __init__(self, exp2, exp3, saved_env, saved_cont):
        self.exp2 = exp2
        self.exp3 = exp3
        self.saved_env = saved_env
        self.saved_cont = saved_cont

    def apply_cont(self, val):
        if expval_to_bool(val):
            return self.exp2.eval_cps(self.saved_env, self.saved_cont)
        else:
            return self.exp3.eval_cps(self.saved_env, self.saved_cont)


class LetExpCont(Cont):
    # EOPL p146
    # (apply-cont (let-exp-cont var body env cont) val)
    #   = (value-of/k body (extend-env var val env) cont)
    def __init__(self, var, body, saved_env, saved_cont):
        self.var = var
        self.body = body
        self.saved_env = saved_env
        self.saved_cont = saved_cont

    def apply_cont(self, val):
        new_env = self.saved_env.extend_env([self.var], [val])
        return self.body.eval_cps(new_env, self.saved_cont)


class Diff1Cont(Cont):
    # EOPL p149
    # (apply-cont (diff1-cont exp2 env cont) val1)
    #   = (value-of/k exp2 env (diff2-cont val1 cont))
    def __init__(self, exp2, saved_env, saved_cont):
        self.exp2 = exp2
        self.saved_env = saved_env
        self.saved_cont = saved_cont

    def apply_cont(self, val1):
        return self.exp2.eval_cps(self.saved_env, Diff2Cont(val1, self.saved_cont))


class Diff2Cont(Cont):
    # EOPL p149
    # (apply-cont (diff2-cont val1 cont) val2)
    #   = (let ((num1 (expval->num val1)) (num2 (expval->num val2)))
    #       (apply-cont cont (num-val (- num1 num2))))
    def __init__(self, val1, saved_cont):
        self.val1 = val1
        self.saved_cont = saved_cont

    def apply_cont(self, val2):
        num1 = expval_to_num(self.val1)
        num2 = expval_to_num(val2)
        return self.saved_cont.apply_cont(NumVal(num1 - num2))


class RatorCont(Cont):
    # EOPL p151
    # (apply-cont (rator-cont rand env cont) val1)
    #   = (value-of/k rand env (rand-cont val1 cont))
    def __init__(self, rand, saved_env, saved_cont):
        self.rand = rand
        self.saved_env = saved_env
        self.saved_cont = saved_cont

    def apply_cont(self, val1):
        return self.rand.eval_cps(self.saved_env, RandCont(val1, self.saved_cont))


class RandCont(Cont):
    # EOPL p152
    # (apply-cont (rand-cont val1 cont) val2)
    #   = (let ((proc1 (expval->proc val1)))
    #       (apply-procedure/k proc1 val2 cont))
    def __init__(self, val1, saved_cont):
        self.val1 = val1
        self.saved_cont = saved_cont

    def apply_cont(self, val2):
        proc1 = self.val1
        if not isinstance(proc1, ProcVal):
            raise TypeError(
                "RandCont.apply_cont: 呼び出そうとした値がProcVal ではありません: %r" % (proc1,)
            )
        return proc1.apply_procedure_k(val2, self.saved_cont)


# 注記: 現状のvalue-of/k(exp_representation.pyのeval_cps)は末尾呼び出しの連鎖として
# 書かれているが、CPython自体は末尾呼び出し最適化を行わないため、再帰が深いプログラムでは
# 通常のPython呼び出しスタックを消費する。EOPL 5.2節のトランポリン化・5.3節のレジスタ化は
# この制約を回避するための後続ステップであり、今回のスコープには含めない。
