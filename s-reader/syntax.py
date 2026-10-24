# -*- coding: utf-8 -*-
# データを抽象構文木に変換
# 構文木はインタプリタの実装モデルに依存しない形にしてあり、
# 各インタプリタはこれを自分の Exp に変換して使う。
from reader import ParseError, SInt, SBool, SSym, SList, SQuote, read_all

KEYWORDS = {}
for _k in ["quote", "lambda", "if", "set!", "begin", "cond", "and", "or",
           "case", "let", "let*", "letrec", "do", "delay", "quasiquote",
           "else", "=>", "define", "unquote", "unquote-splicing",
           "define-syntax", "let-syntax", "letrec-syntax", "syntax-rules"]:
    KEYWORDS[_k] = True

#初期環境の標準手続き 22 個
PRIMITIVES = ["+", "-", "*", "quotient", "remainder", "modulo",
              "=", "<", ">", "<=", ">=",
              "zero?", "not", "eq?",
              "cons", "car", "cdr", "null?", "pair?",
              "display", "newline",
              "call-with-current-continuation"]


# ---- 抽象構文木 ----

class Exp(object):
    def to_string(self):
        return "exp"


class IntExp(Exp):
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return "%d" % (self.value,)


class BoolExp(Exp):
    def __init__(self, value):
        self.value = value

    def to_string(self):
        if self.value:
            return "#t"
        return "#f"


class NilExp(Exp):
    def to_string(self):
        return "'()"


class VarExp(Exp):
    def __init__(self, name):
        self.name = name

    def to_string(self):
        return self.name


class LambdaExp(Exp):
    def __init__(self, params, body):
        self.params = params
        self.body = body

    def to_string(self):
        return "(lambda (%s) %s)" % (" ".join(self.params), self.body.to_string())#joinじゃないと2引数に対応できない、2引数の間は空白


class IfExp(Exp):
    def __init__(self, test, conseq, alt):
        self.test = test
        self.conseq = conseq
        self.alt = alt

    def to_string(self):
        return "(if %s %s %s)" % (self.test.to_string(), self.conseq.to_string(),
                                  self.alt.to_string())


class SetExp(Exp):
    def __init__(self, name, exp):
        self.name = name
        self.exp = exp

    def to_string(self):
        return "(set! %s %s)" % (self.name, self.exp.to_string())


class LetrecExp(Exp):
    def __init__(self, names, lambdas, body):
        self.names = names
        self.lambdas = lambdas
        self.body = body

    def to_string(self):
        binds = []
        for i in range(len(self.names)):
            binds.append("(%s %s)" % (self.names[i], self.lambdas[i].to_string()))
        return "(letrec (%s) %s)" % (" ".join(binds), self.body.to_string())


class AppExp(Exp):
    def __init__(self, rator, rands):
        self.rator = rator
        self.rands = rands

    def to_string(self):
        parts = [self.rator.to_string()]
        for rand in self.rands:
            parts.append(rand.to_string())
        return "(" + " ".join(parts) + ")"


class Define(object):#defineは式じゃないのでexpを継承しない
    def __init__(self, name, exp):
        self.name = name
        self.exp = exp

    def to_string(self):
        return "(define %s %s)" % (self.name, self.exp.to_string())


class Program(object):
    def __init__(self, defines, body):#プログラムは式，定義，および構文定義の列
        self.defines = defines
        self.body = body

    def to_string(self):
        lines = [d.to_string() for d in self.defines]
        lines.append(self.body.to_string())
        return "\n".join(lines)


# ---- スコープ (制約 4, 5: 未束縛変数の検出) ----

class Scope(object):
    # assignable: このスコープの変数に set! できるか (初期環境だけ False)
    def __init__(self, names, parent, assignable=True):
        self.names = {}
        for name in names:
            self.names[name] = True
        self.parent = parent
        self.assignable = assignable

    def find(self, name):
        scope = self
        while scope is not None:
            if name in scope.names:
                return scope
            scope = scope.parent
        return None

    def is_bound(self, name):
        return self.find(name) is not None

    def is_assignable(self, name):
        scope = self.find(name)
        return scope is not None and scope.assignable


# ---- データ -> 構文木 ----

def head_symbol(datum):
    # (kw ...) の kw。先頭が識別子でなければ空文字列
    if isinstance(datum, SList) and len(datum.items) > 0:
        head = datum.items[0]
        if isinstance(head, SSym):
            return head.name
    return ""


def parse_variable(datum):
    if not isinstance(datum, SSym):
        raise ParseError("variable expected: %s" % (datum.to_string(),))
    if datum.name in KEYWORDS:
        raise ParseError("keyword used as variable: %s" % (datum.name,))
    return datum.name


def parse_distinct_variables(data, what):
    # 制約 1, 2: 同じ変数が 2 回以上現れない
    names = []
    seen = {}
    for datum in data:
        name = parse_variable(datum)
        if name in seen:
            raise ParseError("duplicate %s: %s" % (what, name))
        seen[name] = True
        names.append(name)
    return names


