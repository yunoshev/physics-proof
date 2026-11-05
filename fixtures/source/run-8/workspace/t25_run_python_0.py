import os, json
# try to read helpers to understand scale validation
try:
    print(open('src/helpers/scale.py').read()[:3000])
except Exception as e:
    print('no scale.py', e)
try:
    import helpers
    print(dir(helpers))
except Exception as e:
    print(e)
# list artifacts
import pathlib
for p in pathlib.Path('artifacts').glob('*'):
    print(p.name)
