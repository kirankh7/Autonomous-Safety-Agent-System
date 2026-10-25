import json, sys
nb = json.load(open(sys.argv[1]))
g = {"__name__": "__main__"}
for i in map(int, sys.argv[2].split(",")):
    print(f"\n######## cell {i} ########")
    exec("".join(nb["cells"][i]["source"]), g)
