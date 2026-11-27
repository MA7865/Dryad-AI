import collections
import json

d = json.load(open("data/processed/m1_seasonal_history.json"))
for i, f in enumerate(d["frames"]):
    c = collections.Counter(p["data_quality"][i] for p in d["patches"].values())
    print(f["id"], dict(c))
    