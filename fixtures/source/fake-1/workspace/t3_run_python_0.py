from helpers import masks_io
facts=masks_io.clip_facts("input/timing.json")
print(facts["frame_count"], facts["measured_fps"])
print(list(facts["timestamps"][:10]))
print(list(facts["timestamps"][-10:]))
print("dups", facts["duplicate_runs"])
print("cuts", facts["cut_indices"])
