import argparse
import json
import utils

parser = argparse.ArgumentParser('get CoNLL-U file into same order as recombined jackknife files')
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('--folds', type=int, default=5)
parser.add_argument('--skip_windows', action='store')
parser.add_argument('--skip_fold', type=int, default=-1)
parser.add_argument('--only_fold', type=int, default=-1)
args = parser.parse_args()

SKIP = set()
if args.skip_windows:
    with open(args.skip_windows) as fin:
        SKIP = set(json.loads(fin.read()))

out = [[] for _ in range(args.folds)]
with open(args.source) as fin:
    n = 0
    for i, sent in enumerate(utils.conllu_sentences(fin)):
        if i in SKIP:
            continue
        out[n % args.folds].append(''.join(sent))
        n += 1
with open(args.target, 'w') as fout:
    for i, ls in enumerate(out):
        if i == args.skip_fold:
            continue
        if args.only_fold != -1 and i != args.only_fold:
            continue
        fout.write('\n\n'.join(ls) + '\n\n')
