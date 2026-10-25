import json, sys
path = sys.argv[1]
nb = json.load(open(path))
ANS = """### My answers (draft: compare against your own observations from the live session)

**Q1 (prediction):** Frequent character pairs in the training text should get merged first: `th`, `an`, `er`, then whole common words like `the`, `and`, `than`, `dog`, `cat`.

**Q2 (observed):** With 20 ops the vocab has complete words `the`, `a`, `and`, `than`, `dog`, `cat`, `was`, `at`, `he` and subwords `th@@`, `an@@`, `er`, `le@@`, `ow@@`, `ba@@`. That matches the prediction. Rare words (`bird`, `smaller`, `found`) stay split into single characters.

**3a (50 ops):** Nothing changes compared with 20. Learning stopped after 18 merges ("no pair has frequency >= 2. Stopping"), so the vocab stays at 41 tokens.

**3b (1 op):** Only one merge is learned (`t h`). Almost everything stays a single character: 142 training tokens, 32 vocab entries, mostly `x@@` fragments.

**3c (why):** Each operation merges the single most frequent adjacent pair. More ops means more and longer subwords, until no pair occurs at least twice. That is why 50 behaves like 18. Fewer ops leaves text close to character level.

**3d (why a limit):** Running merges until nothing repeats overfits to the training text: you get whole-word tokens for everything frequent and no reusable pieces. A fixed budget controls vocabulary size (memory, embedding table) and keeps reusable subwords, so new or out-of-vocabulary words like `farmer` and `hunter` can still be built from pieces (`er`, `an@@`, `th@@`).

**3e (codes):** `codes` is an ordered list of merges (`t h`, `th e</w>`, `a n`, ...), one new line per op. It is the same idea as the byte-pair table from the BPE exercise (a new symbol = left code + right code), except it merges characters into readable subwords instead of replacing pairs with unused bytes. `</w>` marks the end of a word.

**4a (threshold 10):** In this setup the token count does not change. Every token appears fewer than 10 times (the max is 5), so the filtered vocab is empty, and subword-nmt skips filtering when the vocab is empty. With threshold 3 the input goes from 39 to 42 tokens, and with 5 it goes to 48 (character level).

**4b (why):** When a vocab is given, merges that produce tokens rarer than the threshold get reverted (split back into smaller units), so you get more, shorter tokens. Rare subwords are unreliable to learn, so they get backed off to more common pieces.
"""
cell = {"cell_type": "markdown", "metadata": {}, "source": ANS.splitlines(keepends=True)}
assert "TRAIN_TEXT" in "".join(nb["cells"][51]["source"])
nb["cells"].insert(52, cell)
json.dump(nb, open(path, "w"), indent=1, ensure_ascii=False)
