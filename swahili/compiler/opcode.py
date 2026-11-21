"""Bytecode operation codes for the Kiswahili virtual machine.

Opcodes are deliberately small and explicit.  An instruction carries at most
two operands; anything larger (names, nested functions, class bodies) lives in
a code object's constant table and is referenced by index.
"""

from __future__ import annotations

from enum import IntEnum, unique


@unique
class Opcode(IntEnum):
    NOP = 0

    LOAD_CONST = 1
    LOAD_NONE = 2
    LOAD_TRUE = 3
    LOAD_FALSE = 4
    LOAD_NAME = 5
    LOAD_FUNC_REF = 6
    DEFINE_NAME = 7
    STORE_NAME = 8

    POP = 9
    DUP = 10

    BUILD_LIST = 20
    BUILD_DICT = 21
    BUILD_RANGE = 22
    BUILD_STRING = 23
    FORMAT_VALUE = 24
    MAKE_ITERATOR = 25
    FOR_NEXT = 26

    UNARY_NEGATIVE = 30
    UNARY_POSITIVE = 31
    UNARY_NOT = 32
    TO_BOOL = 33
    BINARY_OP = 34
    COMPARE_OP = 35
    BINARY_SUBSCR = 36
    STORE_SUBSCR = 37
    SLICE = 38
    LOAD_MEMBER = 39
    STORE_MEMBER = 40
    COERCE = 41

    JUMP_FORWARD = 50
    JUMP_ABSOLUTE = 51
    JUMP_IF_FALSE = 52
    JUMP_IF_TRUE = 53

    RETURN_VALUE = 60
    CALL_FUNCTION = 61
    MAKE_FUNCTION = 62
    MAKE_CLASS = 63
    NEW_INSTANCE = 64
    IMPORT_NAME = 65
    RAISE = 66
    DEBUGGER = 67
    LOAD_CLASS_NAME = 68

    SETUP_LOOP = 70
    SETUP_TRY = 71
    DISABLE_HANDLER = 72
    POP_BLOCK = 73
    PUSH_FINALLY = 74
    END_FINALLY = 75
    BREAK = 76
    CONTINUE = 77


NAME_BY_OP = {op.value: op.name for op in Opcode}

OPERAND_CONSTANT_OPS = {
    Opcode.LOAD_CONST, Opcode.LOAD_NAME, Opcode.LOAD_FUNC_REF,
    Opcode.LOAD_CLASS_NAME, Opcode.DEFINE_NAME, Opcode.STORE_NAME, Opcode.BINARY_OP,
    Opcode.COMPARE_OP, Opcode.LOAD_MEMBER, Opcode.STORE_MEMBER,
    Opcode.COERCE, Opcode.MAKE_FUNCTION, Opcode.MAKE_CLASS,
    Opcode.NEW_INSTANCE, Opcode.IMPORT_NAME,
}

NAME_OPERAND_OPS = {
    Opcode.LOAD_NAME, Opcode.LOAD_FUNC_REF, Opcode.LOAD_CLASS_NAME,
    Opcode.DEFINE_NAME, Opcode.STORE_NAME, Opcode.LOAD_MEMBER,
    Opcode.STORE_MEMBER, Opcode.COERCE,
}


def opcode_name(value: int) -> str:
    return NAME_BY_OP.get(int(value), f"<{value}>")
