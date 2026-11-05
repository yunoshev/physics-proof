from helpers import masks_io
import json
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
# create single-frame ref files
masks_io.save_masks('workspace/ref_bp.npz', {'bp': {250: bp[250]}})
masks_io.save_masks('workspace/ref_person.npz', {'person': {205: full[205]}})
print('saved')
# verify
print(masks_io.load_masks('workspace/ref_bp.npz').keys())
print(masks_io.load_masks('workspace/ref_person.npz').keys())
print(open('artifacts/t22_check_mask_0.json').read()[:2000])
print('---')
print(open('artifacts/t28_check_mask_0.json').read()[:2000])
