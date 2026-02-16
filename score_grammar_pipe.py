import argparse
import cg3
import cg3_score
from collections import Counter, defaultdict
import json
import matplotlib.pyplot as plt
import metrics
import os
import subprocess
import tempfile
import utils

parser = argparse.ArgumentParser()
parser.add_argument('out')
parser.add_argument('train_src')
parser.add_argument('train_tgt')
parser.add_argument('train_skip')
parser.add_argument('dev_src')
parser.add_argument('dev_tgt')
parser.add_argument('dev_skip')
parser.add_argument('--target_feats', action='store',
                    help='skip removing features not in this JSON list')
parser.add_argument('grammars', nargs='+')
args = parser.parse_args()

TARGET_FEATS = utils.load_json_set(args.target_feats)
TRAIN_SKIP = utils.load_json_set(args.train_skip)
DEV_SKIP = utils.load_json_set(args.dev_skip)

def read_bin(path):
    with open(path, 'rb') as fin:
        return fin.read()

train_src = read_bin(args.train_src)
train_tgt = read_bin(args.train_tgt)
dev_src = read_bin(args.dev_src)
dev_tgt = read_bin(args.dev_tgt)

def count_lemmas(window):
    lc = Counter()
    fc = Counter()
    for cohort in window.cohorts:
        for reading in cohort.readings:
            if reading.tags[0] == 'SOURCE':
                continue
            key = reading.lemma + ' ' + reading.tags[0]
            lc[key] += 1
            for t in reading.tags:
                if '=' in t and (not TARGET_FEATS or t.split('=')[0] in TARGET_FEATS):
                    fc[key + ' ' + t] += 1
    return lc, fc

def loss(window, tlc, tfc):
    slc, sfc = count_lemmas(window)
    al, bl = cg3_score.symmetric_difference(slc, tlc)
    af, bf = cg3_score.symmetric_difference(sfc, tfc)
    return al + bl, af + bf

train_windows = [cg3.parse_binary_window(tb[5:])
                 for i, tb in enumerate(cg3_score.iter_blocks(train_tgt))
                 if i not in TRAIN_SKIP]
dev_windows = [cg3.parse_binary_window(tb[5:])
               for i, tb in enumerate(cg3_score.iter_blocks(dev_tgt))
               if i not in DEV_SKIP]

train_data = [count_lemmas(w) for w in train_windows]
dev_data = [count_lemmas(w) for w in dev_windows]

scores = {
    'loss_lemma (train)': [],
    'loss_feat (train)': [],
    'PER_lemma (train)': [],
    'PER_form (train)': [],
    'loss_lemma (dev)': [],
    'loss_feat (dev)': [],
    'PER_lemma (dev)': [],
    'PER_form (dev)': [],
}

def score_output(buf, mode):
    global train_src, dev_src, scores
    windows = []
    loss_l = 0
    loss_f = 0
    n = 0
    for i, block in enumerate(cg3_score.iter_blocks(buf)):
        if mode == 'dev' and i in DEV_SKIP:
            continue
        elif mode == 'train' and i in TRAIN_SKIP:
            continue
        elif mode == 'dev' and i >= len(dev_data):
            break
        elif mode == 'train' and i >= len(train_data):
            break
        tgt = train_data[n] if mode == 'train' else dev_data[n]
        w = cg3.parse_binary_window(block[5:])
        l, f = loss(w, *tgt)
        loss_l += l
        loss_f += f
        windows.append(w)
        n += 1
    pl, pf = metrics.PER(
        windows,
        (train_windows if mode == 'train' else dev_windows),
        target_features=TARGET_FEATS)
    if mode == 'train':
        train_src = buf
    else:
        dev_src = buf
    scores[f'loss_lemma ({mode})'].append(loss_l)
    scores[f'loss_feat ({mode})'].append(loss_f)
    scores[f'PER_lemma ({mode})'].append(pl)
    scores[f'PER_form ({mode})'].append(pf)

with tempfile.TemporaryDirectory() as tmpdir:
    n = 0
    for grammar in args.grammars:
        with open(grammar) as fin:
            header = None
            cur = []
            for line in fin:
                if line.startswith('## '):
                    print(n)
                    if header is None:
                        header = '\n'.join(cur)
                        score_output(train_src, 'train')
                        score_output(dev_src, 'dev')
                    else:
                        pth = os.path.join(tmpdir, f'g{n}.cg3')
                        with open(pth, 'w') as fout:
                            fout.write(header + '\n'.join(cur))
                        train_proc = subprocess.run(
                            ['vislcg3', '-g', pth,
                             '--in-binary', '--out-binary'],
                            input=train_src, capture_output=True)
                        score_output(train_proc.stdout, 'train')
                        dev_proc = subprocess.run(
                            ['vislcg3', '-g', pth,
                             '--in-binary', '--out-binary'],
                            input=dev_src, capture_output=True)
                        score_output(dev_proc.stdout, 'dev')
                    cur = []
                    n += 1
                else:
                    cur.append(line)

axs = plt.subplot(ylabel='PER and Normalized Loss', xlabel='Iterations')
axs.set_ylim(ymin=0, ymax=100)
for key in scores:
    vals = scores[key]
    if key.startswith('loss'):
        mx = max(vals)
        vals = [100 * float(v) / mx for v in vals]
    axs.plot(range(len(vals)), vals, label=key)
axs.legend()
plt.savefig(args.out)
