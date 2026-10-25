import json, sys, io, contextlib
nb = json.load(open(sys.argv[1])); g = {}
exec("".join(nb["cells"][49]["source"]), g)
T = """
the cat was cleaner than a dog and the bird was higher than a cow.
he found a cat and a dog in the barn.
an egg is smaller than another ant.
the dog howled at the moon.
he threw a ball at he.
"""
I = "the farmer and another hunter wandered in the thundering rain"
for n, th in [(20,3),(20,5),(20,6)]:
    with contextlib.redirect_stderr(io.StringIO()):
        codes, seg = g["snmt_learn_bpe"](T, n)
    vocab = g["snmt_get_vocab"](seg)
    app = g["snmt_apply_bpe"](I, codes, vocab=vocab, vocab_threshold=th)
    print(f"ops={n} thr={th}: merges={len(codes.splitlines())-1} vocab={len(vocab)} train_tokens={len(seg.split())} input_tokens={len(app.split())}\n  codes={codes.splitlines()[1:]}\n  input={app}")
