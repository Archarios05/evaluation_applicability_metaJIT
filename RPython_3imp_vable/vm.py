# -*- coding: utf-8 -*-
# スタックベースの VM。3imp-4.3+4.4+4.5.scm の VM を PyPy 型のフレームに分けたもの
# レジスタ: a (アキュムレータ) pc (3imp の x) f (フレーム) c (クロージャ) s (スタックトップ)
#
# 3imp との違い:
#   1 本の大きなスタックの代わりに、clambda の呼出しごとに固定長のフレーム Frame を作る。
#   Frame は JIT の virtualizable で、スロットへの読み書きはトレース中では消える。
#   f と s はそのフレーム内の位置で、pc ごとに一定 (codegen.max_depth)。
#   末尾でない clambda の呼出しは execute の再帰 (PyPy と同じ)、末尾呼出しはフレームを使い回す。
#   継続はホストの再帰をまたげないので、生きているフレームへ戻る (脱出する) ものだけ呼べる。
from RPython_3imp_vable.rpy import JitDriver, dont_look_inside, unroll_safe, promote, hint
from RPython_3imp_vable.value import (SchemeError, W_Object, W_Box, W_Frame, W_Closure,
                   W_Functional, W_Primitive, W_Continuation, W_Procedure, W_FALSE,
                   W_UNDEFINED, W_UNSPECIFIED)
from RPython_3imp_vable.primitives import P_CWCC, call_primitive
from RPython_3imp_vable.opcodes import (HALT, CONSTANT, REFER, REFER_FREE, REFER_GLOBAL,
                     INDIRECT, FUNCTIONAL, CLOSE, BOX, TEST, JUMP, ASSIGN, ASSIGN_GLOBAL,
                     FRAME, ARGUMENT, SHIFT, APPLY, RETURN, ASSIGN_FREE, DEFINE_GLOBAL)


def get_location(pc, code):
    return code.describe(pc)


jitdriver = JitDriver(greens=["pc", "code"], reds=["f", "s", "a", "c", "frame", "vm"],
                      virtualizables=["frame"], get_printable_location=get_location)


class Frame(object):
    _virtualizable_ = ["slots[*]"]

    def __init__(self, size):
        self = hint(self, access_directly=True, fresh_virtualizable=True)
        self.slots = [None] * size
        self.live = True

    def get(self, i):
        assert i >= 0
        return self.slots[i]

    def set(self, i, w):
        assert i >= 0
        self.slots[i] = w


class ContinuationThrow(Exception):
    # 継続 k を値 val で呼んだ。k.frame の execute まで巻き戻す
    def __init__(self, k, val):
        self.k = k
        self.val = val


@dont_look_inside
def save_frame(frame, s):
    saved = [None] * s
    for i in range(s):
        saved[i] = frame.slots[i]
    return saved


@dont_look_inside
def restore_frame(frame, saved):
    for i in range(len(saved)):
        frame.slots[i] = saved[i]
    return len(saved)


@unroll_safe
def find_link(frame, n, f):
    while n > 0:
        fn = frame.get(f - 1)
        assert isinstance(fn, W_Functional)
        f = fn.link
        n -= 1
    return f


