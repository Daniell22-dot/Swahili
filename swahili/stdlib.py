"""Viwango la pili — the standard library.

Modules you pull in with `tumia`:

    tumia hesabu        maths
    tumia orodha_kazi   extra list tools
    tumia maneno_kazi   extra string tools
    tumia kansa         randomness
    tumia wakati        time and dates
    tumia mfumo         system / environment
    tumia faili         file reading and writing

Each factory returns `{name: value}` for a `KiswahiliModule`.
"""

from __future__ import annotations

import math
import os
import random as _random
import sys
import time as _time
from datetime import datetime as _datetime

from .builtins import _pangamiza, _chomoa, _pinganya
from .runtime import NativeFunction


def _jumla(*values: object) -> float | int:
    """`hesabu.jumla(1, 2, 3)` or `hesabu.jumla([1, 2, 3])`."""
    if len(values) == 1 and isinstance(values[0], (list, tuple, range)):
        return sum(values[0])
    return sum(values)


def _hesabu(interp) -> dict:
    return {
        "pi": NativeFunction("pi", lambda: math.pi),
        "e": NativeFunction("e", lambda: math.e),
        "kokotoa": NativeFunction("kokotoa", math.sqrt),
        "kadiria": NativeFunction("kadiria", round),
        "jumla": NativeFunction("jumla", _jumla),
        "zidisha": NativeFunction("zidisha", lambda a, b=1: a * b),
        "jumlisha": NativeFunction("jumlisha", lambda xs: sum(xs)),
        "kipeano": NativeFunction("kipeano", lambda n: list(range(int(n)))),
        "hiki": NativeFunction("hiki", lambda x: math.floor(x)),
        "hapa": NativeFunction("hapa", lambda x: math.ceil(x)),
        "kabla": NativeFunction("kabla", lambda x: math.trunc(x)),
        "jumbufu": NativeFunction("jumbufu", lambda x: math.fsum(
            x if isinstance(x, list) else [x])),
        "kadiria_max": NativeFunction("kadiria_max", lambda xs: max(xs)),
        "kadiria_min": NativeFunction("kadiria_min", lambda xs: min(xs)),
        "sinu": NativeFunction("sinu", math.sin),
        "kosi": NativeFunction("kosi", math.cos),
        "tana": NativeFunction("tana", math.tan),
        "logariti": NativeFunction("logariti", math.log),
        "eksa": NativeFunction("eksa", math.exp),
        "namba_nyukuri": NativeFunction("namba_nyukuri", lambda: _random.random()),
        "namba_kamili": NativeFunction("namba_kamili", lambda x: int(x)),
        "jumla_karibia": NativeFunction("jumla_karibia", lambda a, b, p=2:
                                        round(a / b, p) if b else 0.0),
    }


def _orodha_kazi(interp) -> dict:
    # `interp` is captured from the factory, so none of these need the
    # needs_interp calling convention.
    return {
        "pangilia": NativeFunction("pangilia", lambda xs: sorted(xs)),
        "panga": NativeFunction("panga", lambda xs, f: sorted(xs, key=interp.call(f))),
        "pangamiza": NativeFunction("pangamiza",
                                    lambda xs, f: _pangamiza(interp, xs, f)),
        "chomoa": NativeFunction("chomoa",
                                 lambda xs, f: _chomoa(interp, xs, f)),
        "pinganya": NativeFunction("pinganya", lambda xs: _pinganya(interp, xs)),
        "hakika": NativeFunction("hakika", lambda xs: list(xs)),
    }


def _maneno_kazi(interp) -> dict:
    return {
        "kati": NativeFunction("kati", lambda s, a, b=None: s[a:b]),
        "gavanya": NativeFunction("gavanya", lambda s, sep=" ": s.split(sep)),
        "unganisha": NativeFunction("unganisha",
                                    lambda parts, sep="": sep.join(map(str, parts))),
        "badilisha": NativeFunction("badilisha",
                                    lambda s, a, b="": s.replace(a, b)),
        "kiria": NativeFunction("kiria", lambda s: s.lower()),
        "pandisha": NativeFunction("pandisha", lambda s: s.upper()),
        "punguza": NativeFunction("punguza", lambda s: s.strip()),
        "anzia": NativeFunction("anzia", lambda s, x: s.startswith(x)),
        "ina": NativeFunction("ina", lambda s, x: x in s),
        "tafuta": NativeFunction("tafuta", lambda s, x: s.find(x)),
    }


