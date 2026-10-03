"""Node definitions for the Kiswahili syntax tree.

Deliberately plain dataclasses: one class per grammar production, no logic.
Class names are standard English so the implementation stays maintainable —
the Kiswahili lives in the keywords (`lexer.KEYWORDS`) and the diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Node:
    """Marker base so visitors can type-check cheaply."""

    __slots__ = ()


# --- expressions ------------------------------------------------------------

@dataclass
class Number(Node):
    value: int | float


@dataclass
class Text(Node):
    value: str
    parts: list[Any] | None = None   # f-string: str literals + expression nodes


@dataclass
class BoolLit(Node):
    value: bool


@dataclass
class NoneLit(Node):
    pass


@dataclass
class ListLit(Node):
    elements: list[Node]


@dataclass
class DictLit(Node):
    pairs: list[tuple[Node, Node]]


@dataclass
class RangeLit(Node):
    start: Node
    stop: Node
    step: Node | None = None


@dataclass
class Name(Node):
    ident: str


@dataclass
class Grouping(Node):
    inner: Node


@dataclass
class Unary(Node):
    op: str          # '-' '+' 'sio'
    operand: Node


@dataclass
class Binary(Node):
    op: str          # '+' '-' '*' '/' '//' '%' '**'
    left: Node
    right: Node


@dataclass
class Logical(Node):
    op: str          # 'na' | 'au'
    left: Node
    right: Node


@dataclass
class Compare(Node):
    op: str          # '==' '!=' '<' '<=' '>' '>=' 'iko' 'ni'
    left: Node
    right: Node


@dataclass
class Assign(Node):
    target: Node     # Name | Member | Index
    op: str          # '=' '+=' '-=' '*=' '/=' '//=' '%=' '**='
    value: Node


@dataclass
class Index(Node):
    target: Node
    key: Node


@dataclass
class Slice(Node):
    target: Node
    start: Node | None
    stop: Node | None


@dataclass
class Member(Node):
    target: Node
    name: str


@dataclass
class Call(Node):
    callee: Node
    args: list[Node]
    kwargs: dict[str, Node] = field(default_factory=dict)


@dataclass
class FuncRef(Node):
    """`kazi jina` in expression position — the function value itself."""

    ident: str


@dataclass
class Lambda(Node):
    """Anonymous function: `kazi(x) { x * 2 }`"""

    params: list[Parameter]
    body: Node


@dataclass
class New(Node):
    """`tengeneza Darasa(...)`"""

    class_name: str
    args: list[Node]
    kwargs: dict[str, Node] = field(default_factory=dict)


@dataclass
class Ternary(Node):
    """`chagua(test) { a } vingo { b }`"""

    test: Node
    consequent: Node
    alternate: Node


@dataclass
class Throw(Node):
    value: Node


# --- statements -------------------------------------------------------------

@dataclass
class Program(Node):
    body: list[Node]


@dataclass
class Declaration(Node):
    """`waka` — `x = 1`, or typed: `namba x = 1`"""

    name: str
    type_hint: str | None
    value: Node | None


@dataclass
class ExprStatement(Node):
    expr: Node


@dataclass
class Block(Node):
    body: list[Node]


@dataclass
class If(Node):
    test: Node
    body: Node
    orelse: Node | None = None


@dataclass
class While(Node):
    test: Node
    body: Node
    until: bool = False          # `hadi`


@dataclass
class ForEach(Node):
    """`kila x kwenye y { }` and `kwa x kwenye y { }`"""

    name: str
    iterable: Node
    body: Node
    yields_pairs: bool = False   # iterating a kamusi -> `x` becomes [key, value]


@dataclass
class Return(Node):
    value: Node | None


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class Pass(Node):
    pass


@dataclass
class Debugger(Node):
    pass


@dataclass
class Parameter(Node):
    name: str
    default: Node | None = None
    type_hint: str | None = None


@dataclass
class FuncDef(Node):
    name: str
    params: list[Parameter]
    body: Node
    type_hint: str | None = None
    arrow_hint: str | None = None
    is_arrow: bool = False


@dataclass
class ClassDef(Node):
    name: str
    fields: list[str]
    body: Block


@dataclass
class Try(Node):
    body: Node
    handler: str | None            # `kosa e { }`
    handler_body: Node | None
    orelse: Node | None = None     # `vingo` after handler: runs if no error
    finally_body: Node | None = None   # `mwisho { }`


@dataclass
class Import(Node):
    module: str
    alias: str | None = None