from helpers import masks_io
import json, os
print(os.listdir("input"))
print(os.listdir("."))
facts=masks_io.clip_facts("input/timing.json")
print(facts["frame_count"], facts["measured_fps"])
print("timestamps len", len(facts["timestamps"]))
print(facts["timestamps"][:10])
print(facts["timestamps"][-10:])
print("dups", facts["duplicate_runs"])
print("cuts", facts["cut_indices"])
# also video files
import glob
print(glob.glob("input/*"))
print(glob.glob("artifacts/*")[:20])
