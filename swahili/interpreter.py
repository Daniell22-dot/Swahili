"""Kisimuwili — the tree-walking interpreter.

Walks the syntax tree produced by `parser.py` and evaluates it. Every scope is
an `Environment`; every function closes over the environment where it was
written, which is what makes Kiswahili closures work.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from . import ast, builtins as kitabu
from .errors import (Endelea, KiswahiliError, Kosa, Rudeia, RuntimeErr,
                     TupaImbali, Vunja)
from .parser import parse
from .runtime import (BoundMethod, Environment, KiswahiliModule,
                      NativeFunction, SwahiliClass, SwahiliFunction,
                      SwahiliInstance, display, iterate, type_name)

MAX_DEPTH = 800


def is_truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    if isinstance(value, (str, list, dict, range)) and len(value) == 0:
        return False
    return True


class Interpreter:
    def __init__(self, repl_hook: Callable[[Environment], None] | None = None,
                 search_paths: list[str] | None = None):
        self.builtin_env = Environment()
        kitabu.install(self.builtin_env)
        self.globals = Environment(self.builtin_env)
        self.repl_hook = repl_hook
        self.search_paths = search_paths or []
        self.modules: dict[str, KiswahiliModule] = {}
        self.depth = 0
        self.frames: list[tuple[str, str]] = []

    # --- public entry points ----------------------------------------------

    def run_source(self, source: str, filename: str = "<kisarifi>",
                   env: Environment | None = None) -> None:
        program = parse(source, filename)
        self.frames.append((filename, source))
        try:
            self.execute(program, env or self.globals)
        finally:
            self.frames.pop()

    def run(self, node: ast.Node, env: Environment) -> None:
        self.execute(node, env)

    def call(self, fn, *args, **kwargs):
        """Call any callable value from Python (used by builtins)."""
        return self._invoke(fn, list(args), kwargs)

    # --- statements --------------------------------------------------------

    def execute(self, node: ast.Node, env: Environment) -> None:
        method = self._DISPATCH.get(type(node))
        if method is None:
            raise RuntimeErr("Serikali haijulikani: " + type(node).__name__,
                             "Cannot execute node: " + type(node).__name__,
                             line=getattr(node, "line", 0))
        method(self, node, env)

    def _exec_block(self, node: ast.Block, env: Environment) -> None:
        for statement in node.body:
            self.execute(statement, env)

    def _exec_program(self, node: ast.Program, env: Environment) -> None:
        self._exec_block(node, env)

    def _exec_expr_statement(self, node: ast.ExprStatement, env: Environment) -> None:
        self.evaluate(node.expr, env)

    def _exec_declaration(self, node: ast.Declaration, env: Environment) -> None:
        value = None if node.value is None else self.evaluate(node.value, env)
        if value is not None and node.type_hint:
            value = self._coerce(node, value, node.type_hint)
        env.define(node.name, value)

    def _exec_assign(self, node: ast.Assign, env: Environment) -> None:
        value = self.evaluate(node.value, env)
        if node.op != "=":
            current = self.evaluate(node.target, env)
            value = self._binary(node, node.op[:-1], current, value)

        target = node.target
        if isinstance(target, ast.Name):
            if env.assign(target.ident, value):
                return
            env.define(target.ident, value)
            return
        if isinstance(target, ast.Member):
            holder = self.evaluate(target.target, env)
            if isinstance(holder, SwahiliInstance):
                holder.fields[target.name] = value
                return
            raise self._oops(node,
                             f"{type_name(holder)} haina sehemu '{target.name}'",
                             f"{type_name(holder)} has no property '{target.name}'")
        if isinstance(target, ast.Index):
            holder = self.evaluate(target.target, env)
            key = self.evaluate(target.key, env)
            try:
                if isinstance(holder, dict):
                    holder[key] = value
                elif isinstance(holder, list):
                    if not isinstance(key, int) or isinstance(key, bool):
                        raise TypeError("orodha inahitaji namba kama index")
                    holder[key] = value
                elif isinstance(holder, str):
                    raise TypeError("maneno hayabadilishiki")
                else:
                    raise TypeError(f"{type_name(holder)} haibadilishiki")
            except TypeError as exc:
                raise self._oops(node, str(exc), str(exc)) from None
            return
        raise self._oops(node, "Lengo la kupewa thamani siyo sahihi",
                         "Invalid assignment target")

    def _exec_if(self, node: ast.If, env: Environment) -> None:
        if is_truthy(self.evaluate(node.test, env)):
            self.execute(node.body, env)
        elif node.orelse is not None:
            self.execute(node.orelse, env)

    def _exec_while(self, node: ast.While, env: Environment) -> None:
        while True:
            truth = is_truthy(self.evaluate(node.test, env))
            if node.until:
                truth = not truth
            if not truth:
                return
            try:
                self.execute(node.body, env)
            except Vunja:
                return
            except Endelea:
                continue

    def _exec_for_each(self, node: ast.ForEach, env: Environment) -> None:
        source = self.evaluate(node.iterable, env)
        if isinstance(source, dict) and node.yields_pairs:
            items: list = [[k, v] for k, v in source.items()]
        else:
            try:
                items = iterate(source)
            except TypeError as exc:
                raise self._oops(
                    node,
                    f"Cannot iterate {type_name(source)} ({exc})",
                    f"Cannot iterate over {type_name(source)}: {exc}") from None

        for item in items:
            env.define(node.name, item)
            try:
                self.execute(node.body, env)
            except Vunja:
                return
            except Endelea:
                continue

    def _exec_return(self, node: ast.Return, env: Environment) -> None:
        value = None if node.value is None else self.evaluate(node.value, env)
        raise Rudeia(value)

    def _exec_break(self, node, env) -> None:
        raise Vunja()

    def _exec_continue(self, node, env) -> None:
        raise Endelea()

    def _exec_pass(self, node, env) -> None:
        return

    def _exec_throw(self, node: ast.Throw, env: Environment) -> None:
        raise TupaImbali(self.evaluate(node.value, env))

    def _exec_debugger(self, node, env) -> None:
        print("── kati: mzunguko wa sasa ──  (type 'endelea' to continue)")
        if self.repl_hook is not None:
            self.repl_hook(env)
        else:
            print("Hakuna mazungumzo; endelea.")

    def _exec_func_def(self, node: ast.FuncDef, env: Environment) -> None:
        env.define(node.name, SwahiliFunction(
            node.name, node.params, node.body, env,
            node.type_hint, node.arrow_hint))

    def _exec_class_def(self, node: ast.ClassDef, env: Environment) -> None:
        cls = SwahiliClass(node.name, node.fields, env)
        env.define(node.name, cls)
        # methods live in their own scope so they do not leak into the
        # surrounding namespace, but still close over it
        class_env = Environment(env)
        self._exec_block(node.body, class_env)
        for name, value in class_env.vars.items():
            if isinstance(value, SwahiliFunction):
                cls.methods[name] = value

    def _exec_try(self, node: ast.Try, env: Environment) -> None:
        try:
            try:
                self.execute(node.body, env)
            except (TupaImbali, KiswahiliError) as exc:
                if node.handler_body is not None:
                    value = exc.args[0] if isinstance(exc, TupaImbali) \
                        else str(exc.swahili)
                    if node.handler:
                        env.define(node.handler, value)
                    self.execute(node.handler_body, env)
                else:
                    raise
            else:
                if node.orelse is not None:
                    self.execute(node.orelse, env)
        finally:
            if node.finally_body is not None:
                self.execute(node.finally_body, env)

    def _exec_import(self, node: ast.Import, env: Environment) -> None:
        module = self.load_module(node.module, node)
        env.define(node.alias or node.module, module)

    # --- expressions -------------------------------------------------------

    def evaluate(self, node: ast.Node, env: Environment) -> Any:
        method = self._EVAL_DISPATCH.get(type(node))
        if method is None:
            raise RuntimeErr("Hesabu haijulikani: " + type(node).__name__,
                             "Cannot evaluate node: " + type(node).__name__,
                             line=getattr(node, "line", 0))
        return method(self, node, env)

    def _eval_number(self, node: ast.Number, env) -> Any:
        return node.value

    def _eval_text(self, node: ast.Text, env) -> Any:
        if not node.parts:
            return node.value
        chunks: list[str] = []
        for part in node.parts:
            chunks.append(part if isinstance(part, str)
                          else display(self.evaluate(part, env)))
        return "".join(chunks)

    def _eval_bool(self, node: ast.BoolLit, env) -> Any:
        return node.value

    def _eval_none(self, node: ast.NoneLit, env) -> Any:
        return None

    def _eval_list(self, node: ast.ListLit, env) -> Any:
        return [self.evaluate(item, env) for item in node.elements]

    def _eval_dict(self, node: ast.DictLit, env) -> Any:
        result: dict = {}
        for key_node, value_node in node.pairs:
            try:
                result[self.evaluate(key_node, env)] = self.evaluate(value_node, env)
            except TypeError as exc:
                raise self._oops(node, f"Funguo siyo sahihi: {exc}",
                                 f"Unusable dictionary key: {exc}") from None
        return result

    def _eval_range(self, node: ast.RangeLit, env) -> Any:
        start = self.evaluate(node.start, env)
        stop = self.evaluate(node.stop, env)
        step = self.evaluate(node.step, env) if node.step else 1
        try:
            return range(int(start), int(stop), int(step))
        except (TypeError, ValueError) as exc:
            raise self._oops(node, f"Kipeano siyo sahihi: {exc}",
                             f"Invalid range: {exc}") from None

    def _eval_name(self, node: ast.Name, env) -> Any:
        try:
            return env.get(node.ident)
        except KeyError:
            close = _closest(node.ident, env.all_names())
            hint = f"Ulikuwa unaima '{close}'?" if close else \
                "Je, umeandika jina hili mwanzo?"
            raise self._oops(node, f"Hamna jina la '{node.ident}'",
                             f"No such name: '{node.ident}'", hint)

    def _eval_lambda(self, node: ast.Lambda, env: Environment) -> Any:
        return SwahiliFunction("<kazi>", node.params, node.body, env)

    def _eval_funcref(self, node: ast.FuncRef, env) -> Any:
        try:
            return env.get(node.ident)
        except KeyError:
            raise self._oops(node, f"Hamna kazi ya '{node.ident}'",
                             f"No such function: '{node.ident}'")

    def _eval_grouping(self, node: ast.Grouping, env) -> Any:
        return self.evaluate(node.inner, env)

    def _eval_unary(self, node: ast.Unary, env) -> Any:
        value = self.evaluate(node.operand, env)
        if node.op == "-":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise self._oops(node, f"Hawezi kubadilisha alama ya {type_name(value)}",
                                 f"Cannot negate {type_name(value)}")
            return -value
        if node.op == "+":
            return value
        return not is_truthy(value)

    def _eval_logical(self, node: ast.Logical, env) -> Any:
        left = self.evaluate(node.left, env)
        if node.op == "na":
            return is_truthy(left) and is_truthy(self.evaluate(node.right, env))
        return is_truthy(left) or is_truthy(self.evaluate(node.right, env))

    def _eval_compare(self, node: ast.Compare, env) -> Any:
        left = self.evaluate(node.left, env)
        right = self.evaluate(node.right, env)
        op = node.op

        if op == "iko":
            if isinstance(right, str):
                return isinstance(left, str) and left in right
            try:
                return left in iterate(right)
            except TypeError:
                return False
        if op == "ni":
            return type(left) is type(right) and left == right

        try:
            if op == "==":
                return _loose_eq(left, right)
            if op == "!=":
                return not _loose_eq(left, right)
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
        except TypeError as exc:
            raise self._oops(
                node,
                f"Hawezi kulinganisha {type_name(left)} na {type_name(right)}",
                f"Cannot compare {type_name(left)} with {type_name(right)}") from None
        raise self._oops(node, "Linganisho lisilojulikana: " + op,
                         "Unknown comparison: " + op)

    def _eval_binary(self, node: ast.Binary, env) -> Any:
        left = self.evaluate(node.left, env)
        right = self.evaluate(node.right, env)
        return self._binary(node, node.op, left, right)

    def _binary(self, node, op: str, left: Any, right: Any) -> Any:
        try:
            return _apply_binary(op, left, right)
        except TypeError as exc:
            raise self._oops(
                node,
                f"Operesheni '{op}' haiwezi kutumika kwa "
                f"{type_name(left)} na {type_name(right)}: {exc}",
                f"Operator '{op}' cannot be applied to "
                f"{type_name(left)} and {type_name(right)}: {exc}") from None
        except ZeroDivisionError:
            raise self._oops(node, "Ugawanyaji wa sifuri haiwezekani",
                             "Division by zero") from None

    def _eval_ternary(self, node: ast.Ternary, env) -> Any:
        if is_truthy(self.evaluate(node.test, env)):
            return self.evaluate(node.consequent, env)
        return self.evaluate(node.alternate, env)

    def _eval_index(self, node: ast.Index, env) -> Any:
        holder = self.evaluate(node.target, env)
        key = self.evaluate(node.key, env)
        try:
            return holder[key]
        except IndexError:
            raise self._oops(
                node, f"Indexi {key} iko nje ya mpaka",
                f"Index {key} is out of range") from None
        except KeyError:
            raise self._oops(
                node, f"Hamna funguo la '{key}'",
                f"No such key: '{key}'",
                f"Fun guo zilizoopo: {list(holder)[:8] if isinstance(holder, dict) else ''}"
            ) from None
        except TypeError as exc:
            raise self._oops(node, str(exc), str(exc)) from None

    def _eval_slice(self, node: ast.Slice, env) -> Any:
        holder = self.evaluate(node.target, env)
        start = self.evaluate(node.start, env) if node.start else None
        stop = self.evaluate(node.stop, env) if node.stop else None
        try:
            return holder[start:stop]
        except TypeError as exc:
            raise self._oops(node, str(exc), str(exc)) from None

    def _eval_member(self, node: ast.Member, env) -> Any:
        holder = self.evaluate(node.target, env)
        return self.get_member(node, holder, node.name)

    def get_member(self, node, holder: Any, name: str) -> Any:
        if isinstance(holder, SwahiliInstance):
            if name in holder.fields:
                return holder.fields[name]
            method = holder.cls.methods.get(name)
            if method is not None:
                return BoundMethod(method, holder)
            if name in ("orodha", "kamusi", "hakuna"):
                raise self._oops(node, f"Mwanafunzi hana '{name}'",
                                 f"Instance has no '{name}'")
            return kitabu.get_member(self, dict(holder.fields), name)

        if isinstance(holder, SwahiliClass):
            method = holder.methods.get(name)
            if method is not None:
                return method
            raise self._oops(node, f"Darasa '{holder.name}' haina kazi '{name}'",
                             f"Class '{holder.name}' has no method '{name}'")

        if isinstance(holder, KiswahiliModule):
            if name in holder.members:
                return holder.members[name]
            close = _closest(name, list(holder.members))
            hint = f"Ulikuwa unaima '{close}'?" if close else \
                f"Moduli ina: {', '.join(list(holder.members)[:10])}"
            raise self._oops(node, f"Moduli '{holder.name}' haina '{name}'",
                             f"Module '{holder.name}' has no '{name}'", hint)

        try:
            return kitabu.get_member(self, holder, name)
        except TypeError as exc:
            raise self._oops(node, str(exc), str(exc)) from None

    def _eval_call(self, node: ast.Call, env: Environment) -> Any:
        callee = self.evaluate(node.callee, env)
        args = [self.evaluate(arg, env) for arg in node.args]
        kwargs = {key: self.evaluate(value, env)
                  for key, value in node.kwargs.items()}
        return self._invoke(callee, args, kwargs, node)

    def _eval_assign_expr(self, node: ast.Assign, env: Environment) -> Any:
        self.execute(node, env)
        return self.evaluate(node.target, env)

    def _eval_throw_expr(self, node: ast.Throw, env: Environment) -> Any:
        raise TupaImbali(self.evaluate(node.value, env))

    def _eval_new(self, node: ast.New, env: Environment) -> Any:
        try:
            cls = env.get(node.class_name)
        except KeyError:
            raise self._oops(node, f"Hamna darasa jina la '{node.class_name}'",
                             f"No class named '{node.class_name}'") from None
        if not isinstance(cls, SwahiliClass):
            raise self._oops(node, f"'{node.class_name}' siyo darasa",
                             f"'{node.class_name}' is not a class")

        instance = SwahiliInstance(cls)
        constructor = cls.methods.get(node.class_name)
        if constructor is not None:
            args = [self.evaluate(arg, env) for arg in node.args]
            kwargs = {key: self.evaluate(value, env)
                      for key, value in node.kwargs.items()}
            local = Environment(constructor.closure)
            local.define("mwenyewe", instance)
            self._run_function(constructor, local, args, kwargs, node,
                               self_instance=instance)
        elif node.args or node.kwargs:
            names = ", ".join(cls.methods) or "hakuna"
            raise self._oops(
                node,
                f"Darasa '{cls.name}' haina mjenzi (kazi '{cls.name}')",
                f"Class '{cls.name}' has no constructor "
                f"(a method named '{cls.name}')",
                f"METHODS: {names}. Tengeneza kazi {cls.name}(...) "
                f"ndani ya darasa.")
        return instance

    # --- calling -----------------------------------------------------------

    def _invoke(self, fn, args: list, kwargs: dict, node=None) -> Any:
        if self.depth >= MAX_DEPTH:
            raise RuntimeErr(
                f"Mzunguko umefika kina {MAX_DEPTH} — pengo au mzunguko?",
                f"Recursion limit of {MAX_DEPTH} reached — infinite loop?",
                line=getattr(node, "line", 0))

        try:
            if isinstance(fn, NativeFunction):
                if fn.needs_interp:
                    return fn(self, *args, **kwargs)
                return fn(*args, **kwargs)

            if isinstance(fn, BoundMethod):
                local = Environment(fn.function.closure)
                local.define("mwenyewe", fn.instance)
                return self._run_function(fn.function, local, args, kwargs, node,
                                         self_instance=fn.instance)

            if isinstance(fn, SwahiliFunction):
                local = Environment(fn.closure)
                return self._run_function(fn, local, args, kwargs, node)

            if callable(fn):
                return fn(*args, **kwargs)
        except (KiswahiliError, TupaImbali, Rudeia, Vunja, Endelea):
            raise
        except TypeError as exc:
            message = str(exc)
            raise self._oops(node, f"Agizo lisilo sahihi: {message}",
                             f"Bad call: {message}") from None

        where = type_name(fn)
        raise self._oops(node, f"{where} siwezi kuwekwa wazi",
                         f"{where} is not callable")

    def _run_function(self, fn: SwahiliFunction, local: Environment, args: list,
                      kwargs: dict, node, self_instance=None) -> Any:
        params = fn.params
        if len(args) > len(params):
            raise self._oops(
                node,
                f"Kazi '{fn.name}' inapenda {len(params)} vigezo, "
                f"ulitoa {len(args)}",
                f"'{fn.name}' takes {len(params)} argument(s) but got {len(args)}")

        for index, param in enumerate(params):
            if index < len(args):
                if param.name in kwargs:
                    raise self._oops(node,
                                     f"Ugizo wa '{param.name}' ulirudiwa",
                                     f"Duplicate argument '{param.name}'")
                value = args[index]
            elif param.name in kwargs:
                value = kwargs.pop(param.name)
            elif param.default is not None:
                value = self.evaluate(param.default, fn.closure)
            else:
                raise self._oops(
                    node,
                    f"Kazi '{fn.name}' inahitaji vigezo '{param.name}'",
                    f"'{fn.name}' is missing required argument '{param.name}'")

            if param.type_hint:
                value = self._coerce(node, value, param.type_hint)
            local.define(param.name, value)

        if kwargs:
            extra = ", ".join(sorted(kwargs))
            raise self._oops(node,
                             f"Kazi '{fn.name}' haijui vigezo: {extra}",
                             f"'{fn.name}' got unexpected argument(s): {extra}")

        self.depth += 1
        try:
            self.execute(fn.body, local)
        except Rudeia as ret:
            return ret.args[0] if ret.args else None
        finally:
            self.depth -= 1
        return None

    # --- modules -----------------------------------------------------------

    def load_module(self, name: str, node=None) -> KiswahiliModule:
        if name in self.modules:
            return self.modules[name]

        spec = f"{name}.kisw"
        path = self._find_file(spec)
        if path is not None:
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
            module_env = Environment(self.builtin_env)
            self.run_source(source, path, module_env)
            module = KiswahiliModule(name, dict(module_env.vars))
            self.modules[name] = module
            return module

        builtin = _load_builtin_module(self, name)
        if builtin is not None:
            self.modules[name] = builtin
            return builtin

        raise self._oops(
            node,
            f"Hakuna moduli jina la '{name}'",
            f"No module named '{name}'",
            f" searching: {', '.join(self.search_paths) or 'script folder'}"
            f" and {spec}")

    def _exec_in_module(self, program: ast.Program, env: Environment) -> None:
        self._exec_program(program, env)

    def _find_file(self, filename: str) -> str | None:
        folders: list[str] = [*self.search_paths, os.getcwd()]
        candidates = [os.path.join(folder, filename) for folder in folders]
        candidates += [os.path.join(folder, "moduli", filename) for folder in folders]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)
        return None

    # --- errors & typing ---------------------------------------------------

    def _oops(self, node, swahili: str, english: str = "", hint: str = "") -> Kosa:
        line = getattr(node, "line", 0)
        if self.frames and line:
            filename, source = self.frames[-1]
            index = _index_of_line(source, line)
            return Kosa("Kisimuwili / Runtime", swahili, english or swahili,
                        source, index, hint)
        return RuntimeErr(swahili, english or swahili, line=line)

    def _coerce(self, node, value: Any, hint: str) -> Any:
        actual = type_name(value)
        if hint == "namba" and actual == "desimali" and float(value).is_integer():
            return int(value)
        if actual == hint:
            return value
        if hint == "desimali" and actual == "namba":
            return float(value)
        if hint == "orodha" and actual == "kipeano":
            return list(value)
        raise self._oops(
            node,
            f"Thamani hii ni {actual}, lakini ulitaka {hint}",
            f"This value is {actual}, but you asked for {hint}",
            _TYPE_HINTS.get(hint, ""))


_TYPE_HINTS = {
    "namba": "Mfano: `namba(1)` au `namba(\"1\")`",
    "desimali": "Mfano: `desimali(1.5)` au `desimali(\"1.5\")`",
    "maneno": "Mfano: `maneno(\"habari\")` au `maneno(42)`",
    "orodha": "Mfano: `orodha([1, 2])` au `orodha(\"a,b\".gawanya(\",\"))`",
    "kamusi": "Mfano: `kamusi({\"a\": 1})`",
    "hali": "Mfano: `hali(kweli)`",
}


def _loose_eq(left: Any, right: Any) -> bool:
    """Equality that refuses to conflate `kweli` with `1`."""
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right


def _apply_binary(op: str, left: Any, right: Any) -> Any:
    numeric = (int, float)
    if op == "+":
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        if _num(left) and _num(right):
            return left + right
        raise TypeError("+ inahitaji namba, maneno, au orodha zote mbili")
    if op == "-":
        if _num(left) and _num(right):
            return left - right
        raise TypeError("- inahitaji namba zote mbili")
    if op == "*":
        if _num(left) and _num(right):
            return left * right
        if isinstance(left, str) and _num(right):
            return left * int(right)
        if _num(left) and isinstance(right, str):
            return right * int(left)
        if isinstance(left, list) and _num(right):
            return left * int(right)
        raise TypeError("* inahitaji namba zote mbili, au maneno/orodha na namba")
    if op == "/":
        if _num(left) and _num(right):
            return left / right
        raise TypeError("/ inahitaji namba zote mbili")
    if op == "//":
        if _num(left) and _num(right):
            return left // right
        raise TypeError("// inahitaji namba zote mbili")
    if op == "%":
        if _num(left) and _num(right):
            return left % right
        raise TypeError("% inahitaji namba zote mbili")
    if op == "**":
        if _num(left) and _num(right):
            return left ** right
        raise TypeError("** inahitaji namba zote mbili")
    raise TypeError("operesheni isiyojulikana: " + op)


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _index_of_line(source: str, line: int) -> int:
    """Byte-ish offset of the start of `line`, for the caret in diagnostics."""
    offset = 0
    for number in range(1, line):
        newline = source.find("\n", offset)
        if newline == -1:
            return offset
        offset = newline + 1
    end = len(source)
    while offset < end and source[offset] in " \t":
        offset += 1
    return offset


def _closest(name: str, options: list[str]) -> str:
    import difflib
    matches = difflib.get_close_matches(name, options, n=1, cutoff=0.6)
    return matches[0] if matches else ""


def _load_builtin_module(interp: "Interpreter", name: str) -> KiswahiliModule | None:
    from . import stdlib
    factory = stdlib.MODULES.get(name)
    if factory is None:
        return None
    members = factory(interp)
    return KiswahiliModule(name, members)


Interpreter._DISPATCH = {
    ast.Program: Interpreter._exec_program,
    ast.Block: Interpreter._exec_block,
    ast.ExprStatement: Interpreter._exec_expr_statement,
    ast.Declaration: Interpreter._exec_declaration,
    ast.Assign: Interpreter._exec_assign,
    ast.If: Interpreter._exec_if,
    ast.While: Interpreter._exec_while,
    ast.ForEach: Interpreter._exec_for_each,
    ast.Return: Interpreter._exec_return,
    ast.Break: Interpreter._exec_break,
    ast.Continue: Interpreter._exec_continue,
    ast.Pass: Interpreter._exec_pass,
    ast.Throw: Interpreter._exec_throw,
    ast.Debugger: Interpreter._exec_debugger,
    ast.FuncDef: Interpreter._exec_func_def,
    ast.ClassDef: Interpreter._exec_class_def,
    ast.Try: Interpreter._exec_try,
    ast.Import: Interpreter._exec_import,
}

Interpreter._EVAL_DISPATCH = {
    ast.Number: Interpreter._eval_number,
    ast.Text: Interpreter._eval_text,
    ast.BoolLit: Interpreter._eval_bool,
    ast.NoneLit: Interpreter._eval_none,
    ast.ListLit: Interpreter._eval_list,
    ast.DictLit: Interpreter._eval_dict,
    ast.RangeLit: Interpreter._eval_range,
    ast.Name: Interpreter._eval_name,
    ast.FuncRef: Interpreter._eval_funcref,
    ast.Lambda: Interpreter._eval_lambda,
    ast.Grouping: Interpreter._eval_grouping,
    ast.Unary: Interpreter._eval_unary,
    ast.Binary: Interpreter._eval_binary,
    ast.Logical: Interpreter._eval_logical,
    ast.Compare: Interpreter._eval_compare,
    ast.Ternary: Interpreter._eval_ternary,
    ast.Index: Interpreter._eval_index,
    ast.Slice: Interpreter._eval_slice,
    ast.Member: Interpreter._eval_member,
    ast.Call: Interpreter._eval_call,
    ast.New: Interpreter._eval_new,
    ast.Assign: Interpreter._eval_assign_expr,
    ast.Throw: Interpreter._eval_throw_expr,
}