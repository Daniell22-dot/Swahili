"""Viwango wa kwanza — the built-in library.

Everything here is available in every Kiswahili program without importing
anything: `andika`, `ondoa`, `idadi`, the type conversions, and the methods you
can call on a maneno / orodha / kamusi.

Words were chosen so the whole library reads like an instruction in Swahili:
  kiria (lower)  pandisha (raise)  gawanya (split)  unganisha (join)
  ongeza (add)   ondoa (take out)  chomoa (filter out)  pangamiza (apply)
  ina (has)      futa (delete)     tafuta (look for)
"""

from __future__ import annotations

import math
import random as _random
import sys
from typing import Any, Callable

from .errors import TupaImbali
from .runtime import (BoundMethod, KiswahiliModule, NativeFunction,
                      SwahiliClass, SwahiliFunction, SwahiliInstance,
                      display, iterate, type_name)

MemberGetter = Callable[[Any], Any]


# --- small helpers ----------------------------------------------------------

def _needs(value: Any, kind: str) -> Any:
    actual = type_name(value)
    if actual != kind:
        raise TypeError(f"inahitaji {kind}, lakini ulipata {actual}")
    return value


def _callable(value: Any):
    if isinstance(value, (NativeFunction, SwahiliFunction, BoundMethod)):
        return value
    if not callable(value):
        raise TypeError("hijafanyika kazi")
    return value


# --- global functions -------------------------------------------------------

def _andika(*values: Any) -> None:
    sys.stdout.write(" ".join(display(v) for v in values) + "\n")
    sys.stdout.flush()


def _ondoa(prompt: str = "") -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == "":
        raise TupaImbali("mwisho wa kuingia")
    return line.rstrip("\n").rstrip("\r")


def _idadi(value: Any) -> int:
    if isinstance(value, (str, list, dict, range)):
        return len(value)
    raise TypeError(f"idadi haijasiki {type_name(value)}")


def _ainake(value: Any) -> str:
    return type_name(value)


def _namba(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip(), 0) if value.strip().startswith(("0x", "0o", "0b")) \
                else int(float(value.strip()))
        except ValueError:
            raise TypeError(f"hawezi kubadilisha '{value}' kuwa namba")
    raise TypeError(f"hawezi kubadilisha {type_name(value)} kuwa namba")


