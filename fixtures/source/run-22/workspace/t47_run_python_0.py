import json
for p in ["artifacts/t45_check_mask_0.json","artifacts/t46_check_mask_0.json"]:
    with open(p) as f:
        d=json.load(f)
    print(p)
    print(json.dumps(d, indent=2)[:3000])
    print("---")
