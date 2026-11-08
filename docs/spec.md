# Kiswahili — Language Reference

This document describes the syntax and semantics of the Kiswahili language as
implemented in v0.1. Kiswahili is dynamically typed and executed by a
tree-walking interpreter.

## 1. Source files

- Program files use the extension `.kisw` and are UTF-8 text.
- Statements are separated by newlines or `;`.
- A newline does **not** end a statement when it follows an operator, a comma,
  a dot, an opening bracket, or a block keyword. This allows expressions to
  wrap across lines.
- Comments start with `#` and run to the end of the line.

## 2. Values and types

Kiswahili is dynamically typed. The built-in types are:

| Type | Kiswahili name | Literal examples |
|------|----------------|------------------|
| integer | `namba` | `0`, `42`, `1_000_000` |
| floating point | `desimali` | `3.14`, `1.5e3` |
| string | `maneno` | `"habari"`, `'jambo'` |
| boolean | `hali` | `kweli`, `sikweli` |
| null | `hakuna` | `hakuna` |
| list | `orodha` | `[1, 2, 3]` |
| dictionary | `kamusi` | `{"a": 1}` |
| function | `kazi` | `kazi(x) { rudia x }` |
| instance | `mwanafunzi` | `tengeneza Darasa()` |
| class | `darasa` | `darasa Jina { }` |

`ainake(value)` returns the Kiswahili type name of a value.

### Truthiness

`sikweli`, `hakuna`, `0`, `0.0`, `""`, and empty collections are falsy.
Everything else is truthy.

## 3. Variables and declarations

```kiswahili
jina = "Dunia"          # assignment
namba salamu = 3        # typed declaration
desimali bei = 1500.50
maneno ujumbe = "habari"
orodha rangi = ["nyekundu", "bluu"]
kamusi mji = {"jina": "Dodoma"}
```

Type names may optionally precede a declaration. Type annotations do not
enforce anything at runtime in v0.1; they document intent.

Assignment targets may be a name, a member (`kitu.sifa`), or an index
(`orodha[0]`).

## 4. Operators

From lowest to highest precedence:

| Operators | Meaning |
|-----------|---------|
| `au` | logical or |
| `na` | logical and |
| `==` `!=` `<` `<=` `>` `>=` | comparisons |
| `iko` | membership (`x iko orodha`) |
| `ni` | identity (`x ni y`) |
| `+` `-` | addition, subtraction |
| `*` `/` `//` `%` | multiplication, division, floor division, modulus |
| `**` | exponentiation |
| `sio` | logical not (prefix) |
| `-` | negation (prefix) |

Notes:

- `/` always produces a `desimali`; use `//` for floor division.
- `+` is strict: both operands must be numbers, both strings, or both lists.
  Mixing a string and a number is an error.
- `==` distinguishes booleans from numbers (`kweli == 1` is false).
- `*` repeats a string when one operand is a string and the other an integer.

## 5. Strings

```kiswahili
andika "Habari\nDunia"          # \n, \t, \r, \\, \", \',
                                # \0 are understood
andika "Habari yako, " + jina
andika f"Jumla: {1 + 2}"        # f-string interpolation
```

Slicing uses `[start:stop]` and negative indices are supported.

## 6. Collections

### Lists

```kiswahili
orodha xs = [1, 2, 3]
xs[0]            # 1
xs[-1]           # 3
xs[0:2]          # [1, 2]
idadi(xs)        # 3
xs.idadi         # 3 (property form)
xs.ongeza(4)     # append
```

### Dictionaries

```kiswahili
kamusi miji = {"Mombasa": 1_200_000, "Dodoma": 400_000}
miji["Dodoma"]      # 400000
miji["Kisumu"] = 337_000
miji.funguo         # keys
miji.thamani        # values
miji.ina("Kisumu")  # true
```

### Ranges

`a..b` is a half-open range: it includes `a` but excludes `b`.

```kiswahili
kwa n kwenye 0..3 { andika n }   # 0, 1, 2
```

## 7. Control flow

```kiswahili
kama alama >= 90 {
    andika "A"
} vingo kama alama >= 80 {
    andika "B"
} vingo {
    andika "C"
}

wakati i < 10 {
    i += 1
}

kwa n kwenye 0..10 { andika n }      # iterate a range
kila tunda kwenye matunda {           # iterate a collection
    andika tunda
}

kama n == 3 { vunja }                 # break
kama n % 2 == 0 { endelea }           # continue

andika chagua(i > 2) { "kubwa" } vingo { "ndogo" }   # ternary
```

## 8. Functions

```kiswahili
kazi salimia(jina, salamu = "Habari", alama = "!") {
    rudia salamu + ", " + jina + alama
}

andika salimia("Amina")                 # Habari, Amina!
andika salimia("Juma", "Mambo")         # Mambo, Juma!

# anonymous function
kazi(x) { rudia x * 2 }
```

Functions are first-class values and close over their defining scope:

```kiswahili
kazi mkataba(kiwango) {
    rudia kazi(x) { rudia x + kiwango }
}
ongeza = mkataba(10)
andika ongeza(7)      # 17
```

