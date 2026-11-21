"""Kiswahili bytecode frontend: AST -> code objects -> artifacts."""

from .code import (Artifact, ClassSpec, CodeObject, EXTENSION, FunctionSpec,
                   Instruction, disassemble, output_path_for)
from .compiler import Compiler, compile_ast, compile_source
from .opcode import Opcode, opcode_name

__all__ = [
    "Artifact",
    "ClassSpec",
    "CodeObject",
    "Compiler",
    "EXTENSION",
    "FunctionSpec",
    "Instruction",
    "Opcode",
    "compile_ast",
    "compile_source",
    "disassemble",
    "opcode_name",
    "output_path_for",
]
