"""Kiswahili — a general-purpose programming language in Kiswahili.

    from swahili import Interpreter
    interp = Interpreter()
    interp.run_source('andika "Habari yako, dunia!"')

The same frontend also feeds a bytecode compiler and virtual machine:

    from swahili import VM, compile_source
    vm = VM()
    vm.run_code(compile_source('andika "Habari"'))
"""

from .errors import KiswahiliError, Kosa, LexError, ParseError, RuntimeErr
from .runtime import Interpreter, VM
from .frontend import tokenize, parse
from .compiler import (Artifact, CodeObject, compile_ast, compile_source,
                       disassemble)

__version__ = "0.1.0"
__all__ = [
    "Interpreter", "VM", "KiswahiliError", "Kosa", "LexError", "ParseError",
    "RuntimeErr", "tokenize", "parse", "Artifact", "CodeObject",
    "compile_ast", "compile_source", "disassemble", "__version__",
]