Space-separated call syntax is allowed at the start of a statement:

```kiswahili
andika "habari"
ondoa "Jina lako? "
```

## 9. Classes

```kiswahili
darasa Mwalimu {
    jina                # field (defaults to hakuna)
    somo

    kazi Mwalimu(jina, somo) {     # constructor: same name as the class
        mwenyewe.jina = jina
        mwenyewe.somo = somo
    }

    kazi wasilisha() {
        rudia mwenyewe.jina + " fundisha " + mwenyewe.somo
    }
}

m = tengeneza Mwalimu("Bi Juma", "matematika")
andika m.wasilisha()
andika m.jina
```

- Fields are declared by name inside the class body.
- Methods are functions declared inside the class body and receive the
  instance through `mwenyewe`.
- `tengeneza Darasa(...)` creates an instance; `ainake(instance)` is
  `mwanafunzi`.

### Inheritance

```kiswahili
darasa Mnyama {
    jina
    kazi Mnyama(jina) { mwenyewe.jina = jina }
    kazi sema() { rudia "Mimi ni " + mwenyewe.jina }
}

darasa Mbwa inarithi Mnyama {
    kazi Mbwa(jina) { mzazi.Mnyama(jina) }
    kazi sema() { rudia mzazi.sema() + " (mbwa)" }
}

andika (tengeneza Mbwa("Rex")).sema()   # Mimi ni Rex (mbwa)
```

- `darasa B inarithi A { }` makes `B` inherit `A`'s fields, methods, and
  constructor when `B` does not declare its own.
- `mzazi` is available inside methods and points at the parent class; use
  `mzazi.jina_la_kazi(...)` to call an overridden method (including the
  constructor).
- A method in the subclass overrides a method with the same name in the
  parent.

## 10. Errors

```kiswahili
kazi sali(idadi) {
    kama idadi > 3 { tupa "IDADI kubwa mno!" }
    rudia 100 / idadi
}

jaribu {
    andika sali(9)
} kosa k {
    andika "Kosa: " + k
} mwisho {
    andika "mwisho"
}
```

`tupa value` raises an error carrying `value`; `kosa name { }` catches it and
binds the value to `name`. `mwisho { }` always runs.

## 11. Modules

```kiswahili
tumia hesabu
andika hesabu.kokotoa(144)      # 12.0

tumia orodha_kazi kama or
andika or.pangilia([3, 1, 2])   # [1, 2, 3]
```

Modules are resolved deterministically: built-in modules are considered first,
then `<jina>.kisw` in the program's own directory, in a `moduli/`
subdirectory, and in directories added with `--path DIR`. The current working
directory is never searched implicitly. This prevents a local file from
shadowing a trusted standard module.

```powershell
python -m swahili --path ./lib program.kisw
```

Capability flags for untrusted code:

| Flag | Effect |
|------|--------|
| `--sandbox` | refuse `faili` and `mfumo` |
| `--allow-fs DIR` | allow `faili` only inside `DIR` (repeatable); with `--sandbox`, `mfumo` stays blocked |
| `--path DIR` | add `DIR` to the module search path |
| `--max-steps N` | abort after `N` executed nodes (default 10,000,000) |
| `--max-collection N` | cap ranges/repetition at `N` elements (default 1,000,000) |
| `--max-output N` | cap printed output at `N` characters (default 10,000,000) |

### Standard library

| Module | Contents |
|--------|----------|
| `hesabu` | `pi`, `e`, `kokotoa` (sqrt), `kadiria` (round), `jumla`, `zidisha`, `jumlisha`, `kipeano`, `hiki` (floor), `hapa` (ceil), `sinu`, `kosi`, `tana`, `logariti`, `eksa` |
| `orodha_kazi` | `pangilia`, `panga`, `pangamiza`, `chomoa`, `pinganya`, `hakika` |
| `maneno_kazi` | extra string helpers |
| `kansa` | random helpers (not cryptographically secure) |
| `siri` | `tokeni` (hex token), `baiti`, `namba`, `chagua`, `linganisha` (constant-time compare) |
| `wakati` | time and dates |
| `mfumo` | system and environment |
| `faili` | file reading and writing |

## 12. Built-in functions

| Function | Purpose |
|----------|---------|
| `andika` | print values |
| `ondoa` | read a line of input |
| `idadi` | length / element count |
| `ainake` | type name |
| `namba`, `desimali`, `maneno`, `hali` | conversions |
| `orodha`, `kamusi` | construct collections |
| `kipeano` | range of integers |
| `ondoka` | exit the program |
| `pangilia` | sort a list |
| `panga` | sort with a key function |
| `pangamiza` | map |
| `chomoa` | filter |
| `hesabia` | reduce / fold |
| `pinganya` | shuffle |
| `yoyote` | true if any element matches |
| `zote` | true if all elements match |

## 13. Errors and diagnostics

Runtime errors are reported in Kiswahili first and English second, with the
source line and a caret pointing at the relevant position. Recursion is
limited to 200 nested calls by default.
