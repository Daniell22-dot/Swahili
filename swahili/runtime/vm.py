"""Kisimuwili VM — executes bytecode produced by the Kiswahili compiler.

The VM keeps the tree-walking interpreter as the semantic reference: values,
environments, classes, builtins, and diagnostics are shared.  What changes is
execution: an explicit instruction pointer, value stack, call frames and block
stack replace recursive AST evaluation.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from ..compiler.code import Artifact, ClassSpec, CodeObject, FunctionSpec
from ..compiler.compiler import compile_source
from ..compiler.opcode import Opcode
from ..errors import (Endelea, KiswahiliError, Kosa, Rudeia, RuntimeErr,
                      TupaImbali, Vunja)
from ..library import builtins as kitabu
from ..library import modules as stdlib
from .interpreter import (MAX_DEPTH, MAX_BITS, MAX_EXPONENT, Interpreter,
                          _closest, _index_of_line, _load_builtin_module,
                          _TYPE_HINTS)
from .semantics import (apply_binary, compare, exponent_too_large_message,
                        format_value, is_number, is_truthy,
                        too_large_message)
from .values import (BoundMethod, Environment, KiswahiliModule,
                     NativeFunction, SuperProxy, SwahiliClass, SwahiliFunction,
                     SwahiliInstance, display, iterate, type_name)


class _LineNode:
    """Tiny stand-in so inherited interpreter diagnostics can accept a line."""

    __slots__ = ("line",)

    def __init__(self, line: int):
        self.line = line


class CompiledFunction(SwahiliFunction):
    """A `kazi` compiled to bytecode, with the closure it was created in."""

    __slots__ = ("spec", "code", "param_names", "param_hints", "defaults")

    def __init__(self, spec: FunctionSpec, closure: Environment):
        super().__init__(spec.name, [], None, closure,
                         spec.type_hint, spec.arrow_hint)
        self.spec = spec
        self.code = spec.code
        self.param_names = list(spec.param_names)
        self.param_hints = list(spec.param_hints)
        self.defaults = list(spec.defaults)

    def __repr__(self) -> str:
        names = ", ".join(self.param_names)
        return f"<kazi {self.name}({names})>"


class CompiledClass(SwahiliClass):
    """A `darasa` whose methods are compiled functions."""

    __slots__ = ("spec",)

    def __init__(self, spec: ClassSpec, closure: Environment,
                 parent: SwahiliClass | None = None):
        super().__init__(spec.name, list(spec.fields), closure,
                         dict(spec.defaults), parent)
        self.spec = spec


class CompiledBoundMethod(BoundMethod):
    """A compiled method bound to an instance, with its declaring class."""

    __slots__ = ()


class _Iterator:
    __slots__ = ("items", "index")

    def __init__(self, items: list[Any]):
        self.items = items
        self.index = 0


@dataclass
class Block:
    kind: str
    target: Any = None
    target2: Any = None
    flag: Any = None
    pending: BaseException | None = None
    stack_depth: int = 0


@dataclass
class Frame:
    code: CodeObject
    scope: Environment
    stack: list[Any]
    blocks: list[Block]
    ip: int = 0


class VM(Interpreter):
    """Bytecode virtual machine, API-compatible with :class:`Interpreter`."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.exec_frames: list[Frame] = []

    # --- public entry points ----------------------------------------------

    def run_source(self, source: str, filename: str = "<kisarifi>",
                   env: Environment | None = None) -> None:
        code = compile_source(source, filename)
        self.run_code(code, env)

    def run_code(self, code: CodeObject,
                 env: Environment | None = None) -> None:
        if not self.frames:
            self.reset_budgets()
        self.frames.append((code.filename, code.source))
        try:
            self._execute_frame(Frame(code, env or self.globals, [], []))
        except Rudeia:
            pass
        finally:
            self.frames.pop()

    def run_artifact(self, artifact: Artifact | str,
                     env: Environment | None = None) -> None:
        if isinstance(artifact, str):
            artifact = Artifact.load(artifact)
        if not self.frames:
            self.reset_budgets()
        self.frames.append((artifact.filename, artifact.source))
        try:
            self._execute_frame(
                Frame(artifact.code, env or self.globals, [], []))
        except Rudeia:
            pass
        finally:
            self.frames.pop()

    def call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return self._invoke_value(fn, list(args), dict(kwargs), 0)

    # --- frame execution ---------------------------------------------------

    def _execute_frame(self, frame: Frame) -> None:
        self.exec_frames.append(frame)
        instructions = frame.code.instructions
        try:
            while frame.ip < len(instructions):
                instruction = instructions[frame.ip]
                frame.ip += 1
                self._tick(instruction.line)
                try:
                    self._step(frame, instruction)
                except (Rudeia, Vunja, Endelea, TupaImbali, KiswahiliError) as exc:
                    if not self._unwind(frame, exc):
                        raise
        finally:
            self.exec_frames.pop()

    def _tick(self, line: int) -> None:
        self.steps += 1
        if self.max_steps is not None and self.steps > self.max_steps:
            raise RuntimeErr(
                f"Mpango umezidi kikomo cha hatua ({self.max_steps})",
                f"Step budget of {self.max_steps} exceeded", line=line)
        if (self.max_seconds is not None
                and time.monotonic() - self.started > self.max_seconds):
            raise RuntimeErr(
                f"Mpango umezidi kikomo cha muda ({self.max_seconds}s)",
                f"Time budget of {self.max_seconds}s exceeded", line=line)

    def _unwind(self, frame: Frame, exc: BaseException) -> bool:
        while frame.blocks:
            block = frame.blocks[-1]
            del frame.stack[block.stack_depth:]
            if block.kind == "loop":
                if isinstance(exc, Vunja):
                    frame.blocks.pop()
                    frame.ip = block.target
                    return True
                if isinstance(exc, Endelea):
                    frame.ip = block.target2
                    return True
                frame.blocks.pop()
                continue
            if block.kind == "finally_cleanup":
                frame.blocks.pop()
                continue
            if block.kind in ("try", "finally"):
                catchable = isinstance(exc, (TupaImbali, KiswahiliError))
                if block.kind == "try" and block.flag and catchable \
                        and block.target is not None:
                    block.kind = "finally"
                    value = (exc.thamani if isinstance(exc, TupaImbali)
                             else exc.swahili)
                    frame.stack.append(value)
                    frame.ip = block.target
                    return True
                frame.blocks.pop()
                if block.target2 is not None:
                    frame.blocks.append(Block(
                        "finally_cleanup", pending=exc,
                        stack_depth=len(frame.stack)))
                    frame.ip = block.target2
                    return True
                continue
            frame.blocks.pop()
        return False

    def _oops_line(self, line: int, swahili: str, english: str = "",
                   hint: str = "") -> KiswahiliError:
        if self.frames and line:
            _, source = self.frames[-1]
            return Kosa("Kisimuwili / VM", swahili, english or swahili,
                        source, _index_of_line(source, line), hint)
        return RuntimeErr(swahili, english or swahili, line=line)

    # --- instruction dispatch ---------------------------------------------

    def _step(self, frame: Frame, instruction) -> None:
        op = instruction.op
        stack = frame.stack
        arg = instruction.arg
        arg2 = instruction.arg2
        arg3 = instruction.arg3
        line = instruction.line

        if op == Opcode.NOP:
            return
        if op == Opcode.LOAD_CONST:
            stack.append(frame.code.constants[arg])
            return
        if op == Opcode.LOAD_NONE:
            stack.append(None)
            return
        if op == Opcode.LOAD_TRUE:
            stack.append(True)
            return
        if op == Opcode.LOAD_FALSE:
            stack.append(False)
            return
        if op in (Opcode.LOAD_NAME, Opcode.LOAD_FUNC_REF):
            self._load_name(frame, arg, line, op == Opcode.LOAD_FUNC_REF)
            return
        if op == Opcode.DEFINE_NAME:
            frame.scope.define(frame.code.constants[arg], stack.pop())
            return
        if op == Opcode.STORE_NAME:
            value = stack.pop()
            name = frame.code.constants[arg]
            if not frame.scope.assign(name, value):
                frame.scope.define(name, value)
            return
        if op == Opcode.POP:
            stack.pop()
            return
        if op == Opcode.DUP:
            stack.append(stack[-1])
            return

        if op == Opcode.BUILD_LIST:
            count = int(arg)
            items = stack[-count:] if count else []
            if count:
                del stack[-count:]
            stack.append(items)
            return
        if op == Opcode.BUILD_DICT:
            self._build_dict(frame, int(arg), line)
            return
        if op == Opcode.BUILD_RANGE:
            self._build_range(frame, line)
            return
        if op == Opcode.BUILD_STRING:
            count = int(arg)
            chunks = stack[-count:] if count else []
            if count:
                del stack[-count:]
            stack.append("".join(chunks))
            return
        if op == Opcode.FORMAT_VALUE:
            stack.append(format_value(stack.pop()))
            return
        if op == Opcode.MAKE_ITERATOR:
            self._make_iterator(frame, bool(arg), line)
            return
        if op == Opcode.FOR_NEXT:
            iterator = stack[-1]
            if iterator.index < len(iterator.items):
                stack.append(iterator.items[iterator.index])
                iterator.index += 1
            else:
                frame.ip = arg
            return

        if op == Opcode.UNARY_NEGATIVE:
            self._negative(frame, line)
            return
        if op == Opcode.UNARY_POSITIVE:
            return
        if op == Opcode.UNARY_NOT:
            stack.append(not is_truthy(stack.pop()))
            return
        if op == Opcode.TO_BOOL:
            stack.append(is_truthy(stack.pop()))
            return
        if op == Opcode.BINARY_OP:
            self._binary(frame, frame.code.constants[arg], line)
            return
        if op == Opcode.COMPARE_OP:
            self._compare(frame, frame.code.constants[arg], line)
            return
        if op == Opcode.BINARY_SUBSCR:
            self._subscript(frame, line)
            return
        if op == Opcode.STORE_SUBSCR:
            self._store_subscript(frame, line)
            return
        if op == Opcode.SLICE:
            self._slice(frame, line)
            return
        if op == Opcode.LOAD_MEMBER:
            holder = stack.pop()
            stack.append(self.get_member(_LineNode(line), holder,
                                         frame.code.constants[arg]))
            return
        if op == Opcode.STORE_MEMBER:
            self._store_member(frame, frame.code.constants[arg], line)
            return
        if op == Opcode.COERCE:
            value = stack.pop()
            hint = frame.code.constants[arg]
            result = self._coerce(_LineNode(line), value, hint)
            if type_name(result) != hint:
                raise self._oops_line(
                    line,
                    f"Thamani hii ni {type_name(value)}, lakini ulitaka {hint}",
                    f"This value is {type_name(value)}, but you asked for {hint}",
                    _TYPE_HINTS.get(hint, ""))
            stack.append(result)
            return

        if op == Opcode.JUMP_ABSOLUTE:
            frame.ip = arg
            return
        if op == Opcode.JUMP_FORWARD:
            frame.ip += int(arg)
            return
        if op == Opcode.JUMP_IF_FALSE:
            if not is_truthy(stack.pop()):
                frame.ip = arg
            return
        if op == Opcode.JUMP_IF_TRUE:
            if is_truthy(stack.pop()):
                frame.ip = arg
            return

        if op == Opcode.RETURN_VALUE:
            raise Rudeia(stack.pop())
        if op == Opcode.CALL_FUNCTION:
            self._call(frame, int(arg), arg2, line)
            return
        if op == Opcode.MAKE_FUNCTION:
            spec = frame.code.constants[arg]
            stack.append(CompiledFunction(spec, frame.scope))
            return
        if op == Opcode.MAKE_CLASS:
            self._make_class(frame, arg, line)
            return
        if op == Opcode.NEW_INSTANCE:
            self._new_instance(frame, int(arg), arg2, arg3, line)
            return
        if op == Opcode.IMPORT_NAME:
            self._import(frame, arg, arg2, bool(arg3), line)
            return
        if op == Opcode.RAISE:
            raise TupaImbali(stack.pop())
        if op == Opcode.DEBUGGER:
            print("── kati: mzunguko wa sasa ──  (type 'endelea' to continue)")
            if self.repl_hook is not None:
                self.repl_hook(frame.scope)
            else:
                print("Hakuna mazungumzo; endelea.")
            return

        if op == Opcode.SETUP_LOOP:
            frame.blocks.append(Block("loop", arg, arg2, None,
                                      None, len(stack)))
            return
        if op == Opcode.SETUP_TRY:
            frame.blocks.append(Block("try", arg, arg2, bool(arg3),
                                      None, len(stack)))
            return
        if op == Opcode.DISABLE_HANDLER:
            if frame.blocks and frame.blocks[-1].kind == "try":
                frame.blocks[-1].kind = "finally"
            return
        if op == Opcode.POP_BLOCK:
            if frame.blocks:
                frame.blocks.pop()
            return
        if op == Opcode.PUSH_FINALLY:
            frame.blocks.append(Block("finally_cleanup", None, None, None,
                                      None, len(stack)))
            return
        if op == Opcode.END_FINALLY:
            if frame.blocks and frame.blocks[-1].kind == "finally_cleanup":
                block = frame.blocks.pop()
                if block.pending is not None:
                    raise block.pending
            return
        if op == Opcode.BREAK:
            raise Vunja()
        if op == Opcode.CONTINUE:
            raise Endelea()

        raise RuntimeErr(f"Agizo la VM halijulikani: {int(op)} / "
                         f"Unknown VM opcode: {int(op)}", line=line)

    # --- individual operations --------------------------------------------

    def _load_name(self, frame: Frame, name_index: int, line: int,
                   want_function: bool = False) -> None:
        name = frame.code.constants[name_index]
        try:
            value = frame.scope.get(name)
        except KeyError:
            close = _closest(name, frame.scope.all_names())
            if want_function:
                raise self._oops_line(
                    line, f"Hamna kazi ya '{name}'",
                    f"No such function: '{name}'",
                    f"Ulikuwa unaima '{close}'?" if close else "")
            hint = (f"Ulikuwa unaima '{close}'?" if close else
                    "Je, umeandika jina hili mwanzo?")
            raise self._oops_line(line, f"Hamna jina la '{name}'",
                                  f"No such name: '{name}'", hint) from None
        frame.stack.append(value)

    def _build_dict(self, frame: Frame, count: int, line: int) -> None:
        pairs = [frame.stack.pop() for _ in range(count * 2)]
        pairs.reverse()
        result: dict[Any, Any] = {}
        try:
            for index in range(0, len(pairs), 2):
                result[pairs[index]] = pairs[index + 1]
        except TypeError as exc:
            raise self._oops_line(line, f"Funguo siyo sahihi: {exc}",
                                  f"Unusable dictionary key: {exc}") from None
        frame.stack.append(result)

    def _build_range(self, frame: Frame, line: int) -> None:
        step = frame.stack.pop()
        stop = frame.stack.pop()
        start = frame.stack.pop()
        try:
            result = range(int(start), int(stop), int(step))
        except (TypeError, ValueError) as exc:
            raise self._oops_line(line, f"Kipeano siyo sahihi: {exc}",
                                  f"Invalid range: {exc}") from None
        if self.max_collection is not None and len(result) > self.max_collection:
            raise self._oops_line(line,
                                  f"Kipeano ni kikubwa mno "
                                  f"({len(result)} > {self.max_collection})",
                                  f"Range is too large "
                                  f"({len(result)} > {self.max_collection})")
        frame.stack.append(result)

    def _make_iterator(self, frame: Frame, yields_pairs: bool,
                       line: int) -> None:
        source = frame.stack.pop()
        if isinstance(source, dict) and yields_pairs:
            items: list[Any] = [[key, value] for key, value in source.items()]
        else:
            try:
                items = iterate(source)
            except TypeError as exc:
                raise self._oops_line(
                    line, f"Cannot iterate {type_name(source)} ({exc})",
                    f"Cannot iterate over {type_name(source)}: {exc}") from None
        frame.stack.append(_Iterator(items))

    def _negative(self, frame: Frame, line: int) -> None:
        value = frame.stack.pop()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise self._oops_line(
                line, f"Hawezi kubadilisha alama ya {type_name(value)}",
                f"Cannot negate {type_name(value)}")
        frame.stack.append(-value)

    def _binary(self, frame: Frame, op: str, line: int) -> None:
        right = frame.stack.pop()
        left = frame.stack.pop()
        limit = self.max_collection
        if limit is not None and op == "*":
            if isinstance(left, (str, list)) and is_number(right):
                size = len(left) * max(0, int(right))
                if size > limit:
                    raise self._oops_line(line, *too_large_message(size, limit))
            if isinstance(right, (str, list)) and is_number(left):
                size = len(right) * max(0, int(left))
                if size > limit:
                    raise self._oops_line(line, *too_large_message(size, limit))
        if (op == "**" and isinstance(left, int) and isinstance(right, int)
                and not isinstance(left, bool) and not isinstance(right, bool)
                and right > 0):
            bits = max(1, abs(left).bit_length()) * right
            if right > MAX_EXPONENT or bits > MAX_BITS:
                raise self._oops_line(
                    line, *exponent_too_large_message(right, bits))
        try:
            result = apply_binary(op, left, right)
        except TypeError as exc:
            raise self._oops_line(
                line,
                f"Operesheni '{op}' haiwezi kutumika kwa "
                f"{type_name(left)} na {type_name(right)}: {exc}",
                f"Operator '{op}' cannot be applied to "
                f"{type_name(left)} and {type_name(right)}: {exc}") from None
        except ZeroDivisionError:
            raise self._oops_line(line, "Ugawanyaji wa sifuri haiwezekani",
                                  "Division by zero") from None
        frame.stack.append(result)

    def _compare(self, frame: Frame, op: str, line: int) -> None:
        right = frame.stack.pop()
        left = frame.stack.pop()
        try:
            result = compare(op, left, right)
        except (TypeError, ValueError):
            raise self._oops_line(
                line,
                f"Hawezi kulinganisha {type_name(left)} na {type_name(right)}",
                f"Cannot compare {type_name(left)} with {type_name(right)}") from None
        frame.stack.append(result)

    def _subscript(self, frame: Frame, line: int) -> None:
        key = frame.stack.pop()
        holder = frame.stack.pop()
        try:
            result = holder[key]
        except IndexError:
            raise self._oops_line(line, f"Indexi {key} iko nje ya mpaka",
                                  f"Index {key} is out of range") from None
        except KeyError:
            available = (f"Fun guo zilizoopo: {list(holder)[:8]}"
                         if isinstance(holder, dict) else "")
            raise self._oops_line(line, f"Hamna funguo la '{key}'",
                                  f"No such key: '{key}'", available) from None
        except TypeError as exc:
            raise self._oops_line(line, str(exc), str(exc)) from None
        frame.stack.append(result)

    def _store_subscript(self, frame: Frame, line: int) -> None:
        key = frame.stack.pop()
        holder = frame.stack.pop()
        value = frame.stack.pop()
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
            raise self._oops_line(line, str(exc), str(exc)) from None

    def _slice(self, frame: Frame, line: int) -> None:
        stop = frame.stack.pop()
        start = frame.stack.pop()
        holder = frame.stack.pop()
        try:
            frame.stack.append(holder[start:stop])
        except TypeError as exc:
            raise self._oops_line(line, str(exc), str(exc)) from None

    def _store_member(self, frame: Frame, name: str, line: int) -> None:
        holder = frame.stack.pop()
        value = frame.stack.pop()
        if isinstance(holder, SwahiliInstance):
            holder.fields[name] = value
            return
        raise self._oops_line(
            line, f"{type_name(holder)} haina sehemu '{name}'",
            f"{type_name(holder)} has no property '{name}'")

    def get_member(self, node, holder: Any, name: str) -> Any:
        result = super().get_member(node, holder, name)
        if (isinstance(result, BoundMethod)
                and not isinstance(result, CompiledBoundMethod)
                and isinstance(result.function, CompiledFunction)):
            return CompiledBoundMethod(result.function, result.instance,
                                       result.owner)
        return result

    # --- calls, functions and classes -------------------------------------

    def _pop_call_args(self, frame: Frame, count: int, kw_names_index: Any
                       ) -> tuple[list[Any], dict[str, Any]]:
        names: tuple[str, ...] = ()
        if kw_names_index is not None:
            names = tuple(frame.code.constants[kw_names_index])
        values = [frame.stack.pop() for _ in names]
        values.reverse()
        kwargs: dict[str, Any] = dict(zip(names, values))
        args = [frame.stack.pop() for _ in range(count)]
        args.reverse()
        return args, kwargs

    def _call(self, frame: Frame, count: int, kw_names_index: Any,
              line: int) -> None:
        args, kwargs = self._pop_call_args(frame, count, kw_names_index)
        callee = frame.stack.pop()
        frame.stack.append(self._invoke_value(callee, args, kwargs, line))

    def _invoke_value(self, fn: Any, args: list[Any], kwargs: dict[str, Any],
                      line: int, self_instance: Any = None,
                      owner: SwahiliClass | None = None) -> Any:
        if self.depth >= MAX_DEPTH:
            raise RuntimeErr(
                f"Mzunguko umefika kina {MAX_DEPTH} — pengo au mzunguko?",
                f"Recursion limit of {MAX_DEPTH} reached — infinite loop?",
                line=line)
        try:
            if isinstance(fn, NativeFunction):
                if fn.needs_interp:
                    return fn(self, *args, **kwargs)
                return fn(*args, **kwargs)

            if isinstance(fn, CompiledBoundMethod):
                return self._call_compiled(
                    fn.function, args, kwargs, line,
                    self_instance=fn.instance, owner=fn.owner)

            if isinstance(fn, CompiledFunction):
                return self._call_compiled(
                    fn, args, kwargs, line,
                    self_instance=self_instance, owner=owner)

            if isinstance(fn, BoundMethod):
                local = Environment(fn.function.closure)
                local.define("mwenyewe", fn.instance)
                return self._run_function(fn.function, local, args, kwargs,
                                          _LineNode(line),
                                          self_instance=fn.instance,
                                          owner=fn.owner)

            if isinstance(fn, SwahiliFunction):
                local = Environment(fn.closure)
                return self._run_function(fn, local, args, kwargs,
                                          _LineNode(line))

            if callable(fn):
                return fn(*args, **kwargs)
        except (KiswahiliError, Rudeia, Vunja, Endelea):
            raise
        except TypeError as exc:
            raise self._oops_line(line, f"Agizo lisilo sahihi: {exc}",
                                  f"Bad call: {exc}") from None
        except RecursionError:
            raise self._oops_line(line, "Mzunguko umerefuka sana",
                                  "Recursion went too deep",
                                  "Je, kazi inayoitisha yenyewe inakoseka "
                                  "kuimalisha?") from None
        raise self._oops_line(line, f"{type_name(fn)} siwezi kuwekwa wazi",
                              f"{type_name(fn)} is not callable")

    def _eval_thunk(self, code: CodeObject, closure: Environment) -> Any:
        try:
            self._execute_frame(Frame(code, closure, [], []))
        except Rudeia as result:
            return result.args[0] if result.args else None
        return None

    def _call_compiled(self, fn: CompiledFunction, args: list[Any],
                       kwargs: dict[str, Any], line: int,
                       self_instance: Any = None,
                       owner: SwahiliClass | None = None) -> Any:
        params = fn.param_names
        if len(args) > len(params):
            raise self._oops_line(
                line,
                f"Kazi '{fn.name}' inapenda {len(params)} vigezo, "
                f"ulitoa {len(args)}",
                f"'{fn.name}' takes {len(params)} argument(s) but got {len(args)}")

        local = Environment(fn.closure)
        remaining = dict(kwargs)
        for index, name in enumerate(params):
            if index < len(args):
                if name in remaining:
                    raise self._oops_line(
                        line, f"Ugizo wa '{name}' ulirudiwa",
                        f"Duplicate argument '{name}'")
                value = args[index]
            elif name in remaining:
                value = remaining.pop(name)
            elif fn.defaults[index] is not None:
                value = self._eval_thunk(fn.defaults[index], fn.closure)
            else:
                raise self._oops_line(
                    line,
                    f"Kazi '{fn.name}' inahitaji vigezo '{name}'",
                    f"'{fn.name}' is missing required argument '{name}'")

            hint = fn.param_hints[index]
            if hint:
                value = self._coerce(_LineNode(line), value, hint)
            local.define(name, value)

        if remaining:
            extra = ", ".join(sorted(remaining))
            raise self._oops_line(
                line,
                f"Kazi '{fn.name}' haijui vigezo: {extra}",
                f"'{fn.name}' got unexpected argument(s): {extra}")

        if self_instance is not None:
            local.define("mwenyewe", self_instance)
        if self_instance is not None and owner is not None \
                and owner.parent is not None:
            local.define("mzazi", SuperProxy(self_instance, owner.parent))

        self.depth += 1
        try:
            self._execute_frame(Frame(fn.code, local, [], []))
        except Rudeia as result:
            return result.args[0] if result.args else None
        finally:
            self.depth -= 1
        return None

    def _make_class(self, frame: Frame, spec_index: int, line: int) -> None:
        spec: ClassSpec = frame.code.constants[spec_index]
        parent = frame.stack.pop()
        if parent is not None and not isinstance(parent, SwahiliClass):
            raise self._oops_line(line, f"'{spec.parent}' siyo darasa",
                                  f"'{spec.parent}' is not a class")
        cls = CompiledClass(spec, frame.scope, parent)
        frame.scope.define(spec.name, cls)
        class_scope = Environment(frame.scope)
        try:
            self._execute_frame(Frame(spec.body, class_scope, [], []))
        except Rudeia:
            pass
        for name, value in class_scope.vars.items():
            if isinstance(value, SwahiliFunction):
                cls.methods[name] = value
        frame.stack.append(cls)

    def _new_instance(self, frame: Frame, count: int, kw_names_index: Any,
                      name_index: int, line: int) -> None:
        args, kwargs = self._pop_call_args(frame, count, kw_names_index)
        cls = frame.stack.pop()
        class_name = frame.code.constants[name_index]
        if not isinstance(cls, SwahiliClass):
            raise self._oops_line(line, f"Hamna darasa jina la '{class_name}'",
                                  f"No class named '{class_name}'")
        instance = SwahiliInstance(cls)
        for owner in reversed(cls.lineage()):
            defaults = getattr(owner, "defaults", {}) or {}
            for field_name, thunk in defaults.items():
                if field_name in instance.fields and isinstance(thunk, CodeObject):
                    instance.fields[field_name] = self._eval_thunk(
                        thunk, owner.closure)
        constructor, owner = cls.find_constructor()
        if constructor is not None:
            self._invoke_value(constructor, args, kwargs, line,
                               self_instance=instance, owner=owner)
        elif args or kwargs:
            names = ", ".join(
                name for item in cls.lineage() for name in item.methods
            ) or "hakuna"
            raise self._oops_line(
                line,
                f"Darasa '{cls.name}' haina mjenzi (kazi '{cls.name}')",
                f"Class '{cls.name}' has no constructor "
                f"(a method named '{cls.name}')",
                f"METHODS: {names}. Tengeneza kazi {cls.name}(...) "
                f"ndani ya darasa.")
        frame.stack.append(instance)

    # --- modules -----------------------------------------------------------

    def _import(self, frame: Frame, module_index: int, alias_index: Any,
                is_path: bool, line: int) -> None:
        module_name = frame.code.constants[module_index]
        alias = (None if alias_index is None
                 else frame.code.constants[alias_index])
        node = _LineNode(line)
        if is_path:
            module = self.load_module_path(module_name, node)
            binding = alias or os.path.splitext(
                os.path.basename(module_name))[0]
        else:
            module = self.load_module(module_name, node)
            binding = alias or module_name
        frame.scope.define(binding, module)

    def load_module_path(self, path: str, node=None) -> KiswahiliModule:
        base = path
        if not os.path.isabs(base):
            base = os.path.join(self._current_dir(), base)
        full = os.path.abspath(base)
        if not self._fs_allowed(full):
            raise self._oops(node,
                             "Faili hii iko nje ya folda zilizoruhusiwa",
                             "This file is outside the allowed folders")
        if full in self.modules:
            return self.modules[full]
        if not os.path.isfile(full):
            raise self._oops(node, f"Hakuna faili: {path}",
                             f"No such file: {path}")
        name = os.path.splitext(os.path.basename(full))[0]
        with open(full, "r", encoding="utf-8") as handle:
            source = handle.read()
        module_env = Environment(self.builtin_env)
        self.search_paths.insert(0, os.path.dirname(full))
        try:
            self.run_source(source, full, module_env)
        finally:
            self.search_paths.pop(0)
        module = KiswahiliModule(name, dict(module_env.vars))
        self.modules[full] = module
        return module

    def load_module(self, name: str, node=None) -> KiswahiliModule:
        if name in self.modules:
            return self.modules[name]
        if name in self.denied_modules:
            raise self._oops(
                node,
                f"Moduli '{name}' imezuiwa katika hali ya sandbox",
                f"Module '{name}' is blocked in sandbox mode",
                "Ondoa `--sandbox` ikiwa unaamini programu hii. / "
                "Remove `--sandbox` if you trust this program.")
        builtin = _load_builtin_module(self, name)
        if builtin is not None:
            self.modules[name] = builtin
            return builtin
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
        raise self._oops(
            node,
            f"Hakuna moduli jina la '{name}'",
            f"No module named '{name}'",
            f" searching: {', '.join(self.search_paths) or 'script folder'}"
            f" and {spec}")
