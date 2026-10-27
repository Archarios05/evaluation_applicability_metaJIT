# -*- coding: utf-8 -*-
# RPython 翻訳用のエントリポイント
#   ./3imp-c prog.scm         実行
#   ./3imp-c --dis prog.scm   コンパイル結果 (平坦なコード) を表示
import os
import RPython_3imp_vable.primitives as primitives
from RPython_3imp_vable.codegen import compile_program
from reader import ParseError
from syntax import parse_program
from RPython_3imp_vable.value import SchemeError
from RPython_3imp_vable.vm import VM
from RPython_3imp_vable.opcodes import disassemble
from RPython_3imp_vable.rpy import StackOverflow


def read_file(path):
    fd = os.open(path, os.O_RDONLY, 0o777)
    chunks = []
    while True:
        chunk = os.read(fd, 4096)
        if len(chunk) == 0:
            break
        chunks.append(chunk)
    os.close(fd)
    return "".join(chunks)


def entry_point(argv):
    dis = False
    path = ""
    for i in range(1, len(argv)):
        if argv[i] == "--dis":
            dis = True
        else:
            path = argv[i]
    if path == "":
        os.write(2, "usage: %s [--dis] FILE\n" % (argv[0],))
        return 2
    try:
        program = parse_program(read_file(path))
    except ParseError:
        primitives.write_out("error\n")
        return 1
    code = compile_program(program)
    if dis:
        primitives.write_out(disassemble(code))
        return 0
    try:
        VM(code).run()
    except SchemeError:
        primitives.write_out("error\n")
        return 1
    except StackOverflow:
        # 末尾でない呼出しはホストの再帰なので、深すぎると C スタックが尽きる
        primitives.write_out("error\n")
        return 1
    return 0


def target(*args):
    return entry_point, None


def jitpolicy(driver):
    from rpython.jit.codewriter.policy import JitPolicy
    return JitPolicy()


if __name__ == "__main__":
    import sys
    if sys.version_info[0] >= 3:
        primitives.write_out = lambda s: sys.stdout.write(s)

        def read_file(path):
            with open(path, encoding="utf-8") as fp:
                return fp.read()
    sys.exit(entry_point(sys.argv))
