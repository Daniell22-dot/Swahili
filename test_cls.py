from swahili import Interpreter, parse

src = 'darasa A { x = 1 }\nandika 1'
interp = Interpreter()
interp.run_source(src, 'test.kisw')
print('A in globals:', interp.globals.has('A'))
print('Globals vars:', list(interp.globals.vars.keys()))
PYEOF