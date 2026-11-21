"""Code objects, compiled artifacts, and a small disassembler.

A :class:`CodeObject` is the unit the VM executes.  It is intentionally
self-contained: instructions refer to constants by index, and the source text
is carried along so runtime diagnostics can show the original line even when
running a compiled artifact later.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, TextIO

from .opcode import Opcode, opcode_name

MAGIC = "KISWILI-BYTECODE"
VERSION = 1
EXTENSION = ".kiswc"


@dataclass
class Instruction:
    op: Opcode
    arg: Any = 0
    arg2: Any = None
    arg3: Any = None
    line: int = 0

    def to_json(self) -> list[Any]:
        return [int(self.op), self.arg, self.arg2, self.arg3, self.line]

    @classmethod
    def from_json(cls, data: list[Any]) -> "Instruction":
        if len(data) == 4:
            return cls(Opcode(data[0]), data[1], data[2], None, data[3])
        return cls(Opcode(data[0]), data[1], data[2], data[3], data[4])


@dataclass
class CodeObject:
    name: str
    filename: str
    source: str
    instructions: list[Instruction] = field(default_factory=list)
    constants: list[Any] = field(default_factory=list)
    first_line: int = 1

    def emit(self, op: Opcode, arg: Any = 0, arg2: Any = None,
             arg3: Any = None, line: int = 0) -> int:
        index = len(self.instructions)
        self.instructions.append(Instruction(op, arg, arg2, arg3, line))
        return index

    def patch(self, index: int, **changes: Any) -> None:
        instruction = self.instructions[index]
        for name, value in changes.items():
            setattr(instruction, name, value)

    def constant(self, value: Any) -> int:
        index = len(self.constants)
        self.constants.append(value)
        return index


@dataclass
class FunctionSpec:
    """Serializable description of a compiled Kiswahili function."""

    name: str
    code: CodeObject
    param_names: list[str]
    param_hints: list[str | None]
    defaults: list[CodeObject | None]
    type_hint: str | None = None
    arrow_hint: str | None = None


@dataclass
class ClassSpec:
    """Serializable description of a compiled `darasa`."""

    name: str
    fields: list[str]
    defaults: dict[str, CodeObject]
    body: CodeObject
    parent: str | None = None


@dataclass
class Artifact:
    version: int
    filename: str
    source: str
    code: CodeObject

    def to_dict(self) -> dict[str, Any]:
        return {
            "magic": MAGIC,
            "version": VERSION,
            "filename": self.filename,
            "source": self.source,
            "code": _code_to_json(self.code),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.to_json())
            handle.write("\n")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        if data.get("magic") != MAGIC:
            raise ValueError("Hii si faili ya bytecode ya Kiswahili / "
                             "Not a Kiswahili bytecode file")
        version = data.get("version")
        if version != VERSION:
            raise ValueError(f"Toleo la bytecode halijulikani: {version} / "
                             f"Unknown bytecode version: {version}")
        return cls(int(version), data["filename"], data["source"],
                   _code_from_json(data["code"]))

    @classmethod
    def from_json(cls, text: str) -> "Artifact":
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: str) -> "Artifact":
        with open(path, "r", encoding="utf-8") as handle:
            return cls.from_json(handle.read())


def _code_to_json(code: CodeObject) -> dict[str, Any]:
    return {
        "name": code.name,
        "filename": code.filename,
        "source": code.source,
        "first_line": code.first_line,
        "instructions": [item.to_json() for item in code.instructions],
        "constants": [_const_to_json(value) for value in code.constants],
    }


def _code_from_json(data: dict[str, Any]) -> CodeObject:
    return CodeObject(
        name=data["name"],
        filename=data["filename"],
        source=data["source"],
        instructions=[Instruction.from_json(item) for item in data["instructions"]],
        constants=[_const_from_json(value) for value in data["constants"]],
        first_line=int(data.get("first_line", 1)),
    )


def _const_to_json(value: Any) -> Any:
    if value is None:
        return {"t": "none"}
    if value is True:
        return {"t": "bool", "v": True}
    if value is False:
        return {"t": "bool", "v": False}
    if isinstance(value, int):
        return {"t": "int", "v": value}
    if isinstance(value, float):
        return {"t": "float", "v": value}
    if isinstance(value, str):
        return {"t": "str", "v": value}
    if isinstance(value, (list, tuple)):
        return {"t": "seq", "v": [_const_to_json(item) for item in value],
                "tuple": isinstance(value, tuple)}
    if isinstance(value, CodeObject):
        return {"t": "code", "v": _code_to_json(value)}
    if isinstance(value, FunctionSpec):
        return {"t": "func", "v": {
            "name": value.name,
            "code": _code_to_json(value.code),
            "param_names": value.param_names,
            "param_hints": value.param_hints,
            "defaults": [None if item is None else _const_to_json(item)
                         for item in value.defaults],
            "type_hint": value.type_hint,
            "arrow_hint": value.arrow_hint,
        }}
    if isinstance(value, ClassSpec):
        return {"t": "class", "v": {
            "name": value.name,
            "fields": value.fields,
            "defaults": {key: _const_to_json(item)
                         for key, item in value.defaults.items()},
            "body": _code_to_json(value.body),
            "parent": value.parent,
        }}
    raise ValueError(f"Haiwezi kuhifadhi kipengee cha bytecode: {type(value).__name__}")


def _const_from_json(data: Any) -> Any:
    tag = data["t"]
    if tag == "none":
        return None
    if tag == "bool":
        return data["v"]
    if tag == "int":
        return int(data["v"])
    if tag == "float":
        return float(data["v"])
    if tag == "str":
        return str(data["v"])
    if tag == "seq":
        items = [_const_from_json(item) for item in data["v"]]
        return tuple(items) if data.get("tuple") else items
    if tag == "code":
        return _code_from_json(data["v"])
    if tag == "func":
        raw = data["v"]
        defaults = [None if item is None else _const_from_json(item)
                    for item in raw["defaults"]]
        return FunctionSpec(
            name=raw["name"],
            code=_code_from_json(raw["code"]),
            param_names=list(raw["param_names"]),
            param_hints=list(raw["param_hints"]),
            defaults=defaults,
            type_hint=raw.get("type_hint"),
            arrow_hint=raw.get("arrow_hint"),
        )
    if tag == "class":
        raw = data["v"]
        return ClassSpec(
            name=raw["name"],
            fields=list(raw["fields"]),
            defaults={key: _const_from_json(item)
                      for key, item in raw["defaults"].items()},
            body=_code_from_json(raw["body"]),
            parent=raw.get("parent"),
        )
    raise ValueError(f"Tag ya bytecode haijulikani: {tag}")


def _operand_text(code: CodeObject, op: Opcode, arg: Any) -> str:
    if arg is None:
        return ""
    if isinstance(arg, Opcode):
        return arg.name
    if op in (Opcode.LOAD_CONST,):
        return repr(code.constants[arg]) if isinstance(arg, int) else repr(arg)
    return repr(arg)


def disassemble(code: CodeObject, out: TextIO | None = None) -> str:
    """Return a readable listing of one code object (and its nested specs)."""

    import io
    stream = out or io.StringIO()
    write = stream.write
    write(f"=== {code.name}  ({code.filename}) ===\n")
    for index, instruction in enumerate(code.instructions):
        op = instruction.op
        parts = [opcode_name(int(op))]
        text = _operand_text(code, op, instruction.arg)
        if text:
            parts.append(text)
        if instruction.arg2 is not None:
            parts.append(_operand_text(code, op, instruction.arg2))
        write(f"{index:>5}  {instruction.line:>4}  {' '.join(parts)}\n")

    for constant in code.constants:
        if isinstance(constant, FunctionSpec):
            write("\n")
            disassemble(constant.code, stream)
        elif isinstance(constant, ClassSpec):
            write("\n")
            disassemble(constant.body, stream)
        elif isinstance(constant, CodeObject):
            write("\n")
            disassemble(constant, stream)

    return stream.getvalue() if out is None else ""


def output_path_for(source_path: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    base = os.path.abspath(source_path)
    root, _ = os.path.splitext(base)
    return root + EXTENSION
