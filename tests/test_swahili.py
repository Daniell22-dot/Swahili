"""Vijana — tests for Kiswahili. Run with:  python -m unittest discover tests"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swahili import Interpreter, KiswahiliError            # noqa: E402
from swahili.lexer import tokenize                          # noqa: E402
from swahili.parser import parse                            # noqa: E402


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
            '"abc"[1:3]': '"bc"',
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