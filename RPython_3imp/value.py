# -*- coding: utf-8 -*-
# VM が扱う値。W_Box と W_Frame はスタック上にだけ現れる内部オブジェクト
from RPython_3imp.rpy import dont_look_inside


class SchemeError(Exception):
    pass


class W_Object(object):
    def to_string(self):
        return "#<object>"


class W_Int(W_Object):
    _immutable_fields_ = ["value"]

    def __init__(self, value):
        self.value = value

    def to_string(self):
        return "%d" % (self.value,)


class W_Bool(W_Object):
    _immutable_fields_ = ["value"]

    def __init__(self, value):
        self.value = value

    def to_string(self):
        if self.value:
            return "#t"
        return "#f"


W_TRUE = W_Bool(True)
W_FALSE = W_Bool(False)


def wrap_bool(b):
    if b:
        return W_TRUE
    return W_FALSE


class W_Nil(W_Object):
    def to_string(self):
        return "()"


W_NIL = W_Nil()


class W_Unspecified(W_Object):
    def to_string(self):
        return "#<unspecified>"


W_UNSPECIFIED = W_Unspecified()


class W_Undefined(W_Object):
    # define の変数に値が格納される前の状態、および letrec の box の初期値
    def to_string(self):
        return "#<undefined>"


W_UNDEFINED = W_Undefined()


class W_Pair(W_Object):
    _immutable_fields_ = ["car", "cdr"]

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr


class W_Procedure(W_Object):
    def to_string(self):
        return "#<procedure>"


class W_Closure(W_Procedure):
    # clambda の値。自由変数の値 (または box) をコピーして持つ
    _immutable_fields_ = ["body", "nparams", "free[*]"]

    def __init__(self, body, nparams, free):
        self.body = body
        self.nparams = nparams
        self.free = free


class W_Functional(W_Procedure):
    # slambda の値。外側の変数は静的リンク link (スタック上のフレーム) からたどる
    _immutable_fields_ = ["body", "nparams", "link"]

    def __init__(self, body, nparams, link):
        self.body = body
        self.nparams = nparams
        self.link = link


class W_Primitive(W_Procedure):
    _immutable_fields_ = ["pid", "arity", "name"]

    def __init__(self, pid, name, arity):
        self.pid = pid
        self.name = name
        self.arity = arity


class W_Continuation(W_Procedure):
    # call/cc 時点のスタックのコピー
    _immutable_fields_ = ["saved"]

    def __init__(self, saved):
        self.saved = saved


class W_Box(W_Object):
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return "#<box>"


class W_Frame(W_Object):
    # frame 命令が積む (戻り先 x, ダイナミックリンク f, クロージャ c)
    _immutable_fields_ = ["ret", "fp", "closure"]

    def __init__(self, ret, fp, closure):
        self.ret = ret
        self.fp = fp
        self.closure = closure

    def to_string(self):
        return "#<frame>"


@dont_look_inside
def show(w):
    if isinstance(w, W_Pair):
        parts = ["(", show(w.car)]
        rest = w.cdr
        while isinstance(rest, W_Pair):
            parts.append(" ")
            parts.append(show(rest.car))
            rest = rest.cdr
        if rest is not W_NIL:
            parts.append(" . ")
            parts.append(show(rest))
        parts.append(")")
        return "".join(parts)
    return w.to_string()