class VM(object):
    def __init__(self, code):
        self.code = code
        n = len(code.initial_globals)
        self.globals_w = [None] * n
        for i in range(n):
            self.globals_w[i] = code.initial_globals[i]

    def run(self):
        return self.execute(Frame(self.code.frame_size), 0, 0, 0, None)

    def execute(self, frame, pc, f, s, c):
        code = self.code
        a = W_UNSPECIFIED
        while True:
            jitdriver.jit_merge_point(pc=pc, code=code, a=a, f=f, c=c, s=s, frame=frame, vm=self)
            s = promote(s)
            f = promote(f)
            ops = code.ops
            op = ops[pc]
            if op == CONSTANT:
                a = code.consts[ops[pc + 1]]
                pc += 2
            elif op == REFER:
                a = frame.get(find_link(frame, ops[pc + 1], f) + ops[pc + 2])
                pc += 3
            elif op == REFER_FREE:
                assert c is not None
                a = c.free[ops[pc + 1]]
                pc += 2
            elif op == REFER_GLOBAL:
                a = self.globals_w[ops[pc + 1]]
                if a is W_UNDEFINED:
                    raise SchemeError()
                pc += 2
            elif op == INDIRECT:
                assert isinstance(a, W_Box)
                a = a.value
                pc += 1
            elif op == FUNCTIONAL:
                a = W_Functional(pc + 3, ops[pc + 1], f)
                pc = ops[pc + 2]
            elif op == CLOSE:
                n = ops[pc + 1]
                free = [None] * n
                for i in range(n):
                    free[i] = frame.get(s - n + i)
                a = W_Closure(pc + 4, ops[pc + 2], free)
                s -= n
                pc = ops[pc + 3]
            elif op == BOX:
                i = f + ops[pc + 1]
                frame.set(i, W_Box(frame.get(i)))
                pc += 2
            elif op == TEST:
                if a is W_FALSE:
                    pc = ops[pc + 1]
                else:
                    pc += 2
            elif op == JUMP:
                pc = ops[pc + 1]
            elif op == ASSIGN:
                box = frame.get(find_link(frame, ops[pc + 1], f) + ops[pc + 2])
                assert isinstance(box, W_Box)
                box.value = a
                a = W_UNSPECIFIED
                pc += 3
            elif op == ASSIGN_FREE:
                assert c is not None
                box = c.free[ops[pc + 1]]
                assert isinstance(box, W_Box)
                box.value = a
                a = W_UNSPECIFIED
                pc += 2
            elif op == ASSIGN_GLOBAL:
                i = ops[pc + 1]
                if self.globals_w[i] is W_UNDEFINED:
                    raise SchemeError()
                self.globals_w[i] = a
                a = W_UNSPECIFIED
                pc += 2
            elif op == DEFINE_GLOBAL:
                self.globals_w[ops[pc + 1]] = a
                pc += 2
            elif op == FRAME:
                frame.set(s, W_Frame(ops[pc + 1], f, c))
                s += 1
                pc += 2
            elif op == ARGUMENT:
                frame.set(s, a)
                s += 1
                pc += 1
            elif op == SHIFT:
                n = ops[pc + 1]
                k = ops[pc + 2]
                for i in range(n):
                    frame.set(s - k - n + i, frame.get(s - n + i))
                s -= k
                pc += 3
            elif op == APPLY:
                n = ops[pc + 1]
                proc = frame.get(s - n - 1)
                while isinstance(proc, W_Primitive) and proc.pid == P_CWCC:
                    # (call/cc p) を (p k) への呼出しに置き換える
                    if n != 1:
                        raise SchemeError()
                    p = frame.get(s - 1)
                    if not isinstance(p, W_Procedure):
                        raise SchemeError()
                    k = W_Continuation(save_frame(frame, s - 2), frame)
                    frame.set(s - 2, p)
                    frame.set(s - 1, k)
                    proc = p
                if isinstance(proc, W_Closure):
                    if proc.nparams != n:
                        raise SchemeError()
                    if s - n - 1 == 0:
                        # 末尾呼出し。手続きと引数はもう 0 番から並んでいる
                        f = 1
                        c = proc
                        newpc = proc.body
                        back = newpc < pc
                        pc = newpc
                        if back:
                            jitdriver.can_enter_jit(pc=pc, code=code, a=a, f=f, c=c, s=s,
                                                    frame=frame, vm=self)
                        continue
                    # 手続きと引数を新しいフレームに移して execute を再帰で呼ぶ。
                    # frame を別の関数に渡すと JIT が frame を実体化するので、ここに直接書く
                    callee = Frame(code.frame_size)
                    for i in range(n + 1):
                        callee.set(i, frame.get(s - n - 1 + i))
                    try:
                        a = self.execute(callee, proc.body, 1, n + 1, proc)
                        callee.live = False
                        s -= n + 1
                    except ContinuationThrow as e:
                        callee.live = False
                        if e.k.frame is not frame:
                            raise
                        a = e.val
                        s = restore_frame(frame, e.k.saved)
                elif isinstance(proc, W_Functional):
                    if proc.nparams != n:
                        raise SchemeError()
                    f = s - n
                    newpc = proc.body
                    back = newpc < pc
                    pc = newpc
                    if back:
                        jitdriver.can_enter_jit(pc=pc, code=code, a=a, f=f, c=c, s=s,
                                                frame=frame, vm=self)
                    continue
                elif isinstance(proc, W_Primitive):
                    if proc.arity != n:
                        raise SchemeError()
                    x = None
                    y = None
                    if n >= 1:
                        x = frame.get(s - n)
                    if n >= 2:
                        y = frame.get(s - n + 1)
                    a = call_primitive(proc.pid, x, y)
                    s -= n + 1
                elif isinstance(proc, W_Continuation):
                    if n != 1:
                        raise SchemeError()
                    a = frame.get(s - 1)
                    if proc.frame is not frame:
                        if not proc.frame.live:
                            raise SchemeError()
                        raise ContinuationThrow(proc, a)
                    s = restore_frame(frame, proc.saved)
                else:
                    raise SchemeError()
                if s == 0:
                    return a
                frame_w = frame.get(s - 1)
                assert isinstance(frame_w, W_Frame)
                s -= 1
                newpc = frame_w.ret
                f = frame_w.fp
                c = frame_w.closure
                back = newpc < pc
                pc = newpc
                if back:
                    jitdriver.can_enter_jit(pc=pc, code=code, a=a, f=f, c=c, s=s,
                                            frame=frame, vm=self)
            elif op == RETURN:
                s -= ops[pc + 1]
                if s == 0:
                    return a
                frame_w = frame.get(s - 1)
                assert isinstance(frame_w, W_Frame)
                s -= 1
                newpc = frame_w.ret
                f = frame_w.fp
                c = frame_w.closure
                back = newpc < pc
                pc = newpc
                if back:
                    jitdriver.can_enter_jit(pc=pc, code=code, a=a, f=f, c=c, s=s,
                                            frame=frame, vm=self)
            elif op == HALT:
                return a
            else:
                assert False


def run_code(code):
    return VM(code).run()
