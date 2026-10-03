"""Kichanganuzi — the Kiswahili lexer.

Turns Kiswahili source text into a flat list of tokens. Whitespace and newlines
are insignificant (unlike Python); blocks are delimited by `{}`. Comments start
with `#`.

Also supported, because they make the language nicer to actually use:
  * `1_000_000` digit separators
  * `0..10` range literals (they become calls to `kipeano()`)
  * f-strings: `f"Habari {jina}, umri {umri}"`
"""

from __future__ import annotations

from .errors import Kosa

# --- word lists -------------------------------------------------------------

KEYWORDS = {
    # literals & types
    "kweli": "TRUE", "sikweli": "FALSE", "hakuna": "NULL",
    "namba": "INT_TYPE", "desimali": "FLOAT_TYPE", "maneno": "STRING_TYPE",
    "orodha": "LIST_TYPE", "kamusi": "DICT_TYPE", "hali": "BOOL_TYPE",
    # control flow
    "kama": "IF", "vingo": "ELSE", "wakati": "WHILE", "hadi": "UNTIL",
    "kila": "EACH", "kwa": "FOR", "kwenye": "IN",
    "rudia": "RETURN", "vunja": "BREAK", "endelea": "CONTINUE",
    "nenda": "PASS", "chagua": "TERNARY", "kati": "DEBUGGER",
    # errors
    "jaribu": "TRY", "kosa": "EXCEPT", "mwisho": "FINALLY", "tupa": "THROW",
    # declarations
    "kazi": "DEF", "darasa": "CLASS", "tengeneza": "NEW", "mwenyewe": "SELF",
    "tumia": "IMPORT",
    # operators spelled as words
    "na": "AND", "au": "OR", "sio": "NOT", "iko": "INOP", "ni": "IS",
}

TYPE_TOKENS = {"INT_TYPE", "FLOAT_TYPE", "STRING_TYPE", "LIST_TYPE",
               "DICT_TYPE", "BOOL_TYPE"}

# longest-first so that `**=` wins over `**` wins over `*`
PUNCTUATION = [
    ("**=", "POW_ASSIGN"), ("//=", "IDIV_ASSIGN"), ("...", "SPREAD"),
    ("+=", "ADD_ASSIGN"), ("-=", "SUB_ASSIGN"), ("*=", "MUL_ASSIGN"),
    ("/=", "DIV_ASSIGN"), ("%=", "MOD_ASSIGN"), ("->", "ARROW"),
    ("**", "POW"), ("//", "IDIV"), ("..", "RANGE"),
    ("==", "EQ"), ("!=", "NEQ"), ("<=", "LTE"), (">=", "GTE"),
    ("+", "PLUS"), ("-", "MINUS"), ("*", "STAR"), ("/", "SLASH"),
    ("%", "PERCENT"), ("=", "ASSIGN"), ("<", "LT"), (">", "GT"),
    ("(", "LPAREN"), (")", "RPAREN"), ("{", "LBRACE"), ("}", "RBRACE"),
    ("[", "LBRACKET"), ("]", "RBRACKET"), (",", "COMMA"), (".", "DOT"),
    (":", "COLON"), (";", "SEMI"), ("?", "QUESTION"),
]

ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\",
    '"': '"', "'": "'", "`": "`", "$": "$",
}

OPENERS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {v: k for k, v in OPENERS.items()}

# A newline after any of these does not end a statement, so conditions and
# arguments may wrap onto the next line:
#   kama wingu ni kubwa na
#       jua iko juu
NEWLINE_ABSORBS = {
    "PLUS", "MINUS", "STAR", "SLASH", "IDIV", "PERCENT", "POW", "DOT", "COMMA",
    "COLON", "QUESTION", "ASSIGN", "ADD_ASSIGN", "SUB_ASSIGN", "MUL_ASSIGN",
    "DIV_ASSIGN", "IDIV_ASSIGN", "MOD_ASSIGN", "POW_ASSIGN",
    "LPAREN", "LBRACKET", "LBRACE", "AND", "OR", "NOT", "INOP", "IS",
    "IF", "WHILE", "UNTIL", "EACH", "FOR", "IN", "EXCEPT", "FINALLY",
    "TERNARY", "NEW", "DEF", "ARROW",
}


class Token:
    __slots__ = ("type", "value", "index", "line", "column", "interpolated")

    def __init__(self, type_, value, index, line, column, interpolated=False):
        self.type = type_
        self.value = value
        self.index = index
        self.line = line
        self.column = column
        self.interpolated = interpolated

    @property
    def is_op(self) -> bool:
        return self.type in OP_PRECEDENCE

    def __repr__(self) -> str:
        return f"<{self.type}:{self.value!r}@{self.line}:{self.column}>"


# binding power per infix operator; higher binds tighter
OP_PRECEDENCE = {
    "OR": 1,
    "AND": 2,
    "INOP": 4, "IS": 4, "EQ": 4, "NEQ": 4, "LT": 4, "LTE": 4, "GT": 4, "GTE": 4,
    "PLUS": 5, "MINUS": 5,
    "STAR": 6, "SLASH": 6, "IDIV": 6, "PERCENT": 6,
    "POW": 8,
}


class Lexer:
    def __init__(self, source: str, filename: str = "<kisarifi>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(source)
        self.depth = 0
        self.last: Token | None = None

    # --- plumbing ----------------------------------------------------------

    def _peek(self, offset: int = 0) -> str:
        i = self.pos + offset
        return self.source[i] if i < self.length else ""

    def _advance(self, count: int = 1) -> str:
        chunk = self.source[self.pos:self.pos + count]
        for ch in chunk:
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
        self.pos += count
        return chunk

    def _error(self, swahili: str, english: str, hint: str = "") -> Kosa:
        return Kosa("Kichanganuzi / Lexer", swahili, english, self.source,
                    self.pos, hint)

    # --- main loop ---------------------------------------------------------

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.pos < self.length:
            ch = self._peek()

            if ch in " \t\r":
                self._advance()
                continue

            if ch == "\n":
                token = self._maybe_newline()
                if token is not None:
                    tokens.append(token)
                    self.last = token
                self._advance()
                continue

            if ch == "#":
                while self.pos < self.length and self._peek() != "\n":
                    self._advance()
                continue

            if ch == '"' or (ch in "fF" and self._peek(1) == '"'
                             and self._is_fstring_start()):
                tokens.append(self._emit(self._read_string()))
                continue

            if ch.isdigit():
                tokens.append(self._emit(self._read_number()))
                continue

            if self._is_ident_start(ch):
                tokens.append(self._emit(self._read_word()))
                continue

            token = self._read_punctuation()
            if token is None:
                raise self._error(
                    f"Alama isiyojulikana: '{ch}'",
                    f"Unknown symbol: {ch!r}",
                    "Nakili mstari huu kutoka Kiswahili ki kamili?",
                )
            tokens.append(self._emit(token))

        tokens.append(Token("EOF", None, self.pos, self.line, self.col))
        return tokens

    def _emit(self, token: Token) -> Token:
        self.last = token
        if token.type in OPENERS:
            self.depth += 1
        elif token.type in CLOSERS:
            self.depth = max(0, self.depth - 1)
        return token

    def _maybe_newline(self) -> Token | None:
        """A newline only ends a statement at bracket depth 0."""
        if self.depth > 0:
            return None
        if self.last is None or self.last.type in NEWLINE_ABSORBS:
            return None
        return Token("NEWLINE", "\n", self.pos, self.line, self.col)

    def _is_fstring_start(self) -> bool:
        # `f"..."` only when `f` is not part of a longer identifier
        return not (self.pos > 0 and (self.source[self.pos - 1].isalnum()
                                      or self.source[self.pos - 1] == "_"))

    def _is_ident_start(self, ch: str) -> bool:
        return ch.isalpha() or ch == "_"

    def _is_ident_part(self, ch: str) -> bool:
        return ch.isalnum() or ch == "_"

    # --- readers -----------------------------------------------------------

    def _read_punctuation(self) -> Token | None:
        for text, kind in PUNCTUATION:
            if self.source.startswith(text, self.pos):
                start_index, start_line, start_col = self.pos, self.line, self.col
                self._advance(len(text))
                return Token(kind, text, start_index, start_line, start_col)
        return None

    def _read_word(self) -> Token:
        start_index, start_line, start_col = self.pos, self.line, self.col
        start = self.pos
        while self.pos < self.length and self._is_ident_part(self._peek()):
            self._advance()
        word = self.source[start:self.pos]
        kind = KEYWORDS.get(word, "IDENT")
        return Token(kind, word, start_index, start_line, start_col)

    def _read_number(self) -> Token:
        start_index, start_line, start_col = self.pos, self.line, self.col
        start = self.pos
        while self.pos < self.length:
            ch = self._peek()
            if ch.isdigit() or ch == "_":
                self._advance()
            elif ch == "." and self._peek(1).isdigit() and self.source[start:self.pos] \
                    and "." not in self.source[start:self.pos]:
                self._advance()
            else:
                break

        raw = self.source[start:self.pos].replace("_", "")
        if self._peek() in "eE" and (self._peek(1).isdigit()
                                     or self._peek(1) in "+-"):
            self._advance(2)
            while self._peek().isdigit():
                self._advance()
            raw = self.source[start:self.pos].replace("_", "")

        is_float = "." in raw or "e" in raw or "E" in raw
        value = float(raw) if is_float else int(raw)
        kind = "FLOAT" if is_float else "INT"
        return Token(kind, value, start_index, start_line, start_col)

    def _read_string(self) -> Token:
        start_index, start_line, start_col = self.pos, self.line, self.col
        interpolated = False
        if self._peek() in "fF":
            interpolated = True
            self._advance()
        if self._peek() != '"':
            raise self._error("Fomili haisanzwi kwa neno", "Unterminated string literal")
        self._advance()  # opening quote

        pieces: list[str] = []
        buf: list[str] = []

        while True:
            if self.pos >= self.length:
                raise self._error("Fomili haisanzwi kwa neno",
                                  "Unterminated string literal")
            ch = self._peek()
            if ch == '"':
                self._advance()
                break
            if ch == "\n":
                raise self._error("Fomili haisanzwi kwa mstari",
                                  "Newline inside string literal")
            if ch == "\\":
                buf.append(self._read_escape())
                continue
            if interpolated and ch == "{":
                if self._peek(1) == "{":
                    self._advance(2)
                    buf.append("{")
                    continue
                pieces.append("".join(buf))
                buf = []
                self._advance()          # eat the `{`
                pieces.append(self._read_interpolation())
                continue
            if interpolated and ch == "}" and self._peek(1) == "}":
                self._advance(2)
                buf.append("}")
                continue
            buf.append(self._advance())

        pieces.append("".join(buf))
        if interpolated:
            return Token("FSTRING", pieces, start_index, start_line, start_col, True)
        return Token("STRING", "".join(pieces), start_index, start_line, start_col)

    def _read_escape(self) -> str:
        self._advance()  # backslash
        ch = self._advance()
        if ch in ESCAPES:
            return ESCAPES[ch]
        if ch == "u":
            code = self.source[self.pos:self.pos + 4]
            if len(code) == 4:
                try:
                    self._advance(4)
                    return chr(int(code, 16))
                except ValueError:
                    pass
        return "\\" + ch

    def _read_interpolation(self) -> tuple[str, int]:
        """Consume the body of `{ ... }` (the `{` is already eaten) and return
        (source-of-expression, offset-of-expression)."""
        depth = 0
        start = self.pos
        while self.pos < self.length:
            ch = self._peek()
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if ch == "}" and depth == 0:
                    body = self.source[start:self.pos]
                    self._advance()
                    return body, start
                depth -= 1
            self._advance()
        raise self._error("Kiolesura kimefungwa",
                          "Unclosed interpolation in f-string")


def tokenize(source: str, filename: str = "<kisarifi>") -> list[Token]:
    return Lexer(source, filename).tokenize()