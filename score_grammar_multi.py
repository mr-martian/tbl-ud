import argparse
import cg3
import cg3_score
from collections import defaultdict
import json
import matplotlib.pyplot as plt
import metrics
import os
import subprocess
import tempfile
import utils

parser = argparse.ArgumentParser()
parser.add_argument('grammar')
parser.add_argument('train_src')
parser.add_argument('train_tgt')
parser.add_argument('train_skip')
parser.add_argument('dev_src')
parser.add_argument('dev_tgt')
parser.add_argument('dev_skip')
parser.add_argument('--weights', action='store', default='{}')
parser.add_argument('--target_feats', action='store',
                    help='skip removing features not in this JSON list')
args = parser.parse_args()

WEIGHTS = defaultdict(lambda: 1, json.loads(args.weights))
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

def score_buffer(slb, tgt_words, tgt_feats, tgt_counts):
    score = 0
    src_words, src_feats, src_counts = cg3_score.parse_window(
        slb, TARGET_FEATS)
    score += WEIGHTS['cohorts'] * abs(src_counts['cohort'] - tgt_counts['cohort'])
    extra, missing = cg3_score.symmetric_difference(src_words, tgt_words)
    score += WEIGHTS['missing'] * missing
    score += WEIGHTS['extra'] * extra
    score += WEIGHTS['ambig'] * (src_counts['reading'] - src_counts['cohort'])
    score += WEIGHTS['ins'] * src_counts['ins']
    score += WEIGHTS['unk'] * src_counts['unk']
    mf, ef = cg3_score.symmetric_difference(tgt_feats, src_feats)
    score += WEIGHTS['missing_feats'] * mf
    score += WEIGHTS['extra_feats'] * ef
    return score

train_data = [cg3_score.parse_window(tb, TARGET_FEATS)
              for tb in cg3_score.iter_blocks(train_tgt)]
dev_data = [cg3_score.parse_window(tb, TARGET_FEATS)
            for tb in cg3_score.iter_blocks(dev_tgt)]

train_windows = [cg3.parse_binary_window(tb[5:])
                 for i, tb in enumerate(cg3_score.iter_blocks(train_tgt))
                 if i not in TRAIN_SKIP]
dev_windows = [cg3.parse_binary_window(tb[5:])
               for i, tb in enumerate(cg3_score.iter_blocks(dev_tgt))
               if i not in DEV_SKIP]

print(len(train_data), len(train_windows))

scores = {
    'loss (train)': [],
    'PER_lemma (train)': [],
    'PER_form (train)': [],
    'loss (dev)': [],
    'PER_lemma (dev)': [],
    'PER_form (dev)': [],
}

def score_output(buf, mode):
    global train_src, dev_src, scores
    windows = []
    loss = 0
    for i, block in enumerate(cg3_score.iter_blocks(buf)):
        if mode == 'dev' and i in DEV_SKIP:
            continue
        elif mode == 'train' and i in TRAIN_SKIP:
            continue
        elif mode == 'dev' and i >= len(dev_data):
            break
        elif mode == 'train' and i >= len(train_data):
            break
        tgt = train_data[i] if mode == 'train' else dev_data[i]
        loss += score_buffer(block, *tgt)
        windows.append(cg3.parse_binary_window(block[5:]))
    pl, pf = metrics.PER(
        windows,
        (train_windows if mode == 'train' else dev_windows),
        target_features=TARGET_FEATS)
    if mode == 'train':
        train_src = buf
    else:
        dev_src = buf
    scores[f'loss ({mode})'].append(loss)
    scores[f'PER_lemma ({mode})'].append(pl)
    scores[f'PER_form ({mode})'].append(pf)

header = None
cur = []
with open(args.grammar) as fin, tempfile.TemporaryDirectory() as tmpdir:
    n = 0
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
                    ['vislcg3', '-g', pth, '--in-binary', '--out-binary'],
                    input=train_src, capture_output=True)
                score_output(train_proc.stdout, 'train')
                dev_proc = subprocess.run(
                    ['vislcg3', '-g', pth, '--in-binary', '--out-binary'],
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
plt.savefig(args.grammar + '.multi.png')
