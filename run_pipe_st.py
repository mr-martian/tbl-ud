import argparse
import glob
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('dir')
parser.add_argument('input')
args = parser.parse_args()

with open(args.input, 'rb') as fin:
    initial_data = fin.read()

data = []

def run_sequence(mode):
    global data
    grammars = glob.glob(os.path.join(args.dir, f'{mode}*.cg3'))
    grammars.sort()
    for i, g in enumerate(grammars):
        print(mode, i, g)
        if i >= len(data):
            if i == 0:
                data.append(initial_data)
            else:
                data.append(data[-1])
        for j in range(i, len(data)):
            proc = subprocess.run(['vislcg3', '-g', g, '--in-binary',
                                   '--out-binary'],
                                  capture_output=True,
                                  input=data[j])
            data[j] = proc.stdout

for mode in ['sel', 'replace', 'add', 'feat', 'del']:
    run_sequence(mode)

for i, d in enumerate(data):
    with open(os.path.join(args.dir, f'dev.{i:03}.bin'), 'wb') as fout:
        fout.write(d)
