"""Viwango la pili — the standard library.

Modules you pull in with `tumia`:

    tumia hesabu        maths
    tumia orodha_kazi   extra list tools
    tumia maneno_kazi   extra string tools
    tumia kansa         randomness
    tumia wakati        time and dates
    tumia mfumo         system / environment
    tumia faili         file reading and writing
    tumia umbizo        JSON formatting
    tumia seva          HTTP server (network capability)

Each factory returns `{name: value}` for a `KiswahiliModule`.
"""

from __future__ import annotations

import math
import os
import random as _random
import secrets as _secrets
import sys
import time as _time
from datetime import datetime as _datetime

from .builtins import _pangamiza, _chomoa, _pinganya
from ..errors import RuntimeErr
from ..runtime import NativeFunction


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


def _siri(interp) -> dict:
    def _tokeni(n=32):
        n = int(n)
        if n < 0:
            raise RuntimeErr("siri.tokeni inahitaji n >= 0",
                             "siri.tokeni requires n >= 0")
        return _secrets.token_hex(n)

    def _baiti(n=16):
        n = int(n)
        if n < 0:
            raise RuntimeErr("siri.baiti inahitaji n >= 0",
                             "siri.baiti requires n >= 0")
        return list(_secrets.token_bytes(n))

    def _namba(a, b):
        a, b = int(a), int(b)
        if b <= a:
            raise RuntimeErr(
                "siri.namba inahitaji b > a",
                "siri.namba requires b > a")
        return a + _secrets.randbelow(b - a)

    def _chagua(xs):
        items = list(xs)
        if not items:
            raise RuntimeErr("siri.chagua inahitaji orodha isiyo tupu",
                             "siri.chagua requires a non-empty list")
        return _secrets.choice(items)

    return {
        "tokeni": NativeFunction("tokeni", _tokeni),
        "baiti": NativeFunction("baiti", _baiti),
        "namba": NativeFunction("namba", _namba),
        "chagua": NativeFunction("chagua", _chagua),
        "linganisha": NativeFunction("linganisha", _secrets.compare_digest),
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
    allowed = getattr(interp, "allowed_env", None)

    def _env(name):
        if allowed is not None and name not in allowed:
            return None
        return os.environ.get(name)

    mazingira = NativeFunction("mazingira", _env)
    if getattr(interp, "sandbox", False):
        # In the sandbox only the explicit env capability is exposed.
        return {"mazingira": mazingira}
    return {
        "stdin_kuna": NativeFunction("stdin_kuna", lambda: sys.stdin.isatty()),
        "andika_kosa": NativeFunction("andika_kosa",
                                      lambda *xs: sys.stderr.write(
                                          " ".join(str(x) for x in xs) + "\n")),
        "ondoa_kweli": NativeFunction("ondoa_kweli", lambda: sys.stdout.isatty()),
        "mazingira": mazingira,
        "folda": NativeFunction("folda", lambda p=".": os.getcwd() if p == "." else
                                os.path.abspath(p)),
        "orodha": NativeFunction("orodha", lambda p=".": sorted(os.listdir(p))),
        "mfumo": NativeFunction("mfumo", lambda: sys.platform),
        "python": NativeFunction("python", lambda: sys.version.split()[0]),
        "kufa": NativeFunction("kufa", lambda code=0: sys.exit(code)),
    }


def _faili(interp) -> dict:
    roots = getattr(interp, "allowed_fs", None)

    def _guard(path):
        """Confine access to the allowed roots, resolving symlinks/`..`."""
        if roots is None:
            return path
        target = os.path.normcase(os.path.realpath(str(path)))
        for root in roots:
            base = os.path.normcase(os.path.realpath(root))
            if target == base or target.startswith(base + os.sep):
                return path
        raise RuntimeErr(
            "Huwezi kufikia faili hii: iko nje ya folda zilizoruhusiwa",
            "Cannot access this file: it is outside the allowed folders")

    def _soma(jina, encoding="utf-8"):
        with open(_guard(jina), "r", encoding=encoding) as handle:
            return handle.read()

    def _andika(jina, maudhui, append=False):
        with open(_guard(jina), "a" if append else "w", encoding="utf-8") as handle:
            handle.write(maudhui)
        return len(maudhui)

    def _mistari(jina, encoding="utf-8"):
        with open(_guard(jina), "r", encoding=encoding) as handle:
            return handle.read().splitlines()

    def _ipo(jina):
        return os.path.isfile(_guard(jina))

    def _futa(jina):
        os.remove(_guard(jina))
        return True

    def _tengeneza(jina):
        open(_guard(jina), "a", encoding="utf-8").close()
        return jina

    return {
        "soma": NativeFunction("soma", _soma),
        "andika": NativeFunction("andika", _andika),
        "mistari": NativeFunction("mistari", _mistari),
        "ipo": NativeFunction("ipo", _ipo),
        "futa": NativeFunction("futa", _futa),
        "tengeneza": NativeFunction("tengeneza", _tengeneza),
    }


def _umbizo(interp) -> dict:
    import json as _json

    def _kwa_json(value):
        try:
            return _json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise RuntimeErr(
                f"Haiwezi kuumbizwa kuwa JSON: {exc}",
                f"Cannot encode as JSON: {exc}") from None

    def _kutoka_json(text):
        try:
            return _json.loads(text)
        except (TypeError, ValueError) as exc:
            raise RuntimeErr(
                f"Maandishi si JSON sahihi: {exc}",
                f"Invalid JSON: {exc}") from None

    return {
        "kwa_json": NativeFunction("kwa_json", _kwa_json),
        "kutoka_json": NativeFunction("kutoka_json", _kutoka_json),
    }


def _seva(interp) -> dict:
    from ..server import (DEFAULT_HOST, DEFAULT_PORT, ServerApp, jibu,
                          json_response, serve)

    app = getattr(interp, "server_app", None)
    if app is None:
        app = ServerApp(interp)
        interp.server_app = app

    def _njia(mbinu, njia, kazi):
        app.add_route(mbinu, njia, kazi)

    def _anza(mlango=DEFAULT_PORT, mwenyeji=DEFAULT_HOST):
        app.port = int(mlango)
        app.host = str(mwenyeji)
        serve(app)

    return {
        "njia": NativeFunction("njia", _njia),
        "anza": NativeFunction("anza", _anza),
        "jibu": NativeFunction("jibu", jibu),
        "json": NativeFunction("json", json_response),
        "mwenyeji": NativeFunction("mwenyeji", lambda: app.host),
    }


MODULES = {
    "hesabu": _hesabu,
    "orodha_kazi": _orodha_kazi,
    "maneno_kazi": _maneno_kazi,
    "kansa": _kansa,
    "siri": _siri,
    "wakati": _wakati,
    "mfumo": _mfumo,
    "faili": _faili,
    "umbizo": _umbizo,
    "seva": _seva,
}