import glob
from collections import Counter, defaultdict

xs = []
ys = []

sl = {}
sf = {}
cn = Counter()
cld = Counter()
cfd = Counter()
vl = defaultdict(list)
vf = defaultdict(list)

for fname in glob.glob('tbl-output/*.log'):
    with open(fname) as fin:
        lines = fin.read().strip().splitlines()
        _, l1, f1 = lines[0].strip().split('\t')
        _, l2, f2 = lines[-1].strip().split('\t')
        ld = float(l1) - float(l2)
        fd = float(f1) - float(f2)
        print(f'{fname} {ld:0.2} {fd:0.2}')
        xs.append(ld)
        ys.append(fd)
        key = '_'.join(fname.split('_')[:2])
        cn[key] += 1
        cld[key] += ld
        cfd[key] += fd
        sl[key] = float(l1)
        sf[key] = float(f1)
        vl[key].append(ld)
        vf[key].append(fd)

import matplotlib.pyplot as plt
axs = plt.subplot(ylabel='form diff', xlabel='lemma diff')
axs.scatter(xs, ys)
plt.savefig('blah.png')

for key in cn:
    print(f'{key} & ${sl[key]:.4}$ & ${-min(vl[key]):+.3}$ & ${-cld[key]/cn[key]:+.3}$ & ${-max(vl[key]):+.3}$ & ${sf[key]:.4}$ & ${-min(vf[key]):+.3}$ & ${-cfd[key]/cn[key]:+.3}$ & ${-max(vf[key]):+.3}$')
    print(key, cn[key], cld[key]/cn[key], cfd[key]/cn[key])
    print('\t', sl[key], sf[key])
    print('\t', 'lem', max(vl[key]), min(vl[key]))
    print('\t', 'form', max(vf[key]), min(vf[key]))
