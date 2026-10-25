import json, sys, io, contextlib
nb = json.load(open(sys.argv[1])); g = {}
exec("".join(nb["cells"][49]["source"]), g)
src = "".join(nb["cells"][51]["source"])
for n, th in [(20,2),(20,10),(50,2),(1,2)]:
    s = src.replace("num_operations = 20", f"num_operations = {n}").replace("vocab_threshold = 2", f"vocab_threshold = {th}")
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        exec(s, dict(g))
    lines = out.getvalue().splitlines()
    pick = [l for l in lines if l.startswith(("Vocab size", "Tokens", "Segmented: I"))]
    print(f"--- ops={n} threshold={th}"); print("\n".join(pick))
