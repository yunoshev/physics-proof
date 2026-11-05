from helpers import masks_io
import json, os
facts=masks_io.clip_facts("input/timing.json")
print(facts["frame_count"], facts["measured_fps"])
print("dups", facts["duplicate_runs"][:5])
print("cuts", facts["cut_indices"][:10])
print("t0-5", facts["timestamps"][:5].tolist() if hasattr(facts["timestamps"],"tolist") else facts["timestamps"][:5])
import numpy as np
ts=facts["timestamps"]
print("dur", float(ts[-1]-ts[0]), "n", len(ts))
# list dir
import pathlib
print(os.listdir("input"))
