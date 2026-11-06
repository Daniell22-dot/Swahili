from swahili import Interpreter, parse

src = 'darasa Mwalimu {\n    jina\n    somo\n}'

# Monkey-patch
original = Interpreter._exec_class_def

def debug_cls(self, node, env):
    print(f"  _exec_class_def: node.name={node.name}, env.vars before={len(env.vars)}")
    result = original(self, node, env)
    print(f"  After _exec_class_def: env.vars after={len(env.vars)}")
    return result

Interpreter._exec_class_def = debug_cls

interp = Interpreter()
interp.run_source(src, 'test.kisw')
print('Final globals vars:', list(interp.globals.vars.keys()))
PYEOF