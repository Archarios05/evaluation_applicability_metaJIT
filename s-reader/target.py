# -*- coding: utf-8 -*-
# パーサ単体の RPython 翻訳確認用。ファイルを構文解析して構文木を表示する。
#   ./parser-c prog.scm
# 構文エラーなら "error" だけを出力する。
import os
from reader import ParseError
from syntax import parse_program


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
    if len(argv) != 2:
        os.write(2, "usage: %s FILE\n" % (argv[0],))
        return 2
    text = read_file(argv[1])
    try:
        program = parse_program(text)
    except ParseError as e:
        os.write(2, e.msg + "\n")
        os.write(1, "error\n")
        return 1
    os.write(1, program.to_string() + "\n")
    return 0


def target(*args):
    return entry_point, None


if __name__ == "__main__":
    import sys
    entry_point(sys.argv)
