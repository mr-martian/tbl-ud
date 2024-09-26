#!/usr/bin/env python3

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('conllu')
parser.add_argument('rel')
parser.add_argument('norel')
parser.add_argument('--max', '-m', type=int, default=None)
args = parser.parse_args()

with open(args.conllu) as fin, open(args.rel, 'w') as frel, open(args.norel, 'w') as fnorel:
    for i, block in enumerate(fin.read().split('\n\n')):
        if i == args.max:
            break
        for line in block.splitlines():
            cols = line.strip().split('\t')
            if len(cols) != 10:
                continue
            if not cols[0].isdigit():
                continue
            wid = (i+1)*1000 + int(cols[0])
            out = f'"<{cols[1]}>"\n\t"{cols[2]}" tgt:{cols[3]} WID:{wid}'
            if cols[5] != '_':
                out += ' tgt:' + cols[5].replace('|', ' tgt:')
            frel.write(f'{out} #{cols[0]}->{cols[0]}\n')
            fnorel.write(f'{out} @{cols[7]} #{cols[0]}->{cols[6]}\n')
        frel.write('\n')
        fnorel.write('\n')