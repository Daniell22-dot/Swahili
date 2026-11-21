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

from .compiler.code import (VERSION as BYTECODE_VERSION, Artifact,
                            disassemble, output_path_for)
from .compiler.compiler import compile_source
from .errors import KiswahiliError, Kosa, TupaImbali
from .runtime import Environment, Interpreter, VM, display

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
    parser.add_argument("--engine", choices=("interpreter", "vm"),
                        default="interpreter",
                        help="execution engine (default: interpreter)")
    parser.add_argument("--compile", action="store_true",
                        help="compile the program to a .kiswc artifact")
    parser.add_argument("-o", "--out", metavar="FILE",
                        help="output path for --compile")
    parser.add_argument("--run-bytecode", metavar="FILE",
                        help="run a compiled .kiswc artifact")
    parser.add_argument("--disassemble", metavar="FILE",
                        help="print the instructions in a .kiswc artifact")
    parser.add_argument("--no-bytecode-cache", dest="bytecode_cache",
                        action="store_false", default=True,
                        help="do not create or use cached .kiswc module artifacts")
    parser.add_argument("--sandbox", action="store_true",
                        help="block host-access modules (faili, mfumo)")
    parser.add_argument("--allow-fs", action="append", metavar="DIR",
                        help="confine `faili` to DIR (repeatable; "
                             "combine with --sandbox to allow only DIR)")
    parser.add_argument("--allow-env", action="append", metavar="NAME",
                        help="let `mfumo.mazingira` read only NAME "
                             "(repeatable; enables env access under --sandbox)")
    parser.add_argument("--path", action="append", metavar="DIR", default=[],
                        help="add a directory to the module search path")
    parser.add_argument("--max-steps", type=int, default=None, metavar="N",
                        help="abort after N executed nodes")
    parser.add_argument("--max-collection", type=int, default=None, metavar="N",
                        help="cap range/repetition size at N elements")
    parser.add_argument("--max-output", type=int, default=None, metavar="N",
                        help="cap printed output at N characters")
    parser.add_argument("--max-seconds", type=float, default=None, metavar="S",
                        help="abort after S seconds of wall-clock time")
    parser.add_argument("-h", "--help", action="help", help=__doc__)
    args = parser.parse_args(argv)

    search_paths: list[str] = []
    if args.faili:
        search_paths.append(os.path.dirname(os.path.abspath(args.faili)))
    search_paths.extend(args.path)

    limits = {}
    if args.max_steps is not None:
        limits["max_steps"] = args.max_steps
    if args.max_collection is not None:
        limits["max_collection"] = args.max_collection
    if args.max_output is not None:
        limits["max_output"] = args.max_output
    if args.max_seconds is not None:
        limits["max_seconds"] = args.max_seconds

    def make_engine(engine_cls, paths: list[str] | None = None):
        options = dict(limits)
        if engine_cls is VM:
            options["bytecode_cache"] = args.bytecode_cache
        engine = engine_cls(repl_hook=None,
                            search_paths=paths if paths is not None
                            else search_paths,
                            sandbox=args.sandbox, allowed_fs=args.allow_fs,
                            allowed_env=args.allow_env, **options)
        engine.repl_hook = lambda env: repl_loop(engine, env, quiet=True)
        return engine

    try:
        if args.disassemble:
            artifact = Artifact.load(args.disassemble)
            sys.stdout.write(disassemble(artifact.code))
            return 0

        if args.run_bytecode:
            artifact = Artifact.load(args.run_bytecode)
            artifact_paths = list(args.path)
            if artifact.filename and not artifact.filename.startswith("<"):
                artifact_paths.insert(
                    0, os.path.dirname(os.path.abspath(artifact.filename)))
            engine = make_engine(VM, artifact_paths)
            engine.run_artifact(artifact)
            return 0

        if args.compile:
            if args.code:
                source = args.code
                filename = "<kando>"
                out = args.out or "programu.kiswc"
            elif args.faili:
                with open(args.faili, "r", encoding="utf-8") as handle:
                    source = handle.read()
                filename = os.path.abspath(args.faili)
                out = output_path_for(args.faili, args.out)
            else:
                sys.stderr.write("Andika programu au taja faili. / "
                                 "Give code or a file to compile.\n")
                return 1
            artifact = Artifact(BYTECODE_VERSION, filename, source,
                                compile_source(source, filename))
            artifact.save(out)
            sys.stdout.write(f"{out}\n")
            return 0

        engine_cls = VM if args.engine == "vm" else Interpreter
        interpreter = make_engine(engine_cls)
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


def compile_main(argv: list[str] | None = None) -> int:
    """Console-script shortcut for `swahili --compile`."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compile" not in arguments:
        arguments.insert(0, "--compile")
    return main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())