import json
for p in ["artifacts/t15_web_search_0.json","artifacts/t15_web_search_1.json","artifacts/t16_web_search_0.json","artifacts/t16_web_search_1.json"]:
    print("==", p)
    try:
        with open(p) as f:
            d=json.load(f)
            print(str(d)[:3000])
    except Exception as e:
        print(e)