def _kansa(interp) -> dict:
    return {
        "namba": NativeFunction("namba", lambda a=0, b=1:
                                _random.randint(a, b - 1) if b > a else a),
        "kiwango": NativeFunction("kiwango", lambda a=0.0, b=1.0: _random.uniform(a, b)),
        "chagua": NativeFunction("chagua", lambda xs: _random.choice(list(xs))),
        "sampuli": NativeFunction("sampuli", lambda xs, n=1:
                                  _random.sample(list(xs), n)),
        "changanua": NativeFunction("changanua", lambda p=True: _random.random() < p),
        "nondowe": NativeFunction("nondowe", _random.gauss),
    }


def _wakati(interp) -> dict:
    return {
        "sasa": NativeFunction("sasa", lambda: _time.time()),
        "sekunde": NativeFunction("sekunde", lambda s: _time.sleep(s)),
        "mwaka": NativeFunction("mwaka", lambda: _datetime.now().year),
        "mwezi": NativeFunction("mwezi", lambda: _datetime.now().month),
        "siku": NativeFunction("siku", lambda: _datetime.now().day),
        "saa": NativeFunction("saa", lambda: _datetime.now().hour),
        "dakika": NativeFunction("dakika", lambda: _datetime.now().minute),
        "leo": NativeFunction("leo", lambda: _datetime.now().strftime("%Y-%m-%d")),
        "wakati": NativeFunction("wakati",
                                 lambda: _datetime.now().strftime("%H:%M:%S")),
        "kipeano": NativeFunction("kipeano", lambda: int(_time.time() * 1000)),
    }


def _mfumo(interp) -> dict:
    return {
        "stdin_kuna": NativeFunction("stdin_kuna", lambda: sys.stdin.isatty()),
        "andika_kosa": NativeFunction("andika_kosa",
                                      lambda *xs: sys.stderr.write(
                                          " ".join(str(x) for x in xs) + "\n")),
        "ondoa_kweli": NativeFunction("ondoa_kweli", lambda: sys.stdout.isatty()),
        "mazingira": NativeFunction("mazingira", lambda jina: os.environ.get(jina)),
        "folda": NativeFunction("folda", lambda p=".": os.getcwd() if p == "." else
                                os.path.abspath(p)),
        "orodha": NativeFunction("orodha", lambda p=".": sorted(os.listdir(p))),
        "mfumo": NativeFunction("mfumo", lambda: sys.platform),
        "python": NativeFunction("python", lambda: sys.version.split()[0]),
        "kufa": NativeFunction("kufa", lambda code=0: sys.exit(code)),
    }


def _faili(reader) -> dict:
    def _soma(jina, encoding="utf-8"):
        with open(jina, "r", encoding=encoding) as handle:
            return handle.read()

    def _andika(jina, maudhui, append=False):
        with open(jina, "a" if append else "w", encoding="utf-8") as handle:
            handle.write(maudhui)
        return len(maudhui)

    def _mistari(jina, encoding="utf-8"):
        with open(jina, "r", encoding=encoding) as handle:
            return handle.read().splitlines()

    def _ipo(jina):
        return os.path.isfile(jina)

    def _futa(jina):
        os.remove(jina)
        return True

    def _tengeneza(jina):
        open(jina, "a", encoding="utf-8").close()
        return jina

    return {
        "soma": NativeFunction("soma", _soma),
        "andika": NativeFunction("andika", _andika),
        "mistari": NativeFunction("mistari", _mistari),
        "ipo": NativeFunction("ipo", _ipo),
        "futa": NativeFunction("futa", _futa),
        "tengeneza": NativeFunction("tengeneza", _tengeneza),
    }


MODULES = {
    "hesabu": _hesabu,
    "orodha_kazi": _orodha_kazi,
    "maneno_kazi": _maneno_kazi,
    "kansa": _kansa,
    "wakati": _wakati,
    "mfumo": _mfumo,
    "faili": _faili,
}