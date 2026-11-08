# Kiswahili

**Kiswahili** is a general-purpose programming language whose syntax is
Kiswahili (Swahili). It has a hand-written lexer, a Pratt parser, a
tree-walking interpreter, a standard library, and an interactive REPL — all
written in dependency-free Python.

```
andika "Habari yako, Dunia!"
```

## Quick start

Requirements: Python 3.10 or newer. No third-party packages.

```powershell
# run a program
python -m swahili examples/karibu.kisw

# run one line
python -m swahili -c 'andika "Habari"'

# start the interactive REPL
python -m swahili
```

Programs use the `.kisw` extension.

## A taste of the language

```kiswahili
# variables and types
namba salamu = 3
desimali bei = 1500.50
maneno jina = "Dunia"

# functions and closures
kazi salimia(jina, salamu = "Habari") {
    rudia salamu + ", " + jina + "!"
}
andika salimia("Amina")

# lists and iteration
orodha matunda = ["apeti", "tufaha", "zanzibar"]
kila tunda kwenye matunda {
    andika tunda
}

# classes
darasa Mwalimu {
    jina
    somo

    kazi Mwalimu(jina, somo) {
        mwenyewe.jina = jina
        mwenyewe.somo = somo
    }

    kazi wasilisha() {
        rudia mwenyewe.jina + " fundisha " + mwenyewe.somo
    }
}

m = tengeneza Mwalimu("Bi Juma", "matematika")
andika m.wasilisha()

# inheritance
darasa MwalimuMkuu inarithi Mwalimu {
    kazi wasilisha() { rudia mzazi.wasilisha() + " (mkuu)" }
}

# errors
jaribu {
    tupa "kitu kimeharibika"
} kosa k {
    andika "Kosa: " + k
} mwisho {
    andika "mwisho"
}

# modules
tumia hesabu
andika hesabu.kokotoa(144)
```

See `examples/karibu.kisw` for a tour of every feature, and
[`docs/spec.md`](docs/spec.md) for the reference.

## Keywords at a glance

| Kiswahili | English | | Kiswahili | English |
|-----------|---------|-|-----------|---------|
| `kweli` / `sikweli` | true / false | | `kama` / `vingo` | if / else |
| `wakati` | while | | `kwa` / `kwenye` | for / in |
| `kila` | each | | `rudia` | return |
| `vunja` / `endelea` | break / continue | | `kazi` | function |
| `darasa` | class | | `tengeneza` | new |
| `mwenyewe` | self | | `tumia` | import |
| `inarithi` / `mzazi` | extends / super | | | |
| `jaribu` / `kosa` / `mwisho` | try / except / finally | | `tupa` | throw |
| `namba` / `desimali` / `maneno` | int / float / string | | `orodha` / `kamusi` | list / dict |
| `hali` / `hakuna` | bool / null | | `na` / `au` / `sio` | and / or / not |

## Built-in functions

`andika` (print), `ondoa` (input), `idadi` (length/count), `ainake` (type
name), `namba`, `desimali`, `maneno`, `hali`, `orodha`, `kamusi`, `kipeano`
(range), `ondoka` (exit), plus higher-order helpers `pangilia`, `panga`,
`pangamiza` (map), `chomoa` (filter), `hesabia` (reduce), `pinganya`
(shuffle), `yoyote` (any), `zote` (all).

## Standard library

Load a module with `tumia <jina>`, or import a specific file with a quoted
path (`tumia "zana/zana.kisw" [kama jina]`):

| Module | Purpose |
|--------|---------|
| `hesabu` | maths (sqrt, round, sum, trig, logs, constants) |
| `orodha_kazi` | extra list tools (sort, map, filter, shuffle) |
| `maneno_kazi` | extra string tools |
| `kansa` | randomness (not cryptographically secure) |
| `siri` | cryptographic randomness (`secrets`) |
| `wakati` | time and dates |
| `mfumo` | system and environment |
| `faili` | file reading and writing |

Built-in modules always win over local files, and only the program's own
directory plus any `--path DIR` entries are searched (never the current
working directory). Run untrusted code with `--sandbox`; add `--allow-fs DIR`
to permit `faili` inside a specific directory while `mfumo` stays blocked.
Step, collection/repetition, and output budgets are on by default and can be
tuned with `--max-steps`, `--max-collection`, and `--max-output`.

## Project layout

```
swahili/            the interpreter package
  frontend/         source code -> syntax tree
    lexer.py        source text -> tokens
    parser.py       tokens -> AST (Pratt parser)
    ast.py          AST node definitions
  runtime/          evaluating the tree
    values.py       values, environments, classes
    interpreter.py  tree-walking evaluator
  library/          the standard library
    builtins.py     global built-ins and value methods
    modules.py      importable modules (`tumia`)
  errors.py         bilingual error types and reporting
  cli.py            command-line entry point / REPL
examples/           sample .kisw programs
tests/              unittest suite
docs/               language reference, tutorial, security notes
SECURITY.md         security policy and threat model summary
```

## Development

Run the test suite:

```powershell
$env:PYTHONPATH="."
python -m unittest discover -s tests
```

## Documentation

- [`docs/tutorial.md`](docs/tutorial.md) — step-by-step introduction
- [`docs/spec.md`](docs/spec.md) — language reference
- [`docs/architecture.md`](docs/architecture.md) — how the interpreter is built
- [`docs/security/threat-model.md`](docs/security/threat-model.md) — threats and hardening
- [`docs/security/sandbox.md`](docs/security/sandbox.md) — running untrusted code
- [`SECURITY.md`](SECURITY.md) — security policy

## Status

Kiswahili is an early-stage project (v0.1). The core language, standard
library, examples, and tests are in place. Expect rough edges and ongoing
change.

## License

MIT. See [`LICENSE`](LICENSE).
