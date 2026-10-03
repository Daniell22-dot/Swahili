"""Kisakifu — the Kiswahili parser.

A hand-written recursive-descent statement parser plus a Pratt expression
parser. No third-party dependencies, so the grammar is readable in one sitting
and easy to extend (that matters when the language is still new).

Precedence, loosest to tightest:

    au  →  na  →  sio (unary not)  →  == != < <= > >= iko ni  →  + -
         →  * / // %  →  **  →  - + (unary)  →  kitu.ch, kitu[x], kitu(x)
"""

from __future__ import annotations

from . import ast
from .errors import Kosa
from .lexer import OP_PRECEDENCE, TYPE_TOKENS, Token, tokenize

ASSIGN_OPS = {
    "ASSIGN": "=", "ADD_ASSIGN": "+=", "SUB_ASSIGN": "-=", "MUL_ASSIGN": "*=",
    "DIV_ASSIGN": "/=", "IDIV_ASSIGN": "//=", "MOD_ASSIGN": "%=",
    "POW_ASSIGN": "**=",
}

TYPE_NAMES = {
    "INT_TYPE": "namba", "FLOAT_TYPE": "desimali", "STRING_TYPE": "maneno",
    "LIST_TYPE": "orodha", "DICT_TYPE": "kamusi", "BOOL_TYPE": "hali",
}

# words that are keywords but still usable as ordinary names
KEYWORD_AS_NAME = {
    "SELF": "mwenyewe",
    "NOT": "sio", "AND": "na", "OR": "au", "IS": "ni", "INOP": "iko",
    "IF": "kama", "ELSE": "vingo", "WHILE": "wakati", "IN": "kwenye",
    "BREAK": "vunja", "CONTINUE": "endelea", "RETURN": "rudia", "PASS": "nenda",
    "DEF": "kazi", "CLASS": "darasa", "EACH": "kila", "FOR": "kwa",
    "THROW": "tupa", "TRY": "jaribu", "EXCEPT": "kosa", "FINALLY": "mwisho",
    "IMPORT": "tumia", "NEW": "tengeneza", "DEBUGGER": "kati", "UNTIL": "hadi",
}

# tokens that may begin an expression — used to find where a space-separated
# argument list ends:  `andika "a", 1, x + 2`
CAN_START_EXPRESSION = {
    "INT", "FLOAT", "STRING", "FSTRING", "TRUE", "FALSE", "NULL", "IDENT",
    "LPAREN", "LBRACKET", "LBRACE", "MINUS", "PLUS", "NOT", "SELF", "DEF",
    "NEW", "TERNARY", "THROW",
} | TYPE_TOKENS

# tokens that close an argument list
ARGUMENT_STOPS = {"NEWLINE", "SEMI", "RBRACE", "RPAREN", "RBRACKET", "EOF"}

# `x[0] = 1` must not be mistaken for a call named `x`, so a bracket right
# after the identifier never starts an implicit argument list.
IMPLICIT_CALL_STARTERS = CAN_START_EXPRESSION - {"LBRACKET"}

# operators that build a Compare node rather than an arithmetic Binary node
COMPARE_OPS = {"EQ", "NEQ", "LT", "LTE", "GT", "GTE"}


