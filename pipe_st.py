import argparse
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('mode')
parser.add_argument('lang')
parser.add_argument('step', type=int)
parser.add_argument('iter1', type=int)
parser.add_argument('iter2', type=int)
args = parser.parse_args()

def iterations():
    yield args.iter1
    while True:
        yield args.iter2

def max_sents():
    mx = 800
    if args.lang == 'eng':
        mx = 4500
    yield from range(200, mx+args.step, args.step)

prefix = f'/N/slate/dangswan/tbl-output/pipe-st/{args.lang}_{args.step}_{args.iter1}_{args.iter2}'
os.makedirs(prefix, exist_ok=True)

out_dir = f'/N/scratch/dangswan/tbl-output/pipe-st/{args.lang}_{args.step}_{args.iter1}_{args.iter2}_{args.mode}'
os.makedirs(out_dir, exist_ok=True)

params = [
    '--threads', '100',
    '--score_proc', '/N/slate/dangswan/tbl-scripts/ch4_pipe_score/ch4_pipe_score',
    '--out_dir', out_dir,
]
if args.mode == 'feat':
    params += ['--rule_count', '100', '--pos_count', '20']
elif args.mode == 'del':
    params += ['--rule_count', '100', '--lemma_count', '20']
elif args.mode == 'add':
    params += ['--rule_count', '20', '--lemma_count', '20']
else:
    params += ['--rule_count', '100', '--lemma_count', '100']

if args.lang == 'eng':
    params += ['--skip_windows', '/N/slate/dangswan/tbl-data/eng.NET.train.skip.json']
elif args.lang == 'blx':
    params += ['--skip_windows', '/N/slate/dangswan/tbl-data/blx.train.skip.json']

srcfiles = {
    'grc_g': '/N/slate/dangswan/tbl-data/hbo.train.bin',
    'grc_m': '/N/slate/dangswan/tbl-data/hbo-macula.train.bin',
    'eng': '/N/slate/dangswan/tbl-data/hbo.NET.train.bin',
    'blx': '/N/slate/dangswan/tbl-data/hbo.blx.train.bin',
}

tgtfiles = {
    'grc_g': '/N/slate/dangswan/tbl-data/grc.train.bin',
    'grc_m': '/N/slate/dangswan/tbl-data/grc.train.bin',
    'eng': '/N/slate/dangswan/tbl-data/eng.NET.train.bin',
    'blx': '/N/slate/dangswan/tbl-data/blx.train.bin',
}

prev_mode = {
    'sel': None,
    'replace': 'sel',
    'add': 'replace',
    'feat': 'add',
    'del': 'feat',
}

pm = prev_mode[args.mode]

for n, (it, ms) in enumerate(zip(iterations(), max_sents())):
    if os.path.exists(os.path.join(prefix, f'{args.mode}_{n+1:03}.cg3')):
        continue
    grammar = os.path.join(prefix, f'{args.mode}_{n:03}.cg3')
    out_bin = os.path.join(prefix, f'{args.mode}_{n:03}.bin')
    if args.mode == 'sel':
        src = srcfiles[args.lang]
    else:
        src = os.path.join(prefix, f'{pm}_{n:03}.bin')
    subprocess.run(
        ['python3', f'/N/slate/dangswan/tbl-scripts/lex_{args.mode}.py',
         src, tgtfiles[args.lang], args.lang[:3], str(it), grammar,
         '--max_sents', str(ms), *params])
    subprocess.run(['vislcg3', '-g', grammar, '-I', src, '-O', out_bin,
                    '--in-binary', '--out-binary'])
