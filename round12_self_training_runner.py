import argparse
import cg3
import concurrent.futures
import datetime
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('prefix')
parser.add_argument('src')
parser.add_argument('tgt')
parser.add_argument('tgt_feats')
parser.add_argument('--skip_windows', action='store')
args = parser.parse_args()

N = 0
with open(args.tgt, 'rb') as fin:
    N = len(list(cg3.parse_binary_stream(fin, windows_only=True)))

def run_config(grammar, rule_count, beam, similarity, start, step):
    print('starting', grammar, 'at', datetime.datetime.now())
    start = time.time()
    args = ['python3', 'round12.py',
            args.src, args.tgt,
            '50', grammar,
            '--count', rule_count,
            '--beam', beam,
            '--rule_count', rule_count,
            '--context_similarity', similarity,
            '--target_feats', args.tgt_feats]
    if args.skip_windows:
        args += ['--skip_windows', args.skip_windows]
    ct = start
    while ct < N:
        subprocess.run(args + ['--max_sents', str(ct)],
                       capture_output=True)
        if ct == start:
            args += ['--append']
        ct += step
    print('finished', grammar, 'after', time.time() - start, 'seconds at',
          datetime.datetime.now())

def gen_configs():
    params = [('small', '10', '3', '0.7'), ('large', '50', '10', '0.9')]
    for name, rule_count, beam, similarity in params:
        for start in [100, 200]:
            for step in [25, 50, 100]:
                yield (f'grammars/{args.prefix}_{name}_{start}_{step}.cg3',
                       rule_count, beam, similarity, start, step)

with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = []
    for p in gen_configs():
        futures.append(executor.submit(run_config, *p))
    for future in concurrent.futures.as_completed(futures):
        pass
