# Kiswahili Tutorial

A hands-on introduction to Kiswahili. Run each snippet by saving it to a
`.kisw` file and executing:

```powershell
python -m swahili file.kisw
```

or use the REPL:

```powershell
python -m swahili
```

Throughout, Kiswahili keywords are shown with their English meaning in
comments.

## 1. Saying hello

```kiswahili
andika "Habari yako, Dunia!"
```

`andika` means *print*. You can print several values at once; they are
separated by a space:

```kiswahili
andika "Jumla ni" 2 + 3
```

## 2. Variables

Assign a name to a value:

```kiswahili
jina = "Amina"
umri = 21
andika jina
andika umri
```

You can optionally write the type before the name. This documents intent:

```kiswahili
namba salamu = 3
desimali bei = 1500.50
maneno ujumbe = "habari"
```

## 3. Numbers and arithmetic

```kiswahili
andika 10 + 5        # 15
andika 10 - 3        # 7
andika 10 * 5        # 50
andika 10 / 3        # 3.3333333333333335
andika 10 // 3       # 3   (floor division)
andika 10 % 3        # 1
andika 2 ** 10       # 1024
```

`/` always gives a decimal; use `//` when you want a whole number.

## 4. Strings and interpolation

```kiswahili
jina = "Dunia"
andika "Habari, " + jina + "!"
andika f"Habari, {jina}!"
```

The `f"..."` form is an f-string: anything inside `{ }` is evaluated and
inserted. Escape sequences such as `\n` and `\t` are supported.

## 5. Conditions

```kiswahili
alama = 85

kama alama >= 90 {
    andika "Daraja A"
} vingo kama alama >= 80 {
    andika "Daraja B"
} vingo {
    andika "Daraja C"
}
```

Comparative operators: `==`, `!=`, `<`, `<=`, `>`, `>=`. Logical operators
are written as words: `na` (and), `au` (or), `sio` (not).

## 6. Loops

```kiswahili
namba i = 0
wakati i < 3 {
    andika f"i = {i}"
    i += 1
}

kwa n kwenye 1..4 {
    andika n          # 1, 2, 3
}
```

`a..b` is a range that stops before `b`. Use `vunja` to break and `endelea`
to continue.

To walk a list:

```kiswahili
orodha matunda = ["apeti", "tufaha", "zanzibar"]
kila tunda kwenye matunda {
    andika tunda
}
```

## 7. Lists

```kiswahili
orodha xs = [1, 2, 3]
andika xs[0]        # 1
andika xs[-1]       # 3
xs.ongeza(4)        # append
andika idadi(xs)    # 4
andika xs[1:3]      # [2, 3]
```

## 8. Dictionaries

```kiswahili
kamusi miji = {"Mombasa": 1_200_000, "Dodoma": 400_000}
andika miji["Dodoma"]
miji["Kisumu"] = 337_000
kama miji.ina("Kisumu") {
    andika "Kisumu iko!"
}
```

## 9. Functions

```kiswahili
kazi salimia(jina, salamu = "Habari") {
    rudia salamu + ", " + jina + "!"
}

andika salimia("Amina")
andika salimia("Juma", "Mambo")
```

Functions can call themselves:

```kiswahili
kazi fibo(n) {
    kama n < 2 { rudia n }
    rudia fibo(n - 1) + fibo(n - 2)
}
andika fibo(12)
```

Functions are values, so they can be passed around and returned:

```kiswahili
kazi ongeza_kiasi(kiasi) {
    rudia kazi(x) { rudia x + kiasi }
}
ongeza_kumi = ongeza_kiasi(10)
andika ongeza_kumi(7)     # 17
```

## 10. Classes

```kiswahili
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
```

- Fields are listed by name in the class body.
- The constructor is a method with the same name as the class.
- Use `mwenyewe` to refer to the current instance.

## 11. Error handling

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
    andika "-- mwisho --"
}
```

`tupa` raises an error. `kosa` catches it and binds the value; `mwisho` always
runs.

## 12. Modules

```kiswahili
tumia hesabu
andika hesabu.kokotoa(144)      # 12.0
andika hesabu.jumla([1, 2, 3])  # 6

tumia kansa
andika kansa.namba(1, 100)
```

Available modules: `hesabu`, `orodha_kazi`, `maneno_kazi`, `kansa`, `siri`,
`wakati`, `mfumo`, `faili`.

Use `siri` for anything security-sensitive (tokens, keys, nonces); `kansa` is
predictable and only suitable for games and tests.

## 13. Where to go next

- Read `examples/karibu.kisw` for a complete feature tour.
- Read `docs/spec.md` for the precise reference.
- Try writing a small program: a number-guessing game, a to-do list, or a
  text report from a file using `faili`.
