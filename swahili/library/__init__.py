"""Library — built-ins and importable modules.

    builtins.py  global built-ins and value methods
    modules.py   modules available through `tumia`
"""

from .builtins import install
from .modules import MODULES

__all__ = ["install", "MODULES"]
