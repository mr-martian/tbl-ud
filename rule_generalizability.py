import argparse
from collections import Counter, defaultdict
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('grammar')
parser.add_argument('train')
parser.add_argument('dev')
args = parser.parse_args()

def count_rules(fname, grammar):
    proc = subprocess.run(
        ['vislcg3', '-I', fname, '-g', grammar, '--in-binary',
         '--trace'],
        capture_output=True, encoding='utf-8')
    windows = 0
    rules = Counter()
    first_reading = False
    for line in proc.stdout.splitlines():
        if '"<' in line:
            first_reading = True
            continue
        if '#1->' in line:
            windows += 1
        first_reading = False
        for tag in line.split():
            if ':' in tag and '=' not in tag and '@' not in tag and ':skip' not in tag and 'PROTECT' not in tag:
                rules[tag] += 1
    ret = defaultdict(lambda: 0)
    ret.update({r: float(c) / windows for r, c in rules.items()})
    return ret

with (open(args.grammar) as gin, tempfile.NamedTemporaryFile() as gout):
    in_with = False
    for line in gin:
        if line.startswith('WITH'):
            in_with = True
        elif line.startswith('}'):
            in_with = False
        elif in_with:
            ls = line.split()
            ls[0] += ':skip'
            line = ' '.join(ls)
        gout.write((line.strip() + '\n').encode('utf-8'))
    gout.flush()
    train = count_rules(args.train, gout.name)
    dev = count_rules(args.dev, gout.name)
#check = list(train.keys())
#for r in check:
#    ln = int(r.split(':')[1])
#    if f'WITH:{ln-1}' in train or f'WITH:{ln-2}' in train:
#        del train[r]
comp = []
total = 0.0
for r in train:
    ratio = dev[r] / train[r]
    total += ratio
    comp.append((ratio, r))
print('MEAN: %0.2f' % (total / len(comp)))
comp.sort()
print('MEDIAN: %0.2f' % (comp[len(comp)//2][0]))

print(train)
print(dev)
print(comp)
