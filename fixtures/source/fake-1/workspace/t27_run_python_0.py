import json
with open("artifacts/t21_check_mask_0.json") as f:
    print(f.read()[:4000])
# also stats for flag
with open("artifacts/t25_segment_stats_0.json") as f:
    import json as j
    st=j.load(f)
    print(st[0])
    print(st[10] if len(st)>10 else "")
