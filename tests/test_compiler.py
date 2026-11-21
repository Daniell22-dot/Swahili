"""Tests for the bytecode compiler and virtual machine.

Run with:  python -m unittest discover -s tests
"""

import io
import json
import os
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swahili import (Artifact, Interpreter, KiswahiliError, VM, compile_source,
                     disassemble)
from swahili.cli import main
from swahili.compiler.code import (VERSION as BYTECODE_VERSION,
                                   hash_source, output_path_for)


PROGRAMS = {
    "arithmetic": r"""
andika 2 + 3 * 4
andika (2 + 3) * 4
andika 7 / 2
andika 7 // 2
andika 7 % 2
andika 2 ** 8
andika -5 + 3
andika sio kweli
andika 10 na 5
andika 0 au 7
""",
    "control": r"""
namba i = 0
wakati i < 5 {
    i += 1
    kama i == 2 { endelea }
    kama i == 4 { vunja }
    andika f"i={i}"
}
kwa n kwenye 1..4 {
    kama n % 2 == 0 { endelea }
    kama n == 3 { vunja }
    andika f"n={n}"
}
andika chagua(i > 2) { "kubwa" } vingo { "ndogo" }
""",
    "functions": r"""
kazi salamia(jina, salamu = "Habari") {
    rudia salamu + ", " + jina + "!"
}
andika salamia("Amina")
andika salamia("Juma", salamu = "Asalamu")
kazi mkataba(kiwango) {
    rudia kazi(x) { rudia f"{x}/{kiwango}" }
}
andika mkataba(10)(7)
mbili = kazi(x) { rudia x * 2 }
andika mbili(21)
andika hesabia([1, 2, 3, 4], kazi(a, b) { rudia a + b })
""",
    "data": r"""
orodha x = [3, 1, 2]
andika x
andika x[1]
andika x[0:2]
andika pangilia(x)
andika pangamiza(x, kazi(v) { rudia v * 2 })
andika chomoa(x, kazi(v) { rudia v > 1 })
kamusi k = {"a": 1, "b": 2}
k["c"] = 3
andika k
andika k.funguo
andika k.thamani
andika "swahili".pandisha()
jina = k["a"]
andika f"jina={jina} / idadi={idadi(x)}"
""",
    "classes": r"""
darasa Mwalimu {
    jina
    somo
    kazi Mwalimu(jina, somo) {
        mwenyewe.jina = jina
        mwenyewe.somo = somo
    }
    kazi wasilisha() { rudia mwenyewe.jina + " fundisha " + mwenyewe.somo }
}
darasa MwalimuMkuu inarithi Mwalimu {
    kazi wasilisha() { rudia mzazi.wasilisha() + " (mkuu)" }
}
m = tengeneza Mwalimu("Bi Juma", "matematika")
andika m.wasilisha()
mm = tengeneza MwalimuMkuu("Bwana Ali", "kiswahili")
andika mm.wasilisha()
andika mm.jina
andika ainake(m)
""",
    "errors": r"""
kazi hatari(n) {
    kama n > 2 { tupa "kubwa mno" }
    rudia 10 / n
}
jaribu {
    andika hatari(1)
    andika hatari(9)
} kosa k {
    andika "Kosa: " + k
} mwisho {
    andika "-- mwisho --"
}
andika "baada"
""",
    "modules": r"""
tumia hesabu
andika hesabu.kokotoa(144)
andika hesabu.jumla([1, 2, 3, 4])
tumia umbizo
data = umbizo.kutoka_json("{\"jina\": \"Amina\"}")
andika data["jina"]
""",
}


def interpret(source: str, **kwargs) -> str:
    buffer = io.StringIO()
    engine = Interpreter(**kwargs)
    with redirect_stdout(buffer):
        engine.run_source(source, "test.kisw")
    return buffer.getvalue()


def execute(source: str, **kwargs) -> str:
    buffer = io.StringIO()
    engine = VM(**kwargs)
    with redirect_stdout(buffer):
        engine.run_source(source, "test.kisw")
    return buffer.getvalue()


