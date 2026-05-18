import argparse
import cg3
import collections

parser = argparse.ArgumentParser()
parser.add_argument('src')
parser.add_argument('tgt')
parser.add_argument('out')
args = parser.parse_args()

def windows(fname):
    with open(fname, 'rb') as fin:
        yield from cg3.parse_binary_stream(fin, windows_only=True)

todo = []
index = collections.defaultdict(list)

for i, (src, tgt) in enumerate(zip(windows(args.src), windows(args.tgt))):
    tgt_lems = set((r.lemma, r.tags[0])
                   for c in tgt.cohorts
                   for r in c.readings)
    src_lems = set()
    unk = set()
    for c in src.cohorts:
        for r in c.readings:
            if 'SOURCE' in r.tags:
                continue
            src_lems.add((r.lemma, r.tags[0]))
            if r.lemma.startswith('"@'):
                spec = r.tags[0]
                for t in r.tags:
                    if t.startswith('LId[SDBH]='):
                        spec += ' ' + t
                unk.add((r.lemma, r.tags[0], spec))
    if unk:
        for u in unk:
            index[u].append(len(todo))
        todo.append((i, tgt_lems, tgt_lems - src_lems, unk))

rules = []
for i in range(300):
    test = collections.Counter()
    for n, tgt_lems, missing, unk in todo:
        for m in missing:
            for u in unk:
                if m[1] == u[1]:
                    test[(u, m)] += 1
    best = 0
    best_rule = None
    for ((u, m), k) in test.most_common():
        if k < best:
            break
        score = 0
        for idx in index[u]:
            if m in todo[idx][2]:
                score += 1
            elif m not in todo[idx][1]:
                score -= 1
        if score > best:
            best = score
            best_rule = (u, m)
    if best_rule is None:
        break
    rules.append((best, best_rule))
    for idx in index[best_rule[0]]:
        sid, t, m, u = todo[idx]
        todo[idx] = (sid, t, m - {best_rule[1]}, u - {best_rule[0]})

with open(args.out, 'w') as fout:
    for score, ((ul, up, us), (ml, mp)) in rules:
        print(f'SUBSTITUTE ({ul}) ({ml}) ({us}) ; # {score}', file=fout)
