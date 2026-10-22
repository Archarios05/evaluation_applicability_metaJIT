# -*- coding: utf-8 -*-
# RPython 翻訳用のエントリポイント
#   ./target-c prog.scm
# エラーはどれも "error" の 1 行だけを出力する 
import primitives
from convert import convert_program
from reader import ParseError
from syntax import parse_program
from value import SchemeError
from interpreter import value_of_program
from rpy import StackOverflow


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


def run_text(text):
    try:
        program = parse_program(text)
    except ParseError:
        primitives.write_out("error\n")
        return 1
    try:
        value_of_program(convert_program(program))
    except SchemeError:
        primitives.write_out("error\n")
        return 1
    except StackOverflow:
        primitives.write_out("error\n")
        return 1
    return 0


def entry_point(argv):
    if len(argv) != 2:
        os.write(2, "usage: %s FILE\n" % (argv[0],))
        return 2
    return run_text(read_file(argv[1]))


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
