import json
for p in ["artifacts/t45_check_mask_0.json","artifacts/t46_check_mask_0.json"]:
    with open(p) as f:
        d=json.load(f)
    print("FILE",p)
    print("coverage:", repr(d["coverage_answer"]))
    print("alternatives:")
    for a in d.get("alternatives",[]):
        print(" -", repr(a))
    print()