def _desimali(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            raise TypeError(f"hawezi kubadilisha '{value}' kuwa desimali")
    raise TypeError(f"hawezi kubadilisha {type_name(value)} kuwa desimali")


def _maneno(value: Any) -> str:
    if isinstance(value, str):
        return value
    return display(value)


def _hali(value: Any) -> bool:
    return bool(value)


def _orodha(value: Any) -> list:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        return list(value)
    if isinstance(value, range):
        return list(value)
    if isinstance(value, dict):
        return list(value.items())
    if isinstance(value, (SwahiliInstance,)):
        return list(value.fields.items())
    raise TypeError(f"hawezi kubadilisha {type_name(value)} kuwa orodha")


def _kamusi(value: Any) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return {k: v for k, v in value}
    raise TypeError(f"hawezi kubadilisha {type_name(value)} kuwa kamusi")


def _kipeano(start: int, stop: int, step: int = 1) -> range:
    return range(start, stop, step)


def _ondoka(code: int = 0, ujumbe: str = "") -> None:
    if ujumbe:
        sys.stderr.write(ujumbe + "\n")
    raise SystemExit(code)


# higher-order builtins: these need to call back into the interpreter

def _pangilia(interp, orodha_: list) -> list:
    return sorted(_needs(iterate(orodha_), "orodha"))


def _panga(interp, orodha_: list, kazi) -> list:
    return sorted(_needs(iterate(orodha_), "orodha"), key=interp.call(kazi))


def _pangamiza(interp, orodha_: list, kazi) -> list:
    return [interp.call(_callable(kazi), item)
            for item in _needs(iterate(orodha_), "orodha")]


def _chomoa(interp, orodha_: list, kazi) -> list:
    return [item for item in _needs(iterate(orodha_), "orodha")
            if interp.call(_callable(kazi), item)]


def _hesabia(interp, orodha_: list, kazi, mwanzo: Any = None) -> Any:
    items = _needs(iterate(orodha_), "orodha")
    if not items:
        return mwanzo
    acc = mwanzo if mwanzo is not None else items[0]
    rest = items if mwanzo is None else items
    index = 0 if mwanzo is not None else 1
    while index < len(rest):
        acc = interp.call(_callable(kazi), acc, rest[index])
        index += 1
    return acc


def _pinganya(interp, orodha_: list) -> list:
    copy = list(_needs(iterate(orodha_), "orodha"))
    _random.shuffle(copy)
    return copy


def _yoyote(interp, orodha_: list, kazi) -> bool:
    return any(interp.call(_callable(kazi), item)
               for item in _needs(iterate(orodha_), "orodha"))


def _zote(interp, orodha_: list, kazi) -> bool:
    return all(interp.call(_callable(kazi), item)
               for item in _needs(iterate(orodha_), "orodha"))


# --- methods on built-in types ---------------------------------------------

def _string_members(value: str) -> dict[str, Any]:
    return {
        "idadi": len(value),
        "kiria": NativeFunction("kiria", value.lower),
        "pandisha": NativeFunction("pandisha", value.upper),
        "badilisha": NativeFunction("badilisha",
                                    lambda a, b="": value.replace(a, b, 1)),
        "badilisha_kweli": NativeFunction("badilisha_kweli",
                                          lambda a, b="": value.replace(a, b)),
        "gava": NativeFunction("gava", lambda a, b=None: value[a:b]),
        "kati": NativeFunction("kati", lambda n: value[:n]),
        "mwisho": NativeFunction("mwisho", lambda n: value[-n:] if n else ""),
        "gawanya": NativeFunction("gawanya",
                                  lambda sep=" ": value.split(sep) if sep else list(value)),
        "unganisha": NativeFunction("unganisha", lambda parts, sep="": sep.join(map(str, parts))),
        "punguza": NativeFunction("punguza", value.strip),
        "anzia": NativeFunction("anzia", value.startswith),
        "ina": NativeFunction("ina", lambda x: x in value),
        "tafuta": NativeFunction("tafuta", lambda x: value.find(x)),
        "pindua": NativeFunction("pindua", lambda: value[::-1]),
        "namba": NativeFunction("namba", lambda: _namba(value)),
        "desimali": NativeFunction("desimali", lambda: _desimali(value)),
        "orodha": NativeFunction("orodha", lambda: list(value)),
        "nafasi": NativeFunction("nafasi", value.count),
        "neno": NativeFunction("neno", lambda n: value.replace(" ", "_", n)),
    }


def _list_members(interp, value: list) -> dict[str, Any]:
    return {
        "idadi": len(value),
        "ongeza": NativeFunction("ongeza", lambda x: (value.append(x), value)[1]),
        "ondoa": NativeFunction("ondoa", lambda i=-1: value.pop(i)),
        "ingiza": NativeFunction("ingiza", lambda i, x: (value.insert(i, x), value)[1]),
        "pata": NativeFunction("pata", lambda a, b=None: value[a:b]),
        "pindua": NativeFunction("pindua", lambda: list(reversed(value))),
        "ina": NativeFunction("ina", lambda x: x in value),
        "tafuta": NativeFunction("tafuta", lambda x: value.index(x) if x in value else -1),
        "pangilia": NativeFunction("pangilia", lambda: sorted(value)),
        "panga": NativeFunction("panga", lambda f: sorted(value, key=interp.call(f))),
        "pinganya": NativeFunction("pinganya", lambda: _pinganya(interp, value)),
        "itea": NativeFunction("itea", lambda: _random.choice(value) if value else None),
        "chagua": NativeFunction("chagua", lambda i: value[i]),
        "pangamiza": NativeFunction("pangamiza", lambda f: _pangamiza(interp, value, f)),
        "chomoa": NativeFunction("chomoa", lambda f: _chomoa(interp, value, f)),
        "hesabia": NativeFunction("hesabia",
                                  lambda f, mwanzo=None: _hesabia(interp, value, f, mwanzo)),
        "yoyote": NativeFunction("yoyote", lambda f: _yoyote(interp, value, f)),
        "zote": NativeFunction("zote", lambda f: _zote(interp, value, f)),
        "fanya": NativeFunction("fanya", lambda n: list(value) * max(0, int(n))),
        "changanya": NativeFunction("changanya", lambda y: value + list(y)),
        "flatu": NativeFunction("flatu", lambda: [x for item in value for x in
                                                  (item if isinstance(item, list) else [item])]),
        "jumlisha": NativeFunction("jumlisha", lambda: sum(value)),
        "nakili": NativeFunction("nakili", lambda: list(value)),
        "wao": NativeFunction("wao", lambda item: value.remove(item)),
    }


def _dict_members(interp, value: dict) -> dict[str, Any]:
    return {
        "funguo": list(value.keys()),
        "thamani": list(value.values()),
        "idadi": len(value),
        "ina": NativeFunction("ina", lambda k: k in value),
        "pata": NativeFunction("pata", lambda k, chaguo=None: value.get(k, chaguo)),
        "futa": NativeFunction("futa", lambda k: value.pop(k, None)),
        "ongeza": NativeFunction("ongeza", lambda k, v: (value.__setitem__(k, v), value)[1]),
        "changanya": NativeFunction("changanya", lambda y: {**value, **y}),
        "badilisha": NativeFunction(
            "badilisha",
            lambda f: {interp.call(f, k): v for k, v in value.items()}),
        "chomoa": NativeFunction(
            "chomoa",
            lambda f: {k: v for k, v in value.items() if interp.call(f, k, v)}),
        "orodha": NativeFunction("orodha", lambda: list(value.items())),
        "nakili": NativeFunction("nakili", lambda: dict(value)),
    }


def _number_members(value: int | float) -> dict[str, Any]:
    return {
        "kokotoa": NativeFunction("kokotoa", lambda: math.sqrt(abs(value))),
        "kubwa": NativeFunction("kubwa", lambda x: value ** x),
        "jumla": NativeFunction("jumla", lambda *rest: sum((value,) + rest)),
        "hakika": NativeFunction("hakika", lambda: str(value)),
    }


def get_member(interp, value: Any, name: str) -> Any:
    """`.jina` on a built-in value: property or method table."""
    if isinstance(value, str):
        table = _string_members(value)
    elif isinstance(value, list):
        table = _list_members(interp, value)
    elif isinstance(value, dict):
        table = _dict_members(interp, value)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        table = _number_members(value)
    else:
        raise TypeError(f"{type_name(value)} haina sehemu '{name}'")

    if name in table:
        return table[name]
    close = _suggest(name, table)
    if close:
        raise TypeError(f"{type_name(value)} haina sehemu '{name}'",
                        )
    raise TypeError(f"{type_name(value)} haina sehemu '{name}'")


def _suggest(name: str, table: dict) -> str:
    import difflib
    matches = difflib.get_close_matches(name, list(table), n=1, cutoff=0.6)
    return matches[0] if matches else ""


# --- the global environment -------------------------------------------------

def install(env) -> None:
    """Define every built-in into `env` (the global scope)."""
    env.define("andika", NativeFunction("andika", _andika))
    env.define("ondoa", NativeFunction("ondoa", _ondoa))
    env.define("idadi", NativeFunction("idadi", _idadi))
    env.define("ainake", NativeFunction("ainake", _ainake))
    env.define("namba", NativeFunction("namba", _namba))
    env.define("desimali", NativeFunction("desimali", _desimali))
    env.define("maneno", NativeFunction("maneno", _maneno))
    env.define("hali", NativeFunction("hali", _hali))
    env.define("orodha", NativeFunction("orodha", _orodha))
    env.define("kamusi", NativeFunction("kamusi", _kamusi))
    env.define("kipeano", NativeFunction("kipeano", _kipeano))
    env.define("ondoka", NativeFunction("ondoka", _ondoka))

    env.define("pangilia", NativeFunction("pangilia", _pangilia, needs_interp=True))
    env.define("panga", NativeFunction("panga", _panga, needs_interp=True))
    env.define("pangamiza", NativeFunction("pangamiza", _pangamiza, needs_interp=True))
    env.define("chomoa", NativeFunction("chomoa", _chomoa, needs_interp=True))
    env.define("hesabia", NativeFunction("hesabia", _hesabia, needs_interp=True))
    env.define("pinganya", NativeFunction("pinganya", _pinganya, needs_interp=True))
    env.define("yoyote", NativeFunction("yoyote", _yoyote, needs_interp=True))
    env.define("zote", NativeFunction("zote", _zote, needs_interp=True))