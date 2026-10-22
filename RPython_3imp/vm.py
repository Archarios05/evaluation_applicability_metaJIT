# -*- coding: utf-8 -*-
# スタックベースの VM。3imp-4.3+4.4+4.5.scm の VM に相当
# レジスタ: a (アキュムレータ) pc (3imp の x) f (フレーム) c (クロージャ) s (スタックトップ)
from RPython_3imp.rpy import JitDriver, dont_look_inside, unroll_safe
from RPython_3imp.value import (SchemeError, W_Object, W_Box, W_Frame, W_Closure, W_Functional,
                   W_Primitive, W_Continuation, W_Procedure, W_FALSE, W_UNDEFINED,
                   W_UNSPECIFIED)
from RPython_3imp.primitives import P_CWCC, call_primitive
from RPython_3imp.opcodes import (HALT, CONSTANT, REFER, REFER_FREE, REFER_GLOBAL, INDIRECT,
                     FUNCTIONAL, CLOSE, BOX, TEST, JUMP, ASSIGN, ASSIGN_GLOBAL,
                     FRAME, ARGUMENT, SHIFT, APPLY, RETURN, ASSIGN_FREE, DEFINE_GLOBAL)

INITIAL_STACK = 1024


def get_location(pc, code):
    return code.describe(pc)


jitdriver = JitDriver(greens=["pc", "code"], reds=["f", "s", "a", "c", "vm"],
                      get_printable_location=get_location)


class VM(object):
    def __init__(self, code):
        self.code = code
        n = len(code.initial_globals)
        self.globals_w = [None] * n
        for i in range(n):
            self.globals_w[i] = code.initial_globals[i]
        self.stack = [None] * INITIAL_STACK

    @dont_look_inside
    def grow(self):
        self.stack.extend([None] * len(self.stack))

    def push(self, s, w):
        if s >= len(self.stack):
            self.grow()
        self.stack[s] = w
        return s + 1

    @unroll_safe
    def find_link(self, n, f):
        while n > 0:
            fn = self.stack[f - 1]
            assert isinstance(fn, W_Functional)
            f = fn.link
            n -= 1
        return f

    @dont_look_inside
    def save_stack(self, s):
        saved = [None] * s
        for i in range(s):
            saved[i] = self.stack[i]
        return saved

    @dont_look_inside
    def restore_stack(self, saved):
        for i in range(len(saved)):
            self.stack[i] = saved[i]
        return len(saved)

    def run(self):
        code = self.code
        pc = 0
        a = W_UNSPECIFIED
        f = 0
        c = None
        s = 0
        while True:
            jitdriver.jit_merge_point(pc=pc, code=code, a=a, f=f, c=c, s=s, vm=self)
            ops = code.ops
            op = ops[pc]
            if op == CONSTANT:
                a = code.consts[ops[pc + 1]]
                pc += 2
            elif op == REFER:
                a = self.stack[self.find_link(ops[pc + 1], f) + ops[pc + 2]]
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
                    free[i] = self.stack[s - n + i]
                a = W_Closure(pc + 4, ops[pc + 2], free)
                s -= n
                pc = ops[pc + 3]
            elif op == BOX:
                i = f + ops[pc + 1]
                self.stack[i] = W_Box(self.stack[i])
                pc += 2
            elif op == TEST:
                if a is W_FALSE:
                    pc = ops[pc + 1]
                else:
                    pc += 2
            elif op == JUMP:
                pc = ops[pc + 1]
            elif op == ASSIGN:
                box = self.stack[self.find_link(ops[pc + 1], f) + ops[pc + 2]]
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
                s = self.push(s, W_Frame(ops[pc + 1], f, c))
                pc += 2
            elif op == ARGUMENT:
                s = self.push(s, a)
                pc += 1
            elif op == SHIFT:
                n = ops[pc + 1]
                k = ops[pc + 2]
                for i in range(n):
                    self.stack[s - k - n + i] = self.stack[s - n + i]
                s -= k
                pc += 3
            elif op == APPLY:
                n = ops[pc + 1]
                proc = self.stack[s - n - 1]
                while isinstance(proc, W_Primitive) and proc.pid == P_CWCC:
                    # (call/cc p) を (p k) への末尾呼出しに置き換える
                    if n != 1:
                        raise SchemeError()
                    p = self.stack[s - 1]
                    if not isinstance(p, W_Procedure):
                        raise SchemeError()
                    k = W_Continuation(self.save_stack(s - 2))
                    self.stack[s - 2] = p
                    self.stack[s - 1] = k
                    proc = p
                if isinstance(proc, W_Closure):
                    if proc.nparams != n:
                        raise SchemeError()
                    f = s - n
                    c = proc
                    newpc = proc.body
                elif isinstance(proc, W_Functional):
                    if proc.nparams != n:
                        raise SchemeError()
                    f = s - n
                    newpc = proc.body
                else:
                    if isinstance(proc, W_Primitive):
                        if proc.arity != n:
                            raise SchemeError()
                        a = call_primitive(proc.pid, self.stack, s - n)
                        s -= n + 1
                    elif isinstance(proc, W_Continuation):
                        if n != 1:
                            raise SchemeError()
                        a = self.stack[s - 1]
                        s = self.restore_stack(proc.saved)
                    else:
                        raise SchemeError()
                    frame = self.stack[s - 1]
                    assert isinstance(frame, W_Frame)
                    s -= 1
                    newpc = frame.ret
                    f = frame.fp
                    c = frame.closure
                back = newpc < pc
                pc = newpc
                if back:
                    jitdriver.can_enter_jit(pc=pc, code=code, a=a, f=f, c=c, s=s, vm=self)
            elif op == RETURN:
                s -= ops[pc + 1]
                frame = self.stack[s - 1]
                assert isinstance(frame, W_Frame)
                s -= 1
                newpc = frame.ret
                f = frame.fp
                c = frame.closure
                back = newpc < pc
                pc = newpc
                if back:
                    jitdriver.can_enter_jit(pc=pc, code=code, a=a, f=f, c=c, s=s, vm=self)
            elif op == HALT:
                return a
            else:
                assert False


def run_code(code):
    return VM(code).run()
