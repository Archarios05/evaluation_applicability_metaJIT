# -*- coding: utf-8 -*-
# 自作言語用のS式リーダ
# テキスト -> トークン列 -> データ (Datum) の列 に変換する。
#構文的に正しい S 式全体がデータ
import sys

try:
    MAXINT = sys.maxint
except AttributeError:
    MAXINT = sys.maxsize


class ParseError(Exception):
    def __init__(self, msg):
        self.msg = msg


# ---- データ ----
class Datum(object):
    def to_string(self):
        return "datum"


class SInt(Datum):
    def __init__(self, value):
        self.value = value

    def to_string(self):
        return "%d" % (self.value,)


class SBool(Datum):
    def __init__(self, value):
        self.value = value

    def to_string(self):
        if self.value:
            return "#t"
        return "#f"


class SSym(Datum):
    def __init__(self, name):
        self.name = name

    def to_string(self):
        return self.name


class SList(Datum):
    def __init__(self, items):
        self.items = items

    def to_string(self):
        parts = [item.to_string() for item in self.items]
        return "(" + " ".join(parts) + ")"


class SQuote(Datum):
    # 'x を (quote x) と区別するため専用のノードにする 
    def __init__(self, datum):
        self.datum = datum

    def to_string(self):
        return "'" + self.datum.to_string()


# ---- 字句解析 ----

TOK_LPAREN = 0
TOK_RPAREN = 1
TOK_QUOTE = 2
TOK_INT = 3
TOK_BOOL = 4
TOK_IDENT = 5


class Token(object):
    def __init__(self, kind, text, line):
        self.kind = kind
        self.text = text
        self.line = line


def is_digit(c):
    return c >= "0" and c <= "9"


def is_letter(c):
    return (c >= "a" and c <= "z") or (c >= "A" and c <= "Z")


def is_whitespace(c):
    return c == " " or c == "\n" or c == "\t" or c == "\r" #空白、タブ、改行


def is_delimiter(c):
    return is_whitespace(c) or c == "(" or c == ")" or c == ";"


def is_initial(c):
    return is_letter(c) or c in "!$%&*/:<=>?^_~"


def is_subsequent(c):
    return is_initial(c) or is_digit(c) or c in "+-.@"


class Lexer(object):
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1

    def at_delimiter(self):
        return self.pos >= len(self.text) or is_delimiter(self.text[self.pos])

    def skip_atmosphere(self):
        text = self.text
        while self.pos < len(text):
            c = text[self.pos]
            if is_whitespace(c):
                if c == "\n":
                    self.line += 1
                self.pos += 1
            elif c == ";":
                while self.pos < len(text) and text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def error(self, msg):
        raise ParseError("%s (line %d)" % (msg, self.line))

    def next_token(self):
        # 終端なら None
        self.skip_atmosphere()
        text = self.text
        start = self.pos
        if start >= len(text):
            return None
        c = text[start]
        if c == "(":
            self.pos += 1
            return Token(TOK_LPAREN, "(", self.line)
        if c == ")":
            self.pos += 1
            return Token(TOK_RPAREN, ")", self.line)
        if c == "'":
            self.pos += 1
            return Token(TOK_QUOTE, "'", self.line)
        if c == "#":
            return self.read_boolean()
        if is_digit(c):
            return self.read_integer()
        if c == "+" or c == "-":
            if start + 1 < len(text) and is_digit(text[start + 1]):
                return self.read_integer()
            self.pos += 1
            return self.finish_ident(start)
        if c == ".":
            if start + 2 < len(text) and text[start + 1] == "." and text[start + 2] == ".":
                self.pos += 3
                return self.finish_ident(start)
            self.error("unexpected '.'")
        if is_initial(c):
            self.pos += 1
            while self.pos < len(text) and is_subsequent(text[self.pos]):
                self.pos += 1
            return self.finish_ident(start)
        self.error("unexpected character")
        return None

    def finish_ident(self, start):
        if not self.at_delimiter():
            self.error("bad identifier")
        return Token(TOK_IDENT, self.text[start:self.pos].lower(), self.line)

    def read_boolean(self):
        start = self.pos
        if start + 1 < len(self.text):
            c = self.text[start + 1]
            self.pos += 2
            if (c == "t" or c == "T") and self.at_delimiter():
                return Token(TOK_BOOL, "#t", self.line)
            if (c == "f" or c == "F") and self.at_delimiter():
                return Token(TOK_BOOL, "#f", self.line)
        self.error("bad '#' syntax")
        return None

    def read_integer(self):
        start = self.pos
        text = self.text
        if text[self.pos] == "+" or text[self.pos] == "-":
            self.pos += 1
        while self.pos < len(text) and is_digit(text[self.pos]):
            self.pos += 1
        if not self.at_delimiter():
            self.error("bad number")
        return Token(TOK_INT, text[start:self.pos], self.line)


def tokenize(text):
    lexer = Lexer(text)
    tokens = []
    while True:
        tok = lexer.next_token()
        if tok is None:
            break
        tokens.append(tok)
    return tokens


def parse_integer(s):
   
    i = 0
    neg = False
    if s[0] == "+" or s[0] == "-":
        neg = s[0] == "-"
        i = 1
    result = 0
    while i < len(s):
        d = ord(s[i]) - ord("0")
        if result > (MAXINT - d) // 10:
            raise ParseError("integer literal out of range: %s" % (s,)) # 固定長整数に収まらないリテラルは実装制限の違反
        result = result * 10 + d
        i += 1
    if neg:
        return -result
    return result


# ---- リーダー ----

class Reader(object):
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

    def at_end(self):
        return self.index >= len(self.tokens)

    def read(self):
        if self.at_end():
            raise ParseError("unexpected end of input")
        tok = self.tokens[self.index]
        self.index += 1
        if tok.kind == TOK_LPAREN:
            items = []
            while True:
                if self.at_end():
                    raise ParseError("unclosed '(' (line %d)" % (tok.line,))
                if self.tokens[self.index].kind == TOK_RPAREN:
                    self.index += 1
                    return SList(items)
                items.append(self.read())
        if tok.kind == TOK_RPAREN:
            raise ParseError("unexpected ')' (line %d)" % (tok.line,))
        if tok.kind == TOK_QUOTE:
            return SQuote(self.read())
        if tok.kind == TOK_INT:
            return SInt(parse_integer(tok.text))
        if tok.kind == TOK_BOOL:
            return SBool(tok.text == "#t")
        return SSym(tok.text)


def read_all(text):#本体
    reader = Reader(tokenize(text))
    data = []
    while not reader.at_end():
        data.append(reader.read())
    return data
