"""Kiswahili — a general-purpose programming language in Kiswahili.

    from swahili import Interpreter
    interp = Interpreter()
    interp.run_source('andika "Habari yako, dunia!"')
"""

from .errors import KiswahiliError, Kosa, LexError, ParseError, RuntimeErr
from .interpreter import Interpreter
from .lexer import tokenize
from .parser import parse

__version__ = "0.1.0"
__all__ = [
    "Interpreter", "KiswahiliError", "Kosa", "LexError", "ParseError",
    "RuntimeErr", "tokenize", "parse", "__version__",
]