import argparse
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

def run_config(grammar, count, weights):
    print('starting', grammar, 'at', datetime.datetime.now())
    start = time.time()
    skip = []
    if args.skip_windows:
        skip = ['--skip_windows', args.skip_windows]
    subprocess.run(['python3', 'round13.py',
                    args.src, args.tgt,
                    '300', grammar,
                    '--weights', weights,
                    '--count', count,
                    '--target_feats', args.tgt_feats] + skip,
                   capture_output=True)
    print('finished', grammar, 'after', time.time() - start, 'seconds at',
          datetime.datetime.now())

weight_settings = [('plain', '{}'),
                   ('feats', '{"missing_feats": 20}'),
                   ('ambig', '{"ambig": 10, "extra": 10}'),
                   ('both', '{"missing_feats": 20, "ambig": 10, "extra": 10}'),
                   ]
params = []
for count in ['50', '100', '200']:
    for name, weights in weight_settings:
        params.append([f'grammars/{args.prefix}_{count}_{name}.cg3',
                       count, weights])
with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = []
    for p in params:
        futures.append(executor.submit(run_config, *p))
    for future in concurrent.futures.as_completed(futures):
        pass
