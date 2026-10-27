# -*- coding: utf-8 -*-
# convert 後の構文木を木の形で表示する (CPython専用、RPython翻訳対象外)。
#   python show_ast.py examples/fib.scm
#
# @xxxx は id() の下位16ビット。同じノードかどうかの目印 (実行ごとに変わる)
import sys
import exp as E
from convert import convert_program
from syntax import parse_program


def label(node):
    s = node.to_string()
    if isinstance(node, E.LocalVarExp):
        s += "  [depth=%d index=%d]" % (node.depth, node.index)
    elif isinstance(node, E.ConstExp) and not s.startswith("prim"):
        s = "const(%s)" % (node.val.to_string(),)
    return "%s  @%04x" % (s, id(node) & 0xffff)


def children(node):
    if isinstance(node, E.LambdaExp):
        return [("body", node.body)]
    if isinstance(node, E.IfExp):
        return [("test", node.test), ("conseq", node.conseq), ("alt", node.alt)]
    if isinstance(node, E.AppExp):
        return [("rator", node.rator)] + [("rand%d" % i, r) for i, r in enumerate(node.rands)]
    if isinstance(node, (E.SetLocalExp, E.SetGlobalExp)):
        return [("exp", node.exp)]
    if isinstance(node, E.LetrecExp):
        return [("lambda%d" % i, l) for i, l in enumerate(node.lambdas)] + [("body", node.body)]
    if isinstance(node, E.DefineExp):
        kids = [("exp", node.exp)]
        if node.rest is not None:
            kids.append(("rest", node.rest))
        return kids
    return []


def show(node, prefix="", role=None, last=True, top=True):
    head = "" if top else prefix + ("└─ " if last else "├─ ")
    print(head + ("%s: " % role if role else "") + label(node))
    kids = children(node)
    sub = prefix if top else prefix + ("   " if last else "│  ")
    for i, (r, k) in enumerate(kids):
        show(k, sub, r, i == len(kids) - 1, False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    with open(sys.argv[1], encoding="utf-8") as f:
        show(convert_program(parse_program(f.read())))
