import json
with open("artifacts/t21_check_mask_0.json") as f:
    d=json.load(f)
print(d["alternatives"])
with open("artifacts/t42_check_mask_0.json") as f:
    d2=json.load(f)
print(d2["alternatives"])
print(d2["coverage_answer"])
with open("workspace/calc.json") as f:
    c=json.load(f)
print(c["e_fig"], c["e_pack"])
