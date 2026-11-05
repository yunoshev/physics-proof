from helpers import masks_io
import json
facts=masks_io.clip_facts("input/timing.json")
print(facts["frame_count"], facts["measured_fps"], facts["duration_s"])
print("dups:", facts["duplicate_runs"][:5])
print("cuts:", facts["cut_indices"][:10])
print("t0-5:", facts["timestamps"][:5].tolist())
print("t_last5:", facts["timestamps"][-5:].tolist())
# also try to list input dir via open? use python import os with relative?
import pathlib, os
# list via glob without getcwd?
import glob
print(glob.glob("input/*"))
print(glob.glob("artifacts/*")[:10])
