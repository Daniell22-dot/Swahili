"""Vijana — tests for Kiswahili. Run with:  python -m unittest discover tests"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swahili import Interpreter, KiswahiliError, tokenize, parse   # noqa: E402


def run(source: str) -> str:
    """Run a Kiswahili program and return everything it printed."""
    buffer = io.StringIO()
    interpreter = Interpreter()
    with redirect_stdout(buffer):
        interpreter.run_source(source, "test.kisw")
    return buffer.getvalue()


def value_of(source: str) -> str:
    """Run a program whose only job is to print, and return that line."""
    return run(source).strip()


class LexerTests(unittest.TestCase):
    def kinds(self, source):
        return [t.type for t in tokenize(source)]

    def test_numbers(self):
        self.assertEqual(value_of("andika 1_000_000"), "1000000")
        self.assertEqual(value_of("andika 3.5"), "3.5")
        self.assertEqual(value_of("andika 1e3"), "1000.0")

    def test_string_escapes(self):
        self.assertEqual(value_of(r'andika "a\tb"'), "a\tb")
        self.assertEqual(value_of(r'andika "salamu"' + "\n"), "salamu")

    def test_comments_are_ignored(self):
        self.assertEqual(value_of("# andika 99\nandika 1"), "1")

    def test_fstring(self):
        self.assertEqual(value_of('x = 5\nandika f"namba {x}"'), "namba 5")

    def test_fstring_with_nested_brackets(self):
        self.assertEqual(value_of('andika f"{[1,2][0]}"'), "1")

    def test_newline_ends_statements(self):
        self.assertEqual(self.kinds("a\nb\n"), ["IDENT", "NEWLINE", "IDENT",
                                               "NEWLINE", "EOF"])

    def test_newline_absorbed_after_operator(self):
        self.assertNotIn("NEWLINE", self.kinds("1 +\n2"))

    def test_unknown_symbol(self):
        with self.assertRaises(KiswahiliError):
            tokenize("andika $")

    def test_unterminated_string(self):
        with self.assertRaises(KiswahiliError):
            tokenize('andika "abc')

    def test_unclosed_interpolation(self):
        with self.assertRaises(KiswahiliError):
            tokenize('andika f"{x"')


class ArithmeticTests(unittest.TestCase):
    def test_integers_stay_integers(self):
        self.assertEqual(value_of("andika 1 + 1"), "2")

    def test_division_gives_desimali(self):
        self.assertEqual(value_of("andika 7 / 2"), "3.5")
        self.assertEqual(value_of("andika 8 / 2"), "4.0")

    def test_floor_division(self):
        self.assertEqual(value_of("andika 7 // 2"), "3")

    def test_modulo(self):
        self.assertEqual(value_of("andika 7 % 3"), "1")

    def test_power_is_right_associative(self):
        self.assertEqual(value_of("andika 2 ** 3 ** 2"), "512")

    def test_precedence(self):
        self.assertEqual(value_of("andika 2 + 3 * 4"), "14")
        self.assertEqual(value_of("andika (2 + 3) * 4"), "20")

    def test_string_repetition(self):
        self.assertEqual(value_of('andika "ab" * 3'), "ababab")

    def test_string_plus_string(self):
        self.assertEqual(value_of('andika "a" + "b"'), "ab")

    def test_string_plus_number_is_an_error(self):
        with self.assertRaises(KiswahiliError):
            run('andika "a" + 1')

    def test_division_by_zero(self):
        with self.assertRaises(KiswahiliError):
            run("andika 1 / 0")

    def test_compound_assignment(self):
        self.assertEqual(value_of("x = 1\nx += 4\nandika x"), "5")
        self.assertEqual(value_of("x = 3\nx **= 2\nandika x"), "9")


class ComparisonTests(unittest.TestCase):
    def test_equality(self):
        self.assertEqual(value_of("andika 1 == 1"), "kweli")
        self.assertEqual(value_of('andika "a" == "b"'), "sikweli")

    def test_hali_is_not_namba(self):
        # `kweli == 1` must be sikweli: types are never conflated
        self.assertEqual(value_of("andika kweli == 1"), "sikweli")

    def test_na_and_au(self):
        self.assertEqual(value_of("andika 1 < 2 na 2 < 3"), "kweli")
        self.assertEqual(value_of("andika 1 > 2 au 2 < 3"), "kweli")

    def test_sio(self):
        self.assertEqual(value_of("andika sio sikweli"), "kweli")

    def test_iko(self):
        self.assertEqual(value_of('andika "a" iko ["a", "b"]'), "kweli")
        self.assertEqual(value_of('andika "z" iko ["a", "b"]'), "sikweli")
        self.assertEqual(value_of('andika "a" iko "abc"'), "kweli")

    def test_ni_is_identity(self):
        self.assertEqual(value_of("andika 3 ni 3"), "kweli")

    def test_na_short_circuits(self):
        # the right side would divide by zero if it were evaluated
        self.assertEqual(value_of("andika sikweli na (1 / 0) > 1"), "sikweli")


class DeclarationTests(unittest.TestCase):
    def test_typed_declaration(self):
        self.assertEqual(value_of("namba x = 5\nandika x"), "5")

    def test_type_mismatch_is_reported(self):
        with self.assertRaises(KiswahiliError):
            run('namba x = "habari"\nandika x')

    def test_namba_is_promoted_to_desimali(self):
        self.assertEqual(value_of("namba x = 5\nandika x / 2"), "2.5")

    def test_ainake(self):
        cases = {"42": "namba", "4.2": "desimali", '"a"': "maneno",
                 "kweli": "hali", "hakuna": "hakuna", "[1]": "orodha",
                 "{}": "kamusi"}
        for literal, expected in cases.items():
            self.assertEqual(value_of(f"andika ainake({literal})"), expected)

    def test_conversions(self):
        self.assertEqual(value_of('andika namba("42")'), "42")
        self.assertEqual(value_of('andika desimali("1.5") * 2'), "3.0")
        self.assertEqual(value_of("andika maneno(42)"), "42")

    def test_unknown_name(self):
        with self.assertRaises(KiswahiliError):
            run("andika haipo")

    def test_name_suggestion(self):
        with self.assertRaises(KiswahiliError) as ctx:
            run("jumla = 1\nandika jumlaa")
        self.assertIn("jumla", str(ctx.exception))


class ControlFlowTests(unittest.TestCase):
    def test_if_else(self):
        source = "x = 5\nkama x > 3 { andika \"n\" } vingo { andika \"ch\" }"
        self.assertEqual(value_of(source), "n")

    def test_else_if_chain(self):
        source = ("x = 85\nkama x >= 90 { andika \"A\" } "
                  "vingo kama x >= 80 { andika \"B\" } vingo { andika \"C\" }")
        self.assertEqual(value_of(source), "B")

    def test_while(self):
        self.assertEqual(value_of("i = 0\nwakati i < 3 { andika i\ni += 1 }"),
                         "0\n1\n2")

    def test_until(self):
        self.assertEqual(value_of("i = 0\nhadi i >= 3 { andika i\ni += 1 }"),
                         "0\n1\n2")

    def test_kila_loops_over_list(self):
        self.assertEqual(value_of('kila x kwenye ["a", "b"] { andika x }'), "a\nb")

    def test_kila_over_range(self):
        self.assertEqual(value_of("kila n kwenye 1..4 { andika n }"),
                         "1\n2\n3")

    def test_vunja_stops_the_loop(self):
        source = ("kwa n kwenye 0..9 { kama n == 3 { vunja }\nandika n }")
        self.assertEqual(value_of(source), "0\n1\n2")

    def test_endelea_skips_the_rest(self):
        source = ("kwa n kwenye 0..5 { kama n % 2 == 0 { endelea }\nandika n }")
        self.assertEqual(value_of(source), "1\n3")

    def test_kila_over_dict_uses_keys(self):
        source = 'kila k kwenye {"a": 1, "b": 2} { andika k }'
        self.assertEqual(value_of(source), "a\nb")

    def test_ternary(self):
        self.assertEqual(value_of('andika chagua(kweli) { "n" } vingo { "ch" }'),
                         "n")


class FunctionTests(unittest.TestCase):
    def test_simple_call(self):
        self.assertEqual(value_of('kazi f() { rudia 5 }\nandika f()'), "5")

    def test_arguments(self):
        self.assertEqual(value_of("kazi f(a, b) { rudia a + b }\nandika f(2, 3)"),
                         "5")

    def test_default_arguments(self):
        source = ('kazi g(a, b = 10) { rudia a + b }\nandika g(1)')
        self.assertEqual(value_of(source), "11")

    def test_keyword_arguments(self):
        source = "kazi g(a, b) { rudia a - b }\nandika g(a = 5, b = 2)"
        self.assertEqual(value_of(source), "3")

    def test_recursion(self):
        source = ("kazi f(n) { kama n < 2 { rudia n }\nrudia f(n-1) + f(n-2) }\n"
                  "andika f(10)")
        self.assertEqual(value_of(source), "55")

    def test_missing_argument(self):
        with self.assertRaises(KiswahiliError):
            run("kazi f(a) { rudia a }\nandika f()")

    def test_too_many_arguments(self):
        with self.assertRaises(KiswahiliError):
            run("kazi f(a) { rudia a }\nandika f(1, 2)")

    def test_closure_captures_environment(self):
        source = ("kazi mkataba(kiwango) { rudia kazi(x) { rudia x + kiwango } }\n"
                  "f = mkataba(10)\nandika f(5)")
        self.assertEqual(value_of(source), "15")

    def test_closures_are_independent(self):
        source = ("kazi mkataba(n) { rudia kazi() { rudia n } }\n"
                  "a = mkataba(1)\nb = mkataba(2)\nandika a()\nandika b()")
        self.assertEqual(value_of(source), "1\n2")

    def test_anonymous_function(self):
        source = 'andika orodha([1,2,3]).pangamiza(kazi(x) { rudia x * 2 })'
        self.assertEqual(value_of(source), "[2, 4, 6]")

    def test_arrow_function(self):
        self.assertEqual(value_of("kazi f(x) => x + 1\nandika f(1)"), "2")

    def test_typed_parameters(self):
        source = "kazi f(namba a, namba b) { rudia a * b }\nandika f(3, 4)"
        self.assertEqual(value_of(source), "12")

    def test_recursion_limit(self):
        with self.assertRaises(KiswahiliError):
            run("kazi f(n) { rudia f(n + 1) }\nandika f(0)")


class ClassTests(unittest.TestCase):
    PROGRAM = """
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
andika m.somo
andika ainake(m)
"""
    def test_constructor_and_methods(self):
        self.assertEqual(value_of(self.PROGRAM),
                         "Bi Juma fundisha matematika\nmatematika\nmwanafunzi")

    def test_fields_default_to_hakuna(self):
        source = ("darasa A { x\nkazi A(x) { mwenyewe.x = x } }\n"
                  "andika tengeneza A(7).x")
        self.assertEqual(value_of(source), "7")

    def test_methods_do_not_leak(self):
        source = ("darasa A { kazi salamu() { rudia 1 } }\nandika ainake(A)")
        self.assertEqual(value_of(source), "darasa")

    def test_unknown_method(self):
        source = "darasa A { kazi A() { } }\nandika tengeneza A().haipo()"
        with self.assertRaises(KiswahiliError):
            run(source)

    def test_constructor_without_constructor_method(self):
        self.assertEqual(value_of("darasa A { x = 1 }\nandika 1"), "1")

    def test_new_needs_a_known_class(self):
        with self.assertRaises(KiswahiliError):
            run("andika tengeneza Haipo()")


class ErrorTests(unittest.TestCase):
    def test_tupa_and_kosa(self):
        source = ('jaribu { tupa "kosa kubwa" } kosa k { andika k }')
        self.assertEqual(value_of(source), "kosa kubwa")

    def test_kosa_without_a_binding(self):
        source = 'jaribu { tupa "x" } kosa { andika "imepigwa" }'
        self.assertEqual(value_of(source), "imepigwa")

    def test_mwisho_always_runs(self):
        source = ('jaribu { tupa "x" } kosa { } mwisho { andika "mwisho" }')
        self.assertEqual(value_of(source), "mwisho")

    def test_uncaught_throw_propagates(self):
        with self.assertRaises(KiswahiliError):
            run('tupa "nje"')

    def test_try_without_catch_or_finally(self):
        with self.assertRaises(KiswahiliError):
            run("jaribu { andika 1 }")


class DataTests(unittest.TestCase):
    def test_list_index_and_length(self):
        self.assertEqual(value_of('o = ["a","b"]\nandika o[1]\nandika o.idadi'),
                         "b\n2")

    def test_negative_index(self):
        self.assertEqual(value_of('andika ["a","b"][-1]'), "b")

    def test_slice(self):
        self.assertEqual(value_of('andika [1,2,3,4][1:3]'), "[2, 3]")

    def test_slice_assignment_target_is_not_a_call(self):
        self.assertEqual(value_of('o = [1,2,3]\no[0] = 9\nandika o[0]'), "9")

    def test_list_index_out_of_range(self):
        with self.assertRaises(KiswahiliError):
            run("andika [1,2][9]")

    def test_list_methods(self):
        cases = {
            "orodha([3,1,2]).pangilia()": "[1, 2, 3]",
            "orodha([1,2]).pindua()": "[2, 1]",
            "orodha([1,2,3]).chomoa(kazi(x) { rudia x > 1 })": "[2, 3]",
            "orodha([1,2,3]).pangamiza(kazi(x) { rudia x + 1 })": "[2, 3, 4]",
            "orodha([1,2]).hesabia(kazi(a,b) { rudia a + b }, 0)": "3",
            "orodha([1,2]).fanya(2)": "[1, 2, 1, 2]",
            "orodha([1,2]).jumlisha()": "3",
            "orodha([[1],[2]]).flatu()": "[1, 2]",
            "orodha([1,2]).ina(2)": "kweli",
            "orodha([1,2]).tafuta(2)": "1",
        }
        for expression, expected in cases.items():
            self.assertEqual(value_of(f"andika {expression}"), expected)

    def test_dict_basics(self):
        source = ('k = {"a": 1}\nk["b"] = 2\nandika k["b"]\nandika k.idadi\n'
                  'andika k.funguo')
        self.assertEqual(value_of(source), '2\n2\n["a", "b"]')

    def test_dict_missing_key(self):
        with self.assertRaises(KiswahiliError):
            run('andika {"a": 1}["z"]')

    def test_string_methods(self):
        cases = {
            '"Abc".kiria()': "abc",
            '"Abc".pandisha()': "ABC",
            '"a-b-c".badilisha("-", "+")': "a+b+c",
            '"a,b".gawanya(",")': '["a", "b"]',
            '"  x  ".punguza()': "x",
            '"abc".anzia("ab")': "kweli",
            '"abc".ina("bc")': "kweli",
            '"abc".idadi': "3",
            '"abc"[1:3]': "bc",
        }
        for expression, expected in cases.items():
            self.assertEqual(value_of(f"andika {expression}"), expected)

    def test_higher_order_builtins(self):
        cases = {
            "pangilia([3,1,2])": "[1, 2, 3]",
            'pangamiza([1,2], kazi(x) { rudia x * 2 })': "[2, 4]",
            'chomoa([1,2,3], kazi(x) { rudia x > 1 })': "[2, 3]",
            'hesabia([1,2,3], kazi(a,b) { rudia a + b }, 0)': "6",
            "yoyote([1,2], kazi(x) { rudia x > 1 })": "kweli",
            "zote([1,2], kazi(x) { rudia x > 1 })": "sikweli",
        }
        for expression, expected in cases.items():
            self.assertEqual(value_of(f"andika {expression}"), expected)

    def test_idadi_function(self):
        self.assertEqual(value_of('andika idadi("abc")'), "3")
        self.assertEqual(value_of("andika idadi([1,2])"), "2")

    def test_unknown_member(self):
        with self.assertRaises(KiswahiliError):
            run('andika "a".haipo()')

    def test_andika_joins_with_spaces(self):
        self.assertEqual(value_of('andika "a", "b", 1'), "a b 1")

    def test_booleans_print_in_swahili(self):
        self.assertEqual(value_of("andika kweli"), "kweli")
        self.assertEqual(value_of("andika sikweli"), "sikweli")
        self.assertEqual(value_of("andika hakuna"), "hakuna")


class ModuleTests(unittest.TestCase):
    def test_builtin_hesabu(self):
        cases = {
            "hesabu.kokotoa(144)": "12.0",
            "hesabu.jumla([1,2,3])": "6",
            "hesabu.jumla(1,2,3)": "6",
            "hesabu.zidisha(6,7)": "42",
        }
        for expression, expected in cases.items():
            self.assertEqual(value_of(f"tumia hesabu\nandika {expression}"),
                             expected)

    def test_module_alias(self):
        self.assertEqual(value_of("tumia hesabu kama h\nandika h.zidisha(2,3)"),
                         "6")

    def test_missing_module(self):
        with self.assertRaises(KiswahiliError):
            run("tumia hakipo")

    def test_unknown_module_member(self):
        with self.assertRaises(KiswahiliError):
            run("tumia hesabu\nandika hesabu.haipo")

    def test_builtin_wins_over_local_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "hesabu.kisw"), "w",
                      encoding="utf-8") as handle:
                handle.write("kazi zidisha(a, b) { rudia 999 }\n")
            interp = Interpreter(search_paths=[tmp])
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                interp.run_source("tumia hesabu\nandika hesabu.zidisha(2, 3)")
            self.assertEqual(buffer.getvalue().strip(), "6")

    def test_local_module_from_search_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "zana.kisw"), "w",
                      encoding="utf-8") as handle:
                handle.write("kazi mara2(x) { rudia x * 2 }\n")
            interp = Interpreter(search_paths=[tmp])
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                interp.run_source("tumia zana\nandika zana.mara2(4)")
            self.assertEqual(buffer.getvalue().strip(), "8")

    def test_cwd_is_not_a_module_search_path(self):
        original = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "zana_siri.kisw"), "w",
                      encoding="utf-8") as handle:
                handle.write("kazi x() { rudia 1 }\n")
            os.chdir(tmp)
            try:
                with self.assertRaises(KiswahiliError):
                    Interpreter().run_source("tumia zana_siri")
            finally:
                os.chdir(original)

    def test_siri_module(self):
        self.assertEqual(
            value_of("tumia siri\nandika idadi(siri.tokeni(8))"), "16")
        self.assertEqual(
            value_of('tumia siri\nandika siri.linganisha("a", "a")'), "kweli")
        n = int(value_of("tumia siri\nandika siri.namba(1, 3)"))
        self.assertIn(n, (1, 2))


class SandboxTests(unittest.TestCase):
    def _sandboxed(self):
        return Interpreter(sandbox=True)

    def test_blocks_filesystem_module(self):
        with self.assertRaises(KiswahiliError):
            self._sandboxed().run_source("tumia faili")

    def test_blocks_system_module(self):
        with self.assertRaises(KiswahiliError):
            self._sandboxed().run_source("tumia mfumo")

    def test_allows_safe_modules(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self._sandboxed().run_source("tumia hesabu\nandika hesabu.zidisha(2, 3)")
        self.assertEqual(buffer.getvalue().strip(), "6")

    def test_sandbox_off_allows_import(self):
        interp = Interpreter()
        interp.run_source("tumia faili")

    def test_cli_sandbox_flag(self):
        from swahili.cli import main
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            code = main(["--sandbox", "-c", "tumia faili"])
        self.assertEqual(code, 1)
        self.assertIn("sandbox", buffer.getvalue())

    def test_allow_fs_confines_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            inside = os.path.join(tmp, "ndani.txt").replace("\\", "/")
            interp = Interpreter(sandbox=True, allowed_fs=[tmp])
            interp.run_source(f'tumia faili\nfaili.andika("{inside}", "habari")')
            with open(os.path.join(tmp, "ndani.txt"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "habari")

    def test_allow_fs_denies_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = os.path.join(os.path.dirname(tmp),
                                   "swahili_nje_test.txt").replace("\\", "/")
            interp = Interpreter(sandbox=True, allowed_fs=[tmp])
            try:
                with self.assertRaises(KiswahiliError):
                    interp.run_source(
                        f'tumia faili\nfaili.andika("{outside}", "x")')
            finally:
                if os.path.exists(outside):
                    os.remove(outside)

    def test_allow_fs_denies_dotdot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            escape = os.path.join(tmp, "..", "swahili_dotdot_test.txt")
            escape = escape.replace("\\", "/")
            interp = Interpreter(sandbox=True, allowed_fs=[tmp])
            try:
                with self.assertRaises(KiswahiliError):
                    interp.run_source(
                        f'tumia faili\nfaili.andika("{escape}", "x")')
            finally:
                real = os.path.realpath(escape)
                if os.path.exists(real):
                    os.remove(real)

    def test_allow_fs_still_blocks_system_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(KiswahiliError):
                Interpreter(sandbox=True, allowed_fs=[tmp]).run_source(
                    "tumia mfumo")

    def test_cli_allow_fs_flag(self):
        from swahili.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cli.txt").replace("\\", "/")
            code = main(["--sandbox", "--allow-fs", tmp, "-c",
                         f'tumia faili\nfaili.andika("{path}", "x")'])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "cli.txt")))

    def test_cli_path_flag(self):
        from swahili.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "zana.kisw"), "w",
                      encoding="utf-8") as handle:
                handle.write("kazi mara2(x) { rudia x * 2 }\n")
            code = main(["--path", tmp, "-c",
                         "tumia zana\nandika zana.mara2(4)"])
            self.assertEqual(code, 0)


class BudgetTests(unittest.TestCase):
    def test_step_budget_stops_infinite_loop(self):
        with self.assertRaises(KiswahiliError):
            Interpreter(max_steps=5000).run_source("wakati kweli { x = 1 }")

    def test_range_budget(self):
        with self.assertRaises(KiswahiliError):
            Interpreter(max_collection=100).run_source("andika 1..1000")

    def test_repetition_budget(self):
        with self.assertRaises(KiswahiliError):
            Interpreter(max_collection=100).run_source('andika "a" * 1000')

    def test_kipeano_budget(self):
        with self.assertRaises(KiswahiliError):
            Interpreter(max_collection=100).run_source("andika kipeano(0, 1000)")

    def test_exponent_budget(self):
        with self.assertRaises(KiswahiliError):
            Interpreter().run_source("andika 2 ** 2000000")

    def test_output_budget(self):
        with self.assertRaises(KiswahiliError):
            Interpreter(max_output=5).run_source('andika "abcdefghij"')

    def test_budgets_reset_between_runs(self):
        interp = Interpreter(max_steps=100)
        with redirect_stdout(io.StringIO()):
            interp.run_source("andika 1")
            interp.run_source("andika 2")


class ParserTests(unittest.TestCase):
    def test_statements(self):
        program = parse("andika 1\nkaza = 2\n", "t.kisw")
        self.assertEqual(len(program.body), 2)

    def test_comments_and_blank_lines(self):
        program = parse("# tupu\n\nandika 1\n\n", "t.kisw")
        self.assertEqual(len(program.body), 1)

    def test_missing_brace(self):
        with self.assertRaises(KiswahiliError):
            parse("kama kweli { andika 1", "t.kisw")

    def test_bad_assignment_target(self):
        with self.assertRaises(KiswahiliError):
            parse("1 = 2", "t.kisw")

    def test_unexpected_token(self):
        with self.assertRaises(KiswahiliError):
            parse("andika )", "t.kisw")

    def test_error_reports_line_and_column(self):
        with self.assertRaises(KiswahiliError) as ctx:
            parse("andika 1\nandika )", "t.kisw")
        self.assertEqual(ctx.exception.line, 2)
        self.assertIn("2 |", ctx.exception.render())


class CliTests(unittest.TestCase):
    def test_run_file(self):
        from swahili.cli import main
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "_tmp_mwendo.kisw")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('andika "kutoka kwa mafile"\n')
        try:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main([path])
            self.assertEqual(code, 0)
            self.assertIn("kutoka kwa mafile", buffer.getvalue())
        finally:
            os.remove(path)

    def test_missing_file(self):
        from swahili.cli import main
        self.assertEqual(main(["haipo.kisw"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)