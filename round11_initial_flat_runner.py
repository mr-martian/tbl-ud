import argparse
import concurrent.futures
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('prefix')
parser.add_argument('src')
parser.add_argument('tgt')
parser.add_argument('tgt_feats')
args = parser.parse_args()

def run_config(grammar, filters, similarity, weights):
    print('starting', grammar)
    start = time.time()
    subprocess.run(['python3', 'round11.py',
                    args.src, args.tgt,
                    '300', grammar,
                    '--weights', weights,
                    '--count', filters,
                    '--beam', filters,
                    '--rule_count', filters,
                    '--context_similarity', similarity,
                    '--target_feats', args.tgt_feats],
                   capture_output=True)
    print('finished', grammar, 'after', time.time() - start, 'seconds')

weight_settings = [('plain', '{}'),
                   ('feats', '{"missing_feats": 20}')]
params = []
for filters in ['10', '25', '50']:
    for similarity in ['0.7', '0.8', '0.9', '1.0']:
        for name, weights in weight_settings:
            params.append([f'grammars/{args.prefix}_{filters}_{similarity}_{name}.cg3',
                           filters, similarity, weights])
with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = []
    for p in params:
        futures.append(executor.submit(run_config, *p))
    for future in concurrent.futures.as_completed(futures):
        pass