class Parser:
    def __init__(self, source: str, filename: str = "<kisarifi>"):
        self.source = source
        self.filename = filename
        self.tokens = tokenize(source, filename)
        self.current = 0

    # --- plumbing ----------------------------------------------------------

    @property
    def tok(self) -> Token:
        return self.tokens[self.current]

    def _error(self, token: Token, swahili: str, english: str, hint: str = "") -> Kosa:
        return Kosa("Kisakifu / Parser", swahili, english, self.source,
                    token.index, hint)

    def advance(self) -> Token:
        token = self.tokens[self.current]
        if token.type != "EOF":
            self.current += 1
        return token

    def check(self, *types: str) -> bool:
        return self.tok.type in types

    def match(self, *types: str) -> Token | None:
        if self.tok.type in types:
            return self.advance()
        return None

    def expect(self, type_: str, what: str) -> Token:
        if self.tok.type == type_:
            return self.advance()
        raise self._error(
            self.tok,
            f"Hitajiwa '{what}'",
            f"Expected {what}",
            self._hint_for(self.tok),
        )

    def _hint_for(self, token: Token) -> str:
        if token.type == "EOF":
            return "Fomili ilikomea ghafla. Huu ndio ukweli?"
        word = token.value if isinstance(token.value, str) else token.type
        return f"Nilikuwa naona '{word}' hapa."

    def _at_end(self) -> bool:
        return self.check("EOF")

    # --- entry point -------------------------------------------------------

    def parse(self) -> ast.Program:
        body: list[ast.Node] = []
        while not self._at_end():
            if self.match("SEMI", "NEWLINE"):
                continue
            body.append(self.statement())
        return ast.Program(body)

    # --- statements --------------------------------------------------------

    def statement(self) -> ast.Node:
        line = self.tok.line
        node = self._statement()
        node.line = line
        return node

    def _statement(self) -> ast.Node:
        kind = self.tok.type

        if kind == "IMPORT":
            return self.import_statement()
        if kind == "CLASS":
            return self.class_statement()
        if kind == "DEF":
            return self.function_statement()
        if kind == "IF":
            return self.if_statement()
        if kind == "WHILE":
            return self.while_statement(until=False)
        if kind == "UNTIL":
            return self.while_statement(until=True)
        if kind in ("EACH", "FOR"):
            return self.for_statement()
        if kind == "RETURN":
            self.advance()
            value = None if self._end_of_statement() else self.expression()
            self._end_statement()
            return ast.Return(value)
        if kind == "BREAK":
            self.advance()
            self._end_statement()
            return ast.Break()
        if kind == "CONTINUE":
            self.advance()
            self._end_statement()
            return ast.Continue()
        if kind == "PASS":
            self.advance()
            self._end_statement()
            return ast.Pass()
        if kind == "DEBUGGER":
            self.advance()
            self._end_statement()
            return ast.Debugger()
        if kind == "TRY":
            return self.try_statement()
        if kind == "THROW":
            self.advance()
            return ast.Throw(self.expression())

        # typed declaration: `namba x = 1` / `maneno jina`
        if kind in TYPE_TOKENS and self.tokens[self.current + 1].type == "IDENT":
            return self.typed_declaration()

        # space-separated call: `andika "habari"`, `ondoa "jina lako ni nini?"`
        if self._starts_implicit_call():
            return ast.ExprStatement(self._implicit_call())

        return self.expression_statement()

    def _starts_implicit_call(self) -> bool:
        if self.tok.type != "IDENT" or self.tokens[self.current + 1].type \
                not in IMPLICIT_CALL_STARTERS:
            return False
        return not self._at_argument_stop()

    def _at_argument_stop(self) -> bool:
        token = self.tok
        if token.type in ARGUMENT_STOPS:
            return True
        following = self.tokens[self.current + 1].type if token.type == "IDENT" \
            else None
        return following in ("ASSIGN", "ADD_ASSIGN", "SUB_ASSIGN", "MUL_ASSIGN",
                             "DIV_ASSIGN", "IDIV_ASSIGN", "MOD_ASSIGN",
                             "POW_ASSIGN")

    def _implicit_call(self) -> ast.Call:
        name = self.advance()          # the verb, e.g. `andika`
        args: list[ast.Node] = []
        while self.tok.type in CAN_START_EXPRESSION and not self._at_argument_stop():
            args.append(self.expression())
            if not self.match("COMMA"):
                break
        return ast.Call(ast.Name(name.value), args)

    def _end_of_statement(self) -> bool:
        return self.check("SEMI", "NEWLINE", "RBRACE", "EOF")

    def _end_statement(self) -> None:
        if self.match("SEMI", "NEWLINE"):
            return
        if self.check("RBRACE", "EOF"):
            return
        raise self._error(self.tok, "Hakuna mstari mpya baada ya sentensi",
                          "Unexpected token after statement")

    def import_statement(self) -> ast.Import:
        self.advance()  # tumia
        name_token = self.expect("IDENT", "jina la kifurushi")
        alias = None
        if self.match("IF"):  # `kama` doubles as "as"
            alias = self.expect("IDENT", "jina la kifurushi").value
        self._end_statement()
        return ast.Import(name_token.value, alias)

    def typed_declaration(self) -> ast.Declaration:
        hint = TYPE_NAMES[self.advance().type]
        name = self.expect("IDENT", "jina la kipeo").value
        value = None
        if self.match("ASSIGN"):
            value = self.expression()
        self._end_statement()
        return ast.Declaration(name, hint, value)

    def expression_statement(self) -> ast.Node:
        expr = self.expression()
        if self.tok.type in ASSIGN_OPS:
            op = ASSIGN_OPS[self.advance().type]
            value = self.expression()
            self._check_assignable(expr)
            self._end_statement()
            return ast.Assign(expr, op, value)
        self._end_statement()
        return ast.ExprStatement(expr)

    def _check_assignable(self, target: ast.Node) -> None:
        if isinstance(target, (ast.Name, ast.Member, ast.Index)):
            return
        raise self._error(
            self.tok,
            "Huwezi kuweka thamani pale hapa",
            "Cannot assign to this expression",
            "Weka kwa jina, orodha[k] au kitu.sifa inavyofaa? "
            "Mfano: `jina = 1`, `orodha[0] = 1`, `kitu.sifa = 1`.",
        )

    def if_statement(self) -> ast.If:
        self.advance()  # kama
        test = self.expression()
        body = self.block()

        orelse = None
        if self.match("ELSE"):  # vingo
            if self.check("IF"):  # `vingo kama` — chain to a fresh `if`
                orelse = self.if_statement()
            else:
                orelse = self.block()
        return ast.If(test, body, orelse)

    def while_statement(self, until: bool) -> ast.While:
        self.advance()
        test = self.expression()
        return ast.While(test, self.block(), until)

    def for_statement(self) -> ast.ForEach:
        self.advance()  # kila / kwa
        name = self.expect("IDENT", "jina la kipeo").value
        self.expect("IN", "'kwenye'")
        iterable = self.expression()
        return ast.ForEach(name, iterable, self.block())

    def try_statement(self) -> ast.Try:
        self.advance()  # jaribu
        body = self.block()
        handler = None
        handler_body = None
        orelse = None
        finally_body = None

        if self.match("EXCEPT"):  # kosa
            name_token = self.match("IDENT")
            handler = name_token.value if name_token else None
            handler_body = self.block()
        if self.match("ELSE"):
            orelse = self.block()
        if self.match("FINALLY"):
            finally_body = self.block()

        if handler_body is None and finally_body is None:
            raise self._error(self.tok,
                              "`jaribu` lazima iwe na `kosa` au `mwisho`",
                              "'jaribu' needs a 'kosa' or 'mwisho' block")
        return ast.Try(body, handler, handler_body, orelse, finally_body)

    def block(self) -> ast.Block:
        if self.match("SEMI", "NEWLINE"):
            return ast.Block([])
        self.expect("LBRACE", "'{' kuanza wazi")
        body: list[ast.Node] = []
        while not self.check("RBRACE") and not self._at_end():
            if self.match("SEMI", "NEWLINE"):
                continue
            body.append(self.statement())
        self.expect("RBRACE", "'}' kufunga wazi")
        return ast.Block(body)

    # --- classes & functions ----------------------------------------------

    def class_statement(self) -> ast.ClassDef:
        self.advance()  # darasa
        name = self.expect("IDENT", "jina la darasa").value
        self.expect("LBRACE", "'{' kuanza wazi")
        fields: list[str] = []
        body: list[ast.Node] = []
        while not self.check("RBRACE") and not self._at_end():
            if self.match("SEMI", "NEWLINE"):
                continue
            if self.check("IDENT") or self.tok.type in TYPE_TOKENS:
                save = self.current
                if self.tok.type in TYPE_TOKENS:
                    self.advance()
                if self.check("IDENT"):
                    fields.append(self.advance().value)
                    self.match("ASSIGN")   # default value is set on the instance
                    self._end_statement()
                    continue
                self.current = save
            body.append(self.statement())
        self.expect("RBRACE", "'}' kufunga darasa")
        return ast.ClassDef(name, fields, ast.Block(body))

    def function_statement(self) -> ast.FuncDef:
        self.advance()  # kazi
        name = self.expect("IDENT", "jina la kazi").value
        params = self.parameter_list()

        ret_hint = None
        is_arrow = False
        if self.match("COLON") and self.tok.type in TYPE_TOKENS:
            ret_hint = TYPE_NAMES[self.advance().type]
        elif self.match("ARROW"):
            is_arrow = True
            if self.tok.type in TYPE_TOKENS:
                ret_hint = TYPE_NAMES[self.advance().type]
            elif self.check("IDENT"):
                ret_hint = self.advance().value

        if self.match("ARROW"):
            is_arrow = True

        if is_arrow:
            expr = self.expression()
            self._end_statement()
            return ast.FuncDef(name, params, ast.Block([ast.Return(expr)]),
                               ret_hint, ret_hint, True)

        return ast.FuncDef(name, params, self.block(), ret_hint)

    def parameter_list(self) -> list[ast.Parameter]:
        self.expect("LPAREN", "'(' kuanza vigezo")
        params: list[ast.Parameter] = []
        if not self.check("RPAREN"):
            while True:
                hint = None
                if self.tok.type in TYPE_TOKENS and \
                        self.tokens[self.current + 1].type == "IDENT":
                    hint = TYPE_NAMES[self.advance().type]
                name = self.expect("IDENT", "jina la kipimo").value
                default = None
                if self.match("ASSIGN"):
                    default = self.expression()
                params.append(ast.Parameter(name, default, hint))
                if not self.match("COMMA"):
                    break
        self.expect("RPAREN", "')' kufunga vigezo")
        return params

    # --- expressions -------------------------------------------------------

    def expression(self) -> ast.Node:
        return self.assignment()

    def assignment(self) -> ast.Node:
        left = self.ternary()
        if self.tok.type in ASSIGN_OPS:
            op = ASSIGN_OPS[self.advance().type]
            self._check_assignable(left)
            return ast.Assign(left, op, self.assignment())
        return left

    def ternary(self) -> ast.Node:
        if self.check("TERNARY"):
            return self.ternary_expression()
        return self.binary(0)

    def ternary_expression(self) -> ast.Ternary:
        self.advance()  # chagua
        self.expect("LPAREN", "'(' baada ya chagua")
        test = self.expression()
        self.expect("RPAREN", "')' baada ya masharti")
        consequent = self.expression_block("vingo")
        self.expect("ELSE", "'vingo' baada ya chagua")
        alternate = self.expression_block("vingo")
        return ast.Ternary(test, consequent, alternate)

    def expression_block(self, closer: str) -> ast.Node:
        """A `{ expr }` used as a value."""
        self.expect("LBRACE", "'{' kuanza thamani")
        if self.check("RBRACE"):
            raise self._error(self.tok, "Hakuna thamani ndani ya kizari",
                              "Empty expression block")
        node = self.expression()
        self.expect("RBRACE", "'}' kufunga thamani")
        return node

    def binary(self, min_prec: int) -> ast.Node:
        left = self.unary()
        while True:
            op_type = self.tok.type
            if op_type in ("AND", "OR"):
                if op_type == "AND":
                    prec = 2
                else:
                    prec = 1
            else:
                prec = self._precedence(op_type)
            if prec is None or prec <= min_prec:
                break
            if op_type in ("AND", "OR"):
                self.advance()
                word = "na" if op_type == "AND" else "au"
                right = self.binary(prec)
                left = ast.Logical(word, left, right)
            elif op_type in ("INOP", "IS"):
                self.advance()
                word = "iko" if op_type == "INOP" else "ni"
                right = self.binary(prec)
                left = ast.Compare(word, left, right)
            elif op_type in COMPARE_OPS:
                word = str(self.tok.value)
                self.advance()
                right = self.binary(prec)
                left = ast.Compare(word, left, right)
            else:
                word = str(self.tok.value)
                self.advance()
                right = self.binary(prec)
                left = ast.Binary(word, left, right)
        return left

    @staticmethod
    def _precedence(op_type: str) -> int | None:
        return OP_PRECEDENCE.get(op_type)

    def unary(self) -> ast.Node:
        if self.check("MINUS", "PLUS"):
            op = "-" if self.advance().type == "MINUS" else "+"
            return ast.Unary(op, self.unary())
        if self.check("NOT"):
            self.advance()
            return ast.Unary("sio", self.unary())
        if self.check("THROW"):
            self.advance()
            return ast.Throw(self.unary())
        return self.power()

    def power(self) -> ast.Node:
        base = self.postfix()
        if self.check("POW"):
            self.advance()
            return ast.Binary("**", base, self.unary())  # right associative
        return base

    def postfix(self) -> ast.Node:
        node = self.primary()
        while True:
            if self.check("LPAREN"):
                node = self.call(node)
            elif self.check("LBRACKET"):
                self.advance()
                if self.check("COLON"):  # [:n]
                    self.advance()
                    stop = None if self.check("RBRACKET") else self.expression()
                    self.expect("RBRACKET", "']'")
                    node = ast.Slice(node, None, stop)
                    continue
                key = self.expression()
                if self.match("COLON"):
                    stop = None if self.check("RBRACKET") else self.expression()
                    self.expect("RBRACKET", "']'")
                    node = ast.Slice(node, key, stop)
                    continue
                self.expect("RBRACKET", "']'")
                node = ast.Index(node, key)
            elif self.check("DOT"):
                self.advance()
                node = ast.Member(node, self._member_name())
            elif self.check("RANGE"):  # `0..10`
                self.advance()
                node = ast.RangeLit(node, self.expression())
            else:
                break
        return node

    def _member_name(self) -> str:
        token = self.tok
        if token.type == "IDENT":
            self.advance()
            return token.value
        if token.type in TYPE_TOKENS:
            self.advance()
            return TYPE_NAMES[token.type]
        if token.type == "NOT":
            self.advance()
            return "sio"
        if token.type in KEYWORD_AS_NAME:
            self.advance()
            return KEYWORD_AS_NAME[token.type]
        raise self._error(token, f"Hitajiwa jina baada ya '.'",
                          f"Expected a property name after '.'",
                          "Mfano: `orodha.idadi`, `kamusi.funguo`")

    def call(self, callee: ast.Node) -> ast.Call:
        self.advance()  # (
        args, kwargs = self._arguments()
        return ast.Call(callee, args, kwargs)

    def _arguments(self) -> tuple[list[ast.Node], dict[str, ast.Node]]:
        args: list[ast.Node] = []
        kwargs: dict[str, ast.Node] = {}
        if not self.check("RPAREN"):
            while True:
                if self.check("IDENT") and self.tokens[self.current + 1].type == "ASSIGN":
                    key = self.advance().value
                    self.advance()
                    kwargs[key] = self.expression()
                else:
                    args.append(self.expression())
                if not self.match("COMMA"):
                    break
        self.expect("RPAREN", "')' kufunga vigezo")
        return args, kwargs

    def primary(self) -> ast.Node:
        token = self.tok

        if token.type == "INT":
            self.advance()
            return ast.Number(token.value)
        if token.type == "FLOAT":
            self.advance()
            return ast.Number(token.value)
        if token.type == "STRING":
            self.advance()
            return ast.Text(token.value)
        if token.type == "FSTRING":
            self.advance()
            return ast.Text("", self._fstring_parts(token))
        if token.type == "TRUE":
            self.advance()
            return ast.BoolLit(True)
        if token.type == "FALSE":
            self.advance()
            return ast.BoolLit(False)
        if token.type == "NULL":
            self.advance()
            return ast.NoneLit()
        if token.type == "IDENT":
            self.advance()
            return ast.Name(token.value)
        if token.type == "DEF":  # `kazi salimia` or `kazi(x) { ... }`
            self.advance()
            if self.check("IDENT") and self.tokens[self.current + 1].type != "LPAREN":
                name = self.advance().value
                return ast.FuncRef(name)
            params = self.parameter_list()
            if self.match("COLON") or self.match("ARROW"):
                if self.tok.type in TYPE_TOKENS:
                    self.advance()
            if self.check("ARROW"):
                self.advance()
                return ast.Lambda(params, ast.Block([ast.Return(self.expression())]))
            return ast.Lambda(params, self.block())
        if token.type == "NEW":  # `tengeneza Darasa(...)`
            self.advance()
            class_name = self.expect("IDENT", "jina la darasa").value
            if self.check("LPAREN"):
                self.advance()
                return ast.New(class_name, *self._arguments())
            return ast.New(class_name)
        if token.type == "SELF":
            self.advance()
            return ast.Name("mwenyewe")

        if token.type in TYPE_TOKENS:
            # `namba(...)` / `maneno(...)` behave as conversion functions
            self.advance()
            return ast.Name(TYPE_NAMES[token.type])

        if token.type == "LPAREN":
            self.advance()
            inner = self.expression()
            self.expect("RPAREN", "')'")
            return ast.Grouping(inner)
        if token.type == "LBRACKET":
            return self.list_literal()
        if token.type == "LBRACE":
            return self.dict_literal()
        if token.type == "SPREAD":
            self.advance()
            raise self._error(token, "`...` inaweza kutumika ndani ya orodha au kamusi pekee",
                              "'...' is only valid inside a list or dict literal")

        raise self._error(token, "Haijulikani neno hapa",
                          f"Unexpected token {token.type}",
                          self._hint_for(token))

    def list_literal(self) -> ast.ListLit:
        self.advance()  # [
        elements: list[ast.Node] = []
        while not self.check("RBRACKET"):
            if self.match("COMMA"):
                continue
            elements.append(self.expression())
            if not self.match("COMMA"):
                break
        self.expect("RBRACKET", "']' kufunga orodha")
        return ast.ListLit(elements)

    def dict_literal(self) -> ast.DictLit:
        self.advance()  # {
        pairs: list[tuple[ast.Node, ast.Node]] = []
        while not self.check("RBRACE"):
            if self.match("COMMA"):
                continue
            key = self.expression()
            self.expect("COLON", "':' baada ya funguo")
            value = self.expression()
            pairs.append((key, value))
            if not self.match("COMMA"):
                break
        self.expect("RBRACE", "'}' kufunga kamusi")
        return ast.DictLit(pairs)

    def _fstring_parts(self, token: Token) -> list:
        from .lexer import Lexer
        from .errors import Kosa as _Kosa
        parts: list = []
        for piece in token.value:
            if isinstance(piece, str):
                parts.append(piece)
            else:
                body, offset = piece
                sub = Lexer(body, self.filename)
                try:
                    sub_tokens = sub.tokenize()
                except _Kosa:
                    raise self._error(token,
                                      f"Kiolesura batili siyo maneno halali: {{{body}}}",
                                      f"Invalid interpolation: {{{body}}}")
                sub_parser = Parser(body, self.filename)
                sub_parser.tokens = sub_tokens
                try:
                    parts.append(sub_parser.expression())
                except _Kosa as exc:
                    raise self._error(
                        token,
                        f"Kiolesura batili siyo maneno halali: {{{body}}} — {exc.swahili}",
                        f"Invalid interpolation: {{{body}}} — {exc.english}")
        return parts


def parse(source: str, filename: str = "<kisarifi>") -> ast.Program:
    return Parser(source, filename).parse()