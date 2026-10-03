"""Majadiliano — runtime values and scopes.

Holds the things the interpreter manipulates directly: environments, user
functions and classes, instances, native (host-provided) functions and modules.
"""

from __future__ import annotations

from typing import Any, Callable


class Environment:
    __slots__ = ("vars", "parent")

    def __init__(self, parent: "Environment | None" = None):
        self.vars: dict[str, Any] = {}
        self.parent = parent

    def define(self, name: str, value: Any) -> None:
        self.vars[name] = value

    def has(self, name: str) -> bool:
        env: Environment | None = self
        while env is not None:
            if name in env.vars:
                return True
            env = env.parent
        return False

    def get(self, name: str) -> Any:
        env: Environment | None = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise KeyError(name)

    def assign(self, name: str, value: Any) -> bool:
        env: Environment | None = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return True
            env = env.parent
        return False

    def root(self) -> "Environment":
        env = self
        while env.parent is not None:
            env = env.parent
        return env

    def all_names(self) -> list[str]:
        seen: list[str] = []
        env: Environment | None = self
        while env is not None:
            for name in env.vars:
                if name not in seen:
                    seen.append(name)
            env = env.parent
        return seen


class NativeFunction:
    """A function implemented in the host (Python), like `andika`."""

    __slots__ = ("name", "fn", "needs_interp")

    def __init__(self, name: str, fn: Callable[..., Any], needs_interp: bool = False):
        self.name = name
        self.fn = fn
        self.needs_interp = needs_interp

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<kazi ya ndani {self.name}>"


class SwahiliFunction:
    """A `kazi` declared in Kiswahili."""

    __slots__ = ("name", "params", "body", "closure", "type_hint", "arrow_hint")

    def __init__(self, name, params, body, closure, type_hint=None, arrow_hint=None):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.type_hint = type_hint
        self.arrow_hint = arrow_hint

    def __repr__(self) -> str:
        names = ", ".join(p.name for p in self.params)
        return f"<kazi {self.name}({names})>"


class SwahiliClass:
    __slots__ = ("name", "fields", "methods", "closure")

    def __init__(self, name: str, fields: list[str], closure: Environment):
        self.name = name
        self.fields = fields
        self.methods: dict[str, SwahiliFunction] = {}
        self.closure = closure

    def __repr__(self) -> str:
        return f"<darasa {self.name}>"


class SwahiliInstance:
    __slots__ = ("cls", "fields")

    def __init__(self, cls: SwahiliClass):
        self.cls = cls
        self.fields: dict[str, Any] = {name: None for name in cls.fields}

    @property
    def name(self) -> str:
        return f"{self.cls.name}"

    def __repr__(self) -> str:
        inner = ", ".join(f"{k}: {v!r}" for k, v in self.fields.items())
        return f"<mwanafunzi {self.cls.name} {{{inner}}}>"


class BoundMethod:
    __slots__ = ("function", "instance")

    def __init__(self, function: SwahiliFunction, instance: SwahiliInstance):
        self.function = function
        self.instance = instance

    def __repr__(self) -> str:
        return f"<kazi {self.function.name} ya {self.instance.name}>"


class KiswahiliModule:
    """A loaded module — either built-in or a `.kisw` file."""

    __slots__ = ("name", "members")

    def __init__(self, name: str, members: dict[str, Any]):
        self.name = name
        self.members = members

    def __repr__(self) -> str:
        return f"<moduli {self.name}>"


def type_name(value: Any) -> str:
    """`ainake` — Kiswahili type name of a value."""
    if value is True or value is False:
        return "hali"
    if value is None:
        return "hakuna"
    if isinstance(value, SwahiliFunction):
        return "kazi"
    if isinstance(value, (BoundMethod, NativeFunction)):
        return "kazi"
    if isinstance(value, SwahiliClass):
        return "darasa"
    if isinstance(value, SwahiliInstance):
        return "mwanafunzi"
    if isinstance(value, KiswahiliModule):
        return "moduli"
    if isinstance(value, int):
        return "namba"
    if isinstance(value, float):
        return "desimali"
    if isinstance(value, str):
        return "maneno"
    if isinstance(value, range):
        return "kipeano"
    if isinstance(value, list):
        return "orodha"
    if isinstance(value, dict):
        return "kamusi"
    return "jinsi"


def display(value: Any) -> str:
    """How a value looks when printed with `andika`."""
    if value is True:
        return "kweli"
    if value is False:
        return "sikweli"
    if value is None:
        return "hakuna"
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(display_repr(v) for v in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        inner = ", ".join(f"{display_repr(k)}: {display_repr(v)}"
                          for k, v in value.items())
        return "{" + inner + "}"
    if isinstance(value, range):
        return f"kipeano({value.start}, {value.stop})"
    return repr(value)


def display_repr(value: Any) -> str:
    """Like `display` but strings get quotes — used inside containers."""
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (SwahiliInstance, SwahiliFunction, SwahiliClass,
                          KiswahiliModule, NativeFunction, BoundMethod)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(display_repr(v) for v in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{" + ", ".join(f"{display_repr(k)}: {display_repr(v)}"
                               for k, v in value.items()) + "}"
    return display(value)


def iterate(value: Any) -> list:
    """Turn an iterable into a list, or raise a friendly error."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return list(value)
    if isinstance(value, range):
        return list(value)
    if isinstance(value, dict):
        return list(value.keys())
    if value is None:
        raise TypeError("hakuna hakuna")
    if hasattr(value, "__iter__"):
        return list(value)
    raise TypeError(type_name(value))