def parse_exp(datum, scope):
    if isinstance(datum, SInt):
        return IntExp(datum.value)
    if isinstance(datum, SBool):
        return BoolExp(datum.value)
    if isinstance(datum, SQuote):
        quoted = datum.datum
        if isinstance(quoted, SList) and len(quoted.items) == 0:
            return NilExp()
        raise ParseError("only '() can be quoted: %s" % (datum.to_string(),))
    if isinstance(datum, SSym):
        name = parse_variable(datum)
        if not scope.is_bound(name):
            raise ParseError("unbound variable: %s" % (name,))
        return VarExp(name)
    if isinstance(datum, SList):
        if len(datum.items) == 0:
            raise ParseError("empty combination: ()")
        kw = head_symbol(datum)
        if kw == "lambda":
            return parse_lambda(datum, scope)
        if kw == "if":
            return parse_if(datum, scope)
        if kw == "set!":
            return parse_set(datum, scope)
        if kw == "letrec":
            return parse_letrec(datum, scope)
        if kw in KEYWORDS:
            raise ParseError("unsupported syntax: %s" % (datum.to_string(),))
        return parse_app(datum, scope)
    raise ParseError("bad expression: %s" % (datum.to_string(),))


def parse_lambda(datum, scope):
    # (lambda (<変数>*) <式>)
    items = datum.items
    if len(items) != 3 or not isinstance(items[1], SList):
        raise ParseError("bad lambda: %s" % (datum.to_string(),))
    formals = items[1]
    assert isinstance(formals, SList)
    params = parse_distinct_variables(formals.items, "parameter")
    body = parse_exp(items[2], Scope(params, scope))
    return LambdaExp(params, body)


def parse_if(datum, scope):
    # (if <式> <式> <式>)  代替部は必須
    items = datum.items
    if len(items) != 4:
        raise ParseError("bad if: %s" % (datum.to_string(),))
    return IfExp(parse_exp(items[1], scope), parse_exp(items[2], scope),
                 parse_exp(items[3], scope))


def parse_set(datum, scope):
    # (set! <変数> <式>)  初期環境だけで束縛された名前には代入できない (制約 5)
    items = datum.items
    if len(items) != 3:
        raise ParseError("bad set!: %s" % (datum.to_string(),))
    name = parse_variable(items[1])
    if not scope.is_assignable(name):
        raise ParseError("cannot assign: %s" % (name,))
    return SetExp(name, parse_exp(items[2], scope))


def parse_letrec(datum, scope):
    # (letrec ((<変数> <lambda式>)*) <式>)
    items = datum.items
    if len(items) != 3 or not isinstance(items[1], SList):
        raise ParseError("bad letrec: %s" % (datum.to_string(),))
    bindings = items[1]
    assert isinstance(bindings, SList)
    name_data = []
    init_data = []
    for binding in bindings.items:
        if not (isinstance(binding, SList) and len(binding.items) == 2):
            raise ParseError("bad letrec binding: %s" % (binding.to_string(),))
        assert isinstance(binding, SList)
        name_data.append(binding.items[0])
        init_data.append(binding.items[1])
    names = parse_distinct_variables(name_data, "letrec variable")
    inner = Scope(names, scope)
    lambdas = []
    for init in init_data:
        if head_symbol(init) != "lambda":
            raise ParseError("letrec init must be a lambda: %s" % (init.to_string(),))
        assert isinstance(init, SList)
        lambdas.append(parse_lambda(init, inner))
    return LetrecExp(names, lambdas, parse_exp(items[2], inner))


def parse_app(datum, scope):
    # (<式> <式>*)
    items = datum.items
    rator = parse_exp(items[0], scope)
    rands = []
    for i in range(1, len(items)):
        rands.append(parse_exp(items[i], scope))
    return AppExp(rator, rands)


# ---- プログラム ----

def parse_program_data(data):
    #datumを構文木に変換する
    # <プログラム> ::= <定義>* <式>
    if len(data) == 0:
        raise ParseError("program has no expression")
    def_data = []
    names = []
    seen = {}
    for i in range(len(data) - 1):
        datum = data[i]
        # 先頭がdefineでない場合
        if head_symbol(datum) != "define":
            raise ParseError("only definitions may precede the last expression: %s"
                             % (datum.to_string(),))
        assert isinstance(datum, SList)
        #defineは3要素であること
        if len(datum.items) != 3:
            raise ParseError("bad define: %s" % (datum.to_string(),))
        #他の定義と重複していないか確認
        name = parse_variable(datum.items[1])
        if name in seen:
            raise ParseError("duplicate definition: %s" % (name,))
        seen[name] = True
        names.append(name)
        def_data.append(datum.items[2])
    last = data[len(data) - 1]
    if head_symbol(last) == "define":
        raise ParseError("program must end with an expression")
    # 定義の束縛はプログラム全体から見え、標準手続きの名前を覆い隠してよい 
    #スコープの構築
    scope = Scope(names, Scope(PRIMITIVES, None, False))
    defines = []
    for i in range(len(names)):
        defines.append(Define(names[i], parse_exp(def_data[i], scope)))
    return Program(defines, parse_exp(last, scope))


def parse_program(text):
    return parse_program_data(read_all(text))
