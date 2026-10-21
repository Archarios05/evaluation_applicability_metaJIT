# -*- coding: utf-8 -*-
# 命令セット。3imp の命令に jump (if の合流)、shift (末尾呼出し, 論文 4.6節)、define-global を足した
# 各命令は ops 上で「命令番号 オペランド…」と並ぶ
HALT = 0
CONSTANT = 1        # k          a = consts[k]
REFER = 2           # n m        a = 静的リンクを n 回たどったフレームの m 番目
REFER_FREE = 3      # i          a = c の自由変数 i
REFER_GLOBAL = 4    # i          a = 大域変数 i (未定義ならエラー)
INDIRECT = 5        #            a = unbox(a)
FUNCTIONAL = 6      # n end      a = functional(本体 = 次の命令, link = f)。end へ飛ぶ
CLOSE = 7           # m n end    a = closure(本体 = 次の命令, 自由変数 = スタック上の m 個)。end へ飛ぶ
BOX = 8             # m          局所変数 m を box に入れる
TEST = 9            # else       a が #f なら else へ
JUMP = 10           # to
ASSIGN = 11         # n m        局所変数 (n, m) の box に a を入れ、a = 未規定値
ASSIGN_GLOBAL = 12  # i          大域変数 i に a を入れ、a = 未規定値 (未定義ならエラー)
FRAME = 13          # ret        (ret, f, c) を積む
ARGUMENT = 14       #            a を積む
SHIFT = 15          # n k        上の n 個を k 個下にずらす
APPLY = 16          # n          スタック上の手続きを n 引数で呼ぶ
RETURN = 17         # k          k 個捨ててフレームから x, f, c を戻す
ASSIGN_FREE = 18    # i          c の自由変数 i の box に a を入れ、a = 未規定値
DEFINE_GLOBAL = 19  # i          大域変数 i に a を入れる (define)

NAMES = ["halt", "constant", "refer", "refer-free", "refer-global", "indirect",
         "functional", "close", "box", "test", "jump", "assign", "assign-global",
         "frame", "argument", "shift", "apply", "return", "assign-free", "define-global"]

ARGC = [0, 1, 2, 1, 1, 0, 2, 3, 1, 1, 1, 2, 1, 1, 0, 2, 1, 1, 1, 1]


def describe(code, pc):
    op = code.ops[pc]
    parts = ["%d: %s" % (pc, NAMES[op])]
    for i in range(ARGC[op]):
        parts.append("%d" % (code.ops[pc + 1 + i],))
    if op == CONSTANT:
        parts.append("; " + code.consts[code.ops[pc + 1]].to_string())
    elif op == REFER_GLOBAL or op == ASSIGN_GLOBAL or op == DEFINE_GLOBAL:
        parts.append("; " + code.global_names[code.ops[pc + 1]])
    return " ".join(parts)


def disassemble(code):
    lines = []
    pc = 0
    while pc < len(code.ops):
        lines.append(describe(code, pc))
        pc += 1 + ARGC[code.ops[pc]]
    return "\n".join(lines) + "\n"