class CompilerVmTests(unittest.TestCase):
    def test_parity_with_reference_interpreter(self):
        for name, source in PROGRAMS.items():
            with self.subTest(program=name):
                self.assertEqual(execute(source), interpret(source))

    def test_bytecode_artifact_round_trip(self):
        source = PROGRAMS["classes"]
        artifact = Artifact(1, "test.kisw", source, compile_source(source,
                                                                  "test.kisw"))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "darasa.kiswc")
            artifact.save(path)
            loaded = Artifact.load(path)
            self.assertEqual(loaded.source, source)
            self.assertEqual(loaded.code.constants[0].__class__.__name__,
                             "ClassSpec")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                VM().run_artifact(loaded)
            self.assertEqual(buffer.getvalue(), interpret(source))

    def test_disassembler_shows_nested_functions(self):
        listing = disassemble(compile_source(PROGRAMS["functions"],
                                             "test.kisw"))
        self.assertIn("CALL_FUNCTION", listing)
        self.assertIn("MAKE_FUNCTION", listing)
        self.assertIn("RETURN_VALUE", listing)
        self.assertIn("<kazi>", listing)

    def test_error_messages_match_interpreter(self):
        source = 'andika jina_isiyokuwepo\n'
        failures = []
        for engine in (Interpreter, VM):
            with self.assertRaises(KiswahiliError) as caught:
                engine().run_source(source, "test.kisw")
            failures.append(caught.exception.swahili)
        self.assertEqual(failures[0], failures[1])

    def test_step_budget_applies_to_vm(self):
        source = "wakati kweli { }"
        with self.assertRaises(KiswahiliError):
            execute(source, max_steps=50, max_seconds=None)

    def test_cli_compile_and_run_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            program = os.path.join(folder, "prog.kisw")
            with open(program, "w", encoding="utf-8") as handle:
                handle.write('andika "kutoka bytecode"\n')
            out = output_path_for(program)
            compile_buffer = io.StringIO()
            with redirect_stdout(compile_buffer):
                self.assertEqual(main(["--compile", program]), 0)
            self.assertTrue(os.path.isfile(out))
            self.assertIn("kiswc", compile_buffer.getvalue())

            run_buffer = io.StringIO()
            with redirect_stdout(run_buffer):
                self.assertEqual(main(["--run-bytecode", out]), 0)
            self.assertEqual(run_buffer.getvalue(), "kutoka bytecode\n")

    def test_cli_engine_flag(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(
                main(["--engine", "vm", "-c", 'andika "vm cli"']), 0)
        self.assertEqual(buffer.getvalue(), "vm cli\n")


    def test_expression_spans_reach_vm_errors(self):
        source = "\n\nandika jina_isiyokuwepo\n"
        with self.assertRaises(KiswahiliError) as caught:
            VM().run_source(source, "span.kisw")
        error = caught.exception
        self.assertEqual(error.line, 3)
        self.assertEqual(error.index, source.index("jina_isiyokuwepo"))

    def test_artifact_v2_validates_source_hash_and_migrates_v1(self):
        source = 'andika "habari"\n'
        artifact = Artifact(1, "t.kisw", source,
                            compile_source(source, "t.kisw"))
        data = artifact.to_dict()
        self.assertEqual(data["version"], BYTECODE_VERSION)
        self.assertEqual(data["source_hash"], hash_source(source))

        legacy = dict(data)
        legacy["version"] = 1
        legacy.pop("source_hash")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "legacy.kiswc")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(legacy))
            loaded = Artifact.load(path)
            self.assertEqual(loaded.version, BYTECODE_VERSION)
            self.assertEqual(loaded.source_hash, hash_source(source))

        bad = loaded.to_dict()
        bad["source_hash"] = "0" * 64
        with self.assertRaises(ValueError):
            Artifact.from_dict(bad)

    def test_vm_caches_imported_modules_and_revalidates(self):
        with tempfile.TemporaryDirectory() as folder:
            module = os.path.join(folder, "hesabu_local.kisw")
            cache = output_path_for(module)

            def write_module(factor: int) -> None:
                with open(module, "w", encoding="utf-8") as handle:
                    handle.write(f"kazi mbili(x) {{ rudia x * {factor} }}\n")

            source = ("tumia hesabu_local\n"
                      "andika hesabu_local.mbili(21)\n")
            write_module(2)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                VM(search_paths=[folder]).run_source(source, "main.kisw")
            self.assertEqual(buffer.getvalue(), "42\n")
            self.assertTrue(os.path.isfile(cache))

            write_module(3)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                VM(search_paths=[folder]).run_source(source, "main.kisw")
            self.assertEqual(buffer.getvalue(), "63\n")

            with open(cache, "wb") as handle:
                handle.write(b"garbage")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                VM(search_paths=[folder]).run_source(source, "main.kisw")
            self.assertEqual(buffer.getvalue(), "63\n")

            os.remove(cache)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                VM(search_paths=[folder],
                   bytecode_cache=False).run_source(source, "main.kisw")
            self.assertEqual(buffer.getvalue(), "63\n")
            self.assertFalse(os.path.isfile(cache))

    def test_differential_fuzz_against_interpreter(self):
        rng = random.Random(20261121)
        for case in range(25):
            lines = []
            for _ in range(6):
                left = rng.randint(0, 20)
                right = rng.randint(1, 9)
                op = rng.choice(("+", "-", "*", "//", "%"))
                lines.append(f"andika {left} {op} {right}")
            if rng.random() < 0.5:
                lines.append("kazi f(x) { rudia x * 2 }")
                lines.append(f"andika f({rng.randint(0, 9)})")
            source = "\n".join(lines) + "\n"
            with self.subTest(case=case):
                self.assertEqual(execute(source), interpret(source))


if __name__ == "__main__":
    unittest.main(verbosity=2)
