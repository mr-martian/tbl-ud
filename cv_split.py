#!/usr/bin/env python3

import argparse
import json
import os
import struct

parser = argparse.ArgumentParser('split CG binary input corpus into sections for cross-validation')
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('out_dir')
parser.add_argument('--folds', type=int, default=5)
parser.add_argument('--skip_windows', action='store')
args = parser.parse_args()

SKIP = set()
if args.skip_windows:
    with open(args.skip_windows) as fin:
        SKIP = set(json.loads(fin.read()))

os.makedirs(args.out_dir, exist_ok=True)

with open(args.source, 'rb') as fin:
    source = fin.read()

with open(args.target, 'rb') as fin:
    target = fin.read()

folds = []
for i in range(args.folds):
    ls = []
    for partition in ['train', 'test']:
        for side in ['source', 'target']:
            p = os.path.join(args.out_dir, f'{side}.{partition}.{i}.bin')
            f = open(p, 'wb')
            f.write(source[:8])
            ls.append(f)
    folds.append(ls)

def blocks(buf):
    i = 8
    n = 0
    while i < len(buf):
        spec = buf[i]
        i += 1
        if spec == 1:
            ln = struct.unpack('<I', buf[i:i+4])[0]
            if n not in SKIP:
                yield buf[i-1:i+4+ln]
            n += 1
            i += 4 + ln
        elif spec == 2:
            i += 1
        elif spec == 3:
            ln = struct.unpack('<I', buf[i:i+2])[0]
            i += 2 + ln

for i, (sb, tb) in enumerate(zip(blocks(source), blocks(target))):
    for j, ls in enumerate(folds):
        if i % args.folds == j:
            ls[2].write(sb)
            ls[3].write(tb)
        else:
            ls[0].write(sb)
            ls[1].write(tb)

for ls in folds:
    for f in ls:
        f.close()
