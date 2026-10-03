from swahili.lexer import tokenize

lines = [
    'andika f"fibo(12) = {fibo(12)}"',
    'andika f"i = {i}"',
    'andika f"namba: {n}"',
    'rudia kazi(x) { rudia f"{x} kwenye {kiwango}" }',
]
for line in lines:
    try:
        tokens = tokenize(line + "\n")
        print("OK  ", line, "->", tokens)
    except Exception as exc:
        print("FAIL", line, "->", exc.swahili)