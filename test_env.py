from swahili.runtime import Environment

env = Environment()
env.define('A', 'test_value')
print('A in env:', env.has('A'))
print('A value:', env.get('A'))
PYEOF