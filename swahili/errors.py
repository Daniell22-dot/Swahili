"""Kiswahili error layer.

Every error message is bilingual: Kiswahili first (because that is the point of
the language), then English so that nobody is locked out of their own compiler.
"""

from __future__ import annotations

SEPARATOR = "=" * 62


class KiswahiliError(Exception):
    """Base for everything we raise on purpose."""

    def __init__(self, swahili: str, english: str = "", line: int = 0, column: int = 0):
        self.swahili = swahili
        self.english = english or swahili
        self.line = line
        self.column = column
        super().__init__(self.render())

    def render(self) -> str:
        parts = [self.swahili]
        if self.english and self.english != self.swahili:
            parts.append(self.english)
        return "\n".join(parts)


class LexError(KiswahiliError):
    pass


class ParseError(KiswahiliError):
    pass


class RuntimeErr(KiswahiliError):
    pass


def _line_of(source: str, index: int) -> tuple[int, int]:
    head = source[:index]
    line = head.count("\n") + 1
    column = index - (head.rfind("\n") + 1) + 1
    return line, column


class Kosa(KiswahiliError):
    """A formatted, user-facing error with source context.

    Built by the lexer/parser/interpreter, rendered once by the CLI::

        Kosa la Kiswahili
        ==============================
          kosa.kisw  mistari 12, kolonyo 9
          12 |     andika jina + j
             |              ^ Hamna jina la 'j'
          Hamna jina la 'j'
          No such name: 'j'
    """

    def __init__(self, kind: str, swahili: str, english: str, source: str,
                 index: int, hint: str = ""):
        line, column = _line_of(source, index)
        self.kind = kind
        self.hint = hint
        self.source = source
        self.index = index
        super().__init__(swahili, english, line, column)

    def _caret_line(self) -> tuple[str, str]:
        lines = self.source.split("\n")
        if not (1 <= self.line <= len(lines)):
            return "", ""
        text = lines[self.line - 1]
        stripped = text.lstrip()
        indent = len(text) - len(stripped)
        pointer = " " * max(0, indent + self.column - 1) + "^"
        return text, pointer

    def render(self) -> str:
        out = [SEPARATOR, f"KOSA LA KISWAHILI  /  {self.kind}", SEPARATOR]
        text, pointer = self._caret_line()
        if text:
            gutter = str(self.line)
            pad = " " * len(gutter)
            out.append(f"{pad}  {gutter} | {text}")
            out.append(f"{pad}  {pad} | {pointer} {self.swahili}")
            if self.english != self.swahili:
                out.append(f"{pad}    | {self.english}")
        else:
            out.append(f"{self.swahili}")
            if self.english != self.swahili:
                out.append(f"{self.english}")
        if self.hint:
            out.append("")
            out.append(f"  mawazo: {self.hint}")
        return "\n".join(out)


# --- internal control-flow signals (never shown to the user) ---------------

class Rudeia(Exception):
    """`rudia` — early return."""


class Vunja(Exception):
    """`vunja` — break."""


class Endelea(Exception):
    """`endelea` — continue."""


class TupaImbali(Exception):
    """`tupa` — a user-thrown value travelling up the stack."""