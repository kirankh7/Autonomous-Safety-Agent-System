import json, sys

src, dst = sys.argv[1], sys.argv[2]
nb = json.load(open(src))

BPE = '''from string import ascii_letters, digits, punctuation
from typing import cast, TypedDict

characters = list(ascii_letters + digits + punctuation)

class BytePairTable(TypedDict):
    character: list[str]
    leftcode: list[str]
    rightcode: list[str | int]

def bpe_compression(input_string: str) -> tuple[BytePairTable, str]:
    byte_pair_table = BytePairTable(
        character = characters.copy(),
        leftcode = characters.copy(),
        rightcode = []
    )

    # Initial rightcode set
    for character in byte_pair_table["character"]:
        if character in input_string:
            byte_pair_table["rightcode"].append(1) # 1 = literal (character appears in the input)
        else:
            byte_pair_table["rightcode"].append(0) # 0 = unused, free to stand in for a pair

    buffer = input_string
    most_frequent_pair_value = None

    while most_frequent_pair_value is None or most_frequent_pair_value > 1:
        pair_map: dict[str, int] = {}
        buffer_length = len(buffer)

        for character_index in range(1, buffer_length):
            pair: str = buffer[character_index - 1] + buffer[character_index]

            # Initialize / Increment counter on pair_map
            pair_map[pair] = pair_map.get(pair, 0) + 1

        most_frequent_pair_value: int = max(pair_map.values(), default=0)

        if most_frequent_pair_value > 1:
            most_frequent_pair_key: str = max(pair_map, key=lambda k: pair_map[k])

            # Find new character assignment.
            first_unused_character_index = next((i for i, v in enumerate(byte_pair_table["rightcode"]) if v == 0), None)
            if first_unused_character_index is None:
                # No more unused characters
                return (byte_pair_table, buffer)

            # Update table with character
            byte_pair_table["leftcode"][first_unused_character_index] = most_frequent_pair_key[0]
            byte_pair_table["rightcode"][first_unused_character_index] = most_frequent_pair_key[1]
            replacement_character = byte_pair_table["character"][first_unused_character_index]

            buffer = buffer.replace(most_frequent_pair_key, replacement_character)

    return (byte_pair_table, buffer)

def bpe_expansion(byte_pair_table: BytePairTable, buffer: str) -> str:

    input = list(buffer)
    input.reverse()

    stack: list[str] = []
    output_string = ""

    while len(input) > 0 or len(stack) > 0:
        if len(stack) > 0:
            character = stack.pop()
            character_index = byte_pair_table["character"].index(character)
            leftcode_value = byte_pair_table["leftcode"][character_index]
            rightcode_value = byte_pair_table["rightcode"][character_index]

            if rightcode_value == 1:
                # This means that its a literal
                output_string += leftcode_value

            elif isinstance(rightcode_value, str):
                # If the rightcode_value is string, then its a pair
                # Push right first so the left half is popped (expanded) first
                stack.append(rightcode_value)
                stack.append(leftcode_value)

        else:
            character = input.pop()
            stack.append(character)

    return output_string

if __name__ == "__main__":
    input_string = "ababcabcd"
    print(f"input_string: {input_string}")

    byte_pair_table, buffer = bpe_compression(input_string)
    print(f"buffer: {buffer}")

    output_string = bpe_expansion(byte_pair_table, buffer)
    print(f"output_string: {output_string}")
'''

SNMT = '''TRAIN_TEXT = """
the cat was cleaner than a dog and the bird was higher than a cow.
he found a cat and a dog in the barn.
an egg is smaller than another ant.
the dog howled at the moon.
he threw a ball at he.
"""

INPUT_TEXT = "the farmer and another hunter wandered in the thundering rain"

NUM_OPERATIONS = 20  # Adjust number of operations (try 50, then 1)
VOCAB_THRESHOLD = None  # Question 4: try 10

# Step 1: Learn BPE codes from training text
print("=== Step 1: snmt_learn_bpe ===")
codes, segmented = snmt_learn_bpe(TRAIN_TEXT, num_operations=NUM_OPERATIONS)
print(f"Learned codes:\\n{codes}")
print(f"Segmented: {segmented}")
print(f"Tokens: {len(segmented.split())}")

# Step 2: Get vocabulary from segmented text
print("\\n=== Step 2: snmt_get_vocab ===")
vocab = snmt_get_vocab(segmented)
print(f"Vocabulary: {vocab}")
print(f"Vocab size: {len(vocab)}")

# Step 3: Apply BPE to input text
print("\\n=== Step 3: snmt_apply_bpe ===")
applied = snmt_apply_bpe(INPUT_TEXT, codes, vocab=vocab, vocab_threshold=VOCAB_THRESHOLD)
tokens = applied.split()
complete_tokens = sum(1 for t in tokens if not t.endswith("@@"))
partial_tokens = sum(1 for t in tokens if t.endswith("@@"))
print(f"Input: {INPUT_TEXT}")
print(f"Segmented: {applied}")
print(f"Tokens: {len(tokens)}")
print(f"Complete tokens: {complete_tokens}")
print(f"Partial tokens: {partial_tokens}")
'''

def set_src(i, text, marker):
    cell = nb["cells"][i]
    assert marker in "".join(cell["source"]), f"cell {i} unexpected"
    cell["source"] = text.splitlines(keepends=True)
    cell["outputs"], cell["execution_count"] = [], None

set_src(44, BPE, "def bpe_compression")
set_src(51, SNMT, "TRAIN_TEXT")
json.dump(nb, open(dst, "w"), indent=1, ensure_ascii=False)
print("wrote", dst)
