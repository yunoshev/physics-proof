from helpers import masks_io
import json
facts=masks_io.clip_facts('input/timing.json')
print(facts['frame_count'], facts['measured_fps'], facts['duration_s'])
print('dups', facts['duplicate_runs'][:5])
print('cuts', facts['cut_indices'][:10])
print('ts0', facts['timestamps'][:5], 'ts_end', facts['timestamps'][-5:])
# also try to get video info via masks_io? just print facts keys
print(list(facts.keys()))
