"""Kariakari — command line entry point.

    python -m swahili programu.kisw     run a file
    python -m swahili                    start the REPL
    python -m swahili -i                 same
    python -m swahili -c 'andika "Habari"'
"""

from __future__ import annotations

import argparse
import os
import sys

from .errors import KiswahiliError, Kosa, TupaImbali
from .interpreter import Interpreter
from .runtime import Environment, display

VERSION = "0.1.0"
EXTENSION = ".kisw"

BANNER = """\
╔══════════════════════════════════════════════════════════╗
║  KISWAHILI  v%s                                      ║
║  Programu inayozungumza Kiswahili.                      ║
║  Type `kusaidia` for help, `ondoka` to leave.            ║
╚══════════════════════════════════════════════════════════╝"""

HELP = """\
Kusaidia / help
  andika "habari"            andika angalia kitu
  kazi jina(x) { ... }       define a function
  darasa Jina { ... }        define a class
  kati                       break into the debugger
  msaada                    clear all variables
  orodha, kamusi             wrap values: orodha(1, 2, 3)
  pamoja ...                 print many lines at once
  ondoka                     exit
"""

ALIASES = {
    "kusaidia": "help", "msaada": "clear", "ondoa": "exit", "kutoka": "exit",
    "clear": "clear", "exit": "exit", "help": "help", "quit": "exit",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="swahili",
        description="Kiswahili — a programming language in Kiswahili.",
        add_help=False,
    )
    parser.add_argument("faili", nargs="?", help="program file to run")
    parser.add_argument("-c", "--code", help="run a line of Kiswahili")
    parser.add_argument("-i", "--interaktif", action="store_true",
                        help="start the interactive REPL")
    parser.add_argument("-v", "--version", action="version",
                        version=f"swahili {VERSION}")
    parser.add_argument("-h", "--help", action="help", help=__doc__)
    args = parser.parse_args(argv)

    search_paths: list[str] = []
    if args.faili:
        search_paths.append(os.path.dirname(os.path.abspath(args.faili)))

    interpreter = Interpreter(repl_hook=None, search_paths=search_paths)
    interpreter.repl_hook = lambda env: repl_loop(interpreter, env, quiet=True)

    try:
        if args.code:
            interpreter.run_source(args.code, "<kando>")
            return 0
        if args.faili:
            return run_file(interpreter, args.faili)
        repl_loop(interpreter, interpreter.globals)
        return 0
    except KiswahiliError as exc:
        sys.stderr.write(exc.render() + "\n")
        return 1
    except TupaImbali as exc:
        sys.stderr.write(f"\nKosa: {display(exc.args[0])}\n")
        return 1
    except SystemExit as exc:
        return int(exc.code or 0)
    except RecursionError:
        sys.stderr.write("\nKosa: mzunguko mrefu sana (recursion) —\n"
                         "Error: recursion went too deep.\n")
        return 1


def run_file(interpreter: Interpreter, path: str) -> int:
    if not os.path.isfile(path):
        sys.stderr.write(f"Hakuna faili: {path}\nNo such file: {path}\n")
        return 1
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    interpreter.run_source(source, os.path.abspath(path))
    return 0


def repl_loop(interpreter: Interpreter, env: Environment, quiet: bool = False) -> None:
    if not quiet:
        print(BANNER % VERSION)

    buffer: list[str] = []

    def flush() -> bool:
        if not buffer:
            return True
        source = "\n".join(buffer)
        buffer.clear()
        if not source.strip():
            return True
        first = source.split("\n")[0].strip()
        if first in ALIASES:
            action = ALIASES[first]
            if action == "help":
                print(HELP)
                return True
            if action == "clear":
                env.vars.clear()
                print("Kibafya. / Cleared.")
                return True
            if action == "exit":
                raise SystemExit(0)
        try:
            interpreter.run_source(source, "<mazungumzo>")
        except KiswahiliError as exc:
            sys.stderr.write(exc.render() + "\n")
        except TupaImbali as exc:
            sys.stderr.write(f"Kosa: {display(exc.args[0])}\n")
        except SystemExit:
            raise
        except RecursionError:
            sys.stderr.write("Kosa: mzunguko mrefu sana.\n")
        return True

    while True:
        prompt = "... " if buffer else "kiswahili> "
        try:
            line = input(prompt)
        except EOFError:
            print("\nKwaheri! / Goodbye!")
            return
        except KeyboardInterrupt:
            buffer.clear()
            print("(katizwa / interrupted)")
            continue

        stripped = line.strip()
        if not buffer and stripped in ("", "pamoja", "kasa"):
            if stripped == "kasa":
                buffer.clear()
                continue
        buffer.append(line)
        if _balanced("\n".join(buffer)):
            flush()


def _balanced(source: str) -> bool:
    """A statement is ready once braces/brackets/parens all close."""
    depth = 0
    in_string = False
    escaped = False
    for ch in source:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
    return depth <= 0 and not in_string


if __name__ == "__main__":
    raise SystemExit(main())