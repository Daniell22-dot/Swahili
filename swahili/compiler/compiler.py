"""The Kiswahili bytecode compiler.

The compiler consumes the same AST as the tree-walking interpreter and lowers
it to a stack bytecode program.  It performs no source generation and has no
third-party dependencies; code objects and artifacts are defined in `code.py`.
"""

from __future__ import annotations

from typing import Any

from ..frontend import ast
from .code import ClassSpec, CodeObject, FunctionSpec
from .opcode import Opcode


class Compiler:
    """Compile one AST scope into one :class:`CodeObject`."""

    def __init__(self, name: str, filename: str, source: str, line: int = 0):
        self.code = CodeObject(name, filename, source)
        self.line = line
        self._strings: dict[str, int] = {}

    # --- helpers ------------------------------------------------------------

    def _line_of(self, node: ast.Node | None) -> int:
        if node is not None:
            return getattr(node, "line", 0) or self.line
        return self.line

    def _emit(self, op: Opcode, arg: Any = 0, arg2: Any = None,
              arg3: Any = None, node: ast.Node | None = None) -> int:
        return self.code.emit(
            op, arg, arg2, arg3, self._line_of(node),
            getattr(node, "column", 0) if node is not None else 0,
            getattr(node, "index", 0) if node is not None else 0)

    def _const(self, value: Any) -> int:
        return self.code.constant(value)

    def _str(self, value: str) -> int:
        if value not in self._strings:
            self._strings[value] = self._const(value)
        return self._strings[value]

    def _here(self) -> int:
        return len(self.code.instructions)

    def _child(self, name: str, node: ast.Node | None = None) -> "Compiler":
        return Compiler(name, self.code.filename, self.code.source,
                        self._line_of(node))

    def _finish(self) -> CodeObject:
        self._emit(Opcode.LOAD_NONE)
        self._emit(Opcode.RETURN_VALUE)
        return self.code

    # --- entry point --------------------------------------------------------

    def compile_program(self, program: ast.Program) -> CodeObject:
        self._statements(program.body)
        return self._finish()

    def _statements(self, body: list[ast.Node]) -> None:
        for statement in body:
            self._statement(statement)

    # --- statements ---------------------------------------------------------

    def _statement(self, node: ast.Node) -> None:
        previous = self.line
        self.line = self._line_of(node)
        try:
            handler = getattr(self, f"_stmt_{type(node).__name__}", None)
            if handler is None:
                self._expr(node)
                self._emit(Opcode.POP)
            else:
                handler(node)
        finally:
            self.line = previous

    def _stmt_Program(self, node: ast.Program) -> None:
        self._statements(node.body)

    def _stmt_Block(self, node: ast.Block) -> None:
        self._statements(node.body)

    def _stmt_Pass(self, node: ast.Pass) -> None:
        self._emit(Opcode.NOP)

    def _stmt_ExprStatement(self, node: ast.ExprStatement) -> None:
        self._expr(node.expr)
        self._emit(Opcode.POP)

    def _stmt_Declaration(self, node: ast.Declaration) -> None:
        if node.value is None:
            self._emit(Opcode.LOAD_NONE)
        else:
            self._expr(node.value)
        if node.type_hint:
            self._emit(Opcode.COERCE, self._str(node.type_hint), node=node)
        self._emit(Opcode.DEFINE_NAME, self._str(node.name), node=node)

    def _assign(self, node: ast.Assign, keep: bool) -> None:
        if node.op == "=":
            self._expr(node.value)
        else:
            self._expr(node.value)
            self._expr(node.target)
            self._emit(Opcode.BINARY_OP, self._str(node.op[:-1]), node=node)

        target = node.target
        if isinstance(target, ast.Name):
            self._emit(Opcode.STORE_NAME, self._str(target.ident), node=node)
        elif isinstance(target, ast.Member):
            self._expr(target.target)
            self._emit(Opcode.STORE_MEMBER, self._str(target.name), node=node)
        elif isinstance(target, ast.Index):
            self._expr(target.target)
            self._expr(target.key)
            self._emit(Opcode.STORE_SUBSCR, node=node)
        else:
            self._emit(Opcode.POP)
            raise ValueError(f"Invalid assignment target: {type(target).__name__}")

        if keep:
            self._expr(target)

    def _stmt_Assign(self, node: ast.Assign) -> None:
        self._assign(node, keep=False)

    def _stmt_If(self, node: ast.If) -> None:
        self._expr(node.test)
        skip = self._emit(Opcode.JUMP_IF_FALSE, -1, node=node)
        self._statement(node.body)
        if node.orelse is None:
            self.code.patch(skip, arg=self._here())
        else:
            end = self._emit(Opcode.JUMP_ABSOLUTE, -1, node=node)
            self.code.patch(skip, arg=self._here())
            self._statement(node.orelse)
            self.code.patch(end, arg=self._here())

    def _stmt_While(self, node: ast.While) -> None:
        setup = self._emit(Opcode.SETUP_LOOP, -1, -1, node=node)
        start = self._here()
        self._expr(node.test)
        if node.until:
            self._emit(Opcode.UNARY_NOT, node=node)
        exit_jump = self._emit(Opcode.JUMP_IF_FALSE, -1, node=node)
        self._statement(node.body)
        self._emit(Opcode.JUMP_ABSOLUTE, start, node=node)
        end = self._here()
        self.code.patch(exit_jump, arg=end)
        self.code.patch(setup, arg=end, arg2=start)
        self._emit(Opcode.POP_BLOCK, node=node)

    def _stmt_ForEach(self, node: ast.ForEach) -> None:
        self._expr(node.iterable)
        self._emit(Opcode.MAKE_ITERATOR, bool(node.yields_pairs), node=node)
        setup = self._emit(Opcode.SETUP_LOOP, -1, -1, node=node)
        start = self._here()
        next_index = self._emit(Opcode.FOR_NEXT, -1, node=node)
        self._emit(Opcode.DEFINE_NAME, self._str(node.name), node=node)
        self._statement(node.body)
        self._emit(Opcode.JUMP_ABSOLUTE, start, node=node)
        end = self._here()
        self.code.patch(next_index, arg=end)
        self.code.patch(setup, arg=end, arg2=start)
        self._emit(Opcode.POP_BLOCK, node=node)
        self._emit(Opcode.POP, node=node)

    def _stmt_Return(self, node: ast.Return) -> None:
        if node.value is None:
            self._emit(Opcode.LOAD_NONE, node=node)
        else:
            self._expr(node.value)
        self._emit(Opcode.RETURN_VALUE, node=node)

    def _stmt_Break(self, node: ast.Break) -> None:
        self._emit(Opcode.BREAK, node=node)

    def _stmt_Continue(self, node: ast.Continue) -> None:
        self._emit(Opcode.CONTINUE, node=node)

    def _stmt_Debugger(self, node: ast.Debugger) -> None:
        self._emit(Opcode.DEBUGGER, node=node)

    def _default_thunk(self, expression: ast.Node | None) -> CodeObject | None:
        if expression is None:
            return None
        child = self._child("<default>", expression)
        child._expr(expression)
        child._emit(Opcode.RETURN_VALUE)
        return child.code

    def _stmt_FuncDef(self, node: ast.FuncDef) -> None:
        child = self._child(node.name, node)
        child._statements(node.body.body)
        spec = FunctionSpec(
            name=node.name,
            code=child._finish(),
            param_names=[p.name for p in node.params],
            param_hints=[p.type_hint for p in node.params],
            defaults=[self._default_thunk(p.default) for p in node.params],
            type_hint=node.type_hint,
            arrow_hint=node.arrow_hint,
        )
        self._emit(Opcode.MAKE_FUNCTION, self._const(spec), node=node)
        self._emit(Opcode.DEFINE_NAME, self._str(node.name), node=node)

    def _stmt_ClassDef(self, node: ast.ClassDef) -> None:
        child = self._child(node.name, node)
        child._statements(node.body.body)
        spec = ClassSpec(
            name=node.name,
            fields=list(node.fields),
            defaults={name: self._default_thunk(expr)
                      for name, expr in node.defaults.items()
                      if expr is not None},
            body=child._finish(),
            parent=node.parent,
        )
        if node.parent:
            self._emit(Opcode.LOAD_CLASS_NAME, self._str(node.parent), node=node)
        else:
            self._emit(Opcode.LOAD_NONE, node=node)
        self._emit(Opcode.MAKE_CLASS, self._const(spec), node=node)
        self._emit(Opcode.DEFINE_NAME, self._str(node.name), node=node)

    def _stmt_Try(self, node: ast.Try) -> None:
        has_handler = node.handler_body is not None
        has_finally = node.finally_body is not None
        setup = self._emit(Opcode.SETUP_TRY, -1,
                           -1 if has_finally else None,
                           has_handler, node=node)

        self._statement(node.body)
        self._emit(Opcode.DISABLE_HANDLER, node=node)
        after_body = self._emit(Opcode.JUMP_ABSOLUTE, -1, node=node)

        handler_target = None
        if has_handler:
            handler_target = self._here()
            if node.handler:
                self._emit(Opcode.DEFINE_NAME, self._str(node.handler), node=node)
            else:
                self._emit(Opcode.POP, node=node)
            self._statement(node.handler_body)
            handler_end = self._emit(Opcode.JUMP_ABSOLUTE, -1, node=node)

        after_handler = self._here()
        self.code.patch(after_body, arg=after_handler)
        if has_handler:
            self.code.patch(handler_end, arg=after_handler)
        self._emit(Opcode.POP_BLOCK, node=node)

        finally_target = None
        if has_finally:
            self._emit(Opcode.PUSH_FINALLY, node=node)
            finally_target = self._here()
            self._statement(node.finally_body)
            self._emit(Opcode.END_FINALLY, node=node)

        self.code.patch(setup, arg=handler_target, arg2=finally_target)

    def _stmt_Import(self, node: ast.Import) -> None:
        alias = node.alias if node.alias is not None else None
        self._emit(Opcode.IMPORT_NAME, self._str(node.module),
                   self._str(alias) if alias else None,
                   bool(node.is_path), node=node)

    # --- expressions --------------------------------------------------------

    def _expr(self, node: ast.Node) -> None:
        previous = self.line
        self.line = self._line_of(node)
        try:
            handler = getattr(self, f"_expr_{type(node).__name__}", None)
            if handler is None:
                raise ValueError(f"Unknown expression node: {type(node).__name__}")
            handler(node)
        finally:
            self.line = previous

    def _expr_Number(self, node: ast.Number) -> None:
        self._emit(Opcode.LOAD_CONST, self._const(node.value), node=node)

    def _expr_Text(self, node: ast.Text) -> None:
        if not node.parts:
            self._emit(Opcode.LOAD_CONST, self._const(node.value), node=node)
            return
        for part in node.parts:
            if isinstance(part, str):
                self._emit(Opcode.LOAD_CONST, self._const(part), node=node)
            else:
                self._expr(part)
                self._emit(Opcode.FORMAT_VALUE, node=node)
        self._emit(Opcode.BUILD_STRING, len(node.parts), node=node)

    def _expr_BoolLit(self, node: ast.BoolLit) -> None:
        self._emit(Opcode.LOAD_TRUE if node.value else Opcode.LOAD_FALSE, node=node)

    def _expr_NoneLit(self, node: ast.NoneLit) -> None:
        self._emit(Opcode.LOAD_NONE, node=node)

    def _expr_ListLit(self, node: ast.ListLit) -> None:
        for element in node.elements:
            self._expr(element)
        self._emit(Opcode.BUILD_LIST, len(node.elements), node=node)

    def _expr_DictLit(self, node: ast.DictLit) -> None:
        for key, value in node.pairs:
            self._expr(key)
            self._expr(value)
        self._emit(Opcode.BUILD_DICT, len(node.pairs), node=node)

    def _expr_RangeLit(self, node: ast.RangeLit) -> None:
        self._expr(node.start)
        self._expr(node.stop)
        if node.step is None:
            self._emit(Opcode.LOAD_CONST, self._const(1), node=node)
        else:
            self._expr(node.step)
        self._emit(Opcode.BUILD_RANGE, node=node)

    def _expr_Name(self, node: ast.Name) -> None:
        self._emit(Opcode.LOAD_NAME, self._str(node.ident), node=node)

    def _expr_FuncRef(self, node: ast.FuncRef) -> None:
        self._emit(Opcode.LOAD_FUNC_REF, self._str(node.ident), node=node)

    def _expr_Grouping(self, node: ast.Grouping) -> None:
        self._expr(node.inner)

    def _expr_Unary(self, node: ast.Unary) -> None:
        self._expr(node.operand)
        op = {"-": Opcode.UNARY_NEGATIVE, "+": Opcode.UNARY_POSITIVE,
              "sio": Opcode.UNARY_NOT}[node.op]
        self._emit(op, node=node)

    def _expr_Binary(self, node: ast.Binary) -> None:
        self._expr(node.left)
        self._expr(node.right)
        self._emit(Opcode.BINARY_OP, self._str(node.op), node=node)

    def _expr_Logical(self, node: ast.Logical) -> None:
        self._expr(node.left)
        self._emit(Opcode.TO_BOOL, node=node)
        if node.op == "na":
            skip_right = self._emit(Opcode.JUMP_IF_FALSE, -1, node=node)
            self._expr(node.right)
            self._emit(Opcode.TO_BOOL, node=node)
            end = self._emit(Opcode.JUMP_ABSOLUTE, -1, node=node)
            self.code.patch(skip_right, arg=self._here())
            self._emit(Opcode.LOAD_FALSE, node=node)
        else:
            skip_right = self._emit(Opcode.JUMP_IF_TRUE, -1, node=node)
            self._expr(node.right)
            self._emit(Opcode.TO_BOOL, node=node)
            end = self._emit(Opcode.JUMP_ABSOLUTE, -1, node=node)
            self.code.patch(skip_right, arg=self._here())
            self._emit(Opcode.LOAD_TRUE, node=node)
        self.code.patch(end, arg=self._here())

    def _expr_Compare(self, node: ast.Compare) -> None:
        self._expr(node.left)
        self._expr(node.right)
        self._emit(Opcode.COMPARE_OP, self._str(node.op), node=node)

    def _expr_Ternary(self, node: ast.Ternary) -> None:
        self._expr(node.test)
        alternate = self._emit(Opcode.JUMP_IF_FALSE, -1, node=node)
        self._expr(node.consequent)
        end = self._emit(Opcode.JUMP_ABSOLUTE, -1, node=node)
        self.code.patch(alternate, arg=self._here())
        self._expr(node.alternate)
        self.code.patch(end, arg=self._here())

    def _expr_Index(self, node: ast.Index) -> None:
        self._expr(node.target)
        self._expr(node.key)
        self._emit(Opcode.BINARY_SUBSCR, node=node)

    def _expr_Slice(self, node: ast.Slice) -> None:
        self._expr(node.target)
        if node.start is None:
            self._emit(Opcode.LOAD_NONE, node=node)
        else:
            self._expr(node.start)
        if node.stop is None:
            self._emit(Opcode.LOAD_NONE, node=node)
        else:
            self._expr(node.stop)
        self._emit(Opcode.SLICE, node=node)

    def _expr_Member(self, node: ast.Member) -> None:
        self._expr(node.target)
        self._emit(Opcode.LOAD_MEMBER, self._str(node.name), node=node)

    def _call_operands(self, node: ast.Call | ast.New) -> tuple[int, Any]:
        for argument in node.args:
            self._expr(argument)
        names = tuple(node.kwargs.keys())
        for name in names:
            self._expr(node.kwargs[name])
        return len(node.args), self._const(names) if names else None

    def _expr_Call(self, node: ast.Call) -> None:
        self._expr(node.callee)
        count, kw_names = self._call_operands(node)
        self._emit(Opcode.CALL_FUNCTION, count, kw_names, node=node)

    def _expr_New(self, node: ast.New) -> None:
        self._emit(Opcode.LOAD_CLASS_NAME, self._str(node.class_name), node=node)
        count, kw_names = self._call_operands(node)
        self._emit(Opcode.NEW_INSTANCE, count, kw_names,
                   self._str(node.class_name), node=node)

    def _expr_Lambda(self, node: ast.Lambda) -> None:
        child = self._child("<kazi>", node)
        child._statements(node.body.body)
        spec = FunctionSpec(
            name="<kazi>",
            code=child._finish(),
            param_names=[p.name for p in node.params],
            param_hints=[p.type_hint for p in node.params],
            defaults=[self._default_thunk(p.default) for p in node.params],
        )
        self._emit(Opcode.MAKE_FUNCTION, self._const(spec), node=node)

    def _expr_Assign(self, node: ast.Assign) -> None:
        self._assign(node, keep=True)

    def _expr_Throw(self, node: ast.Throw) -> None:
        self._expr(node.value)
        self._emit(Opcode.RAISE, node=node)


def compile_ast(program: ast.Program, filename: str = "<kisarifi>",
                source: str = "") -> CodeObject:
    """Lower a parsed program into a bytecode code object."""

    compiler = Compiler("<moduli>", filename, source,
                        getattr(program, "line", 0))
    return compiler.compile_program(program)


def compile_source(source: str, filename: str = "<kisarifi>") -> CodeObject:
    """Parse and compile Kiswahili source text into bytecode."""

    from ..frontend.parser import parse
    return compile_ast(parse(source, filename), filename, source)
