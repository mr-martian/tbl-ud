from train_tree_lin import *

import argparse
import random
import sys

def process_sent(words):
    plain = []
    merge = defaultdict(list)
    for w in words:
        if w.relation in ENUMERATED_RELS:
            merge[(w.relation, w.head)].append(w.index)
        else:
            plain.append((w.index,))
    items = plain + [tuple(x) for x in merge.values()]
    random.shuffle(items)
    i = 0
    update = {0: 0}
    seq = []
    for item in items:
        for index in item:
            i += 1
            update[index] = i
            seq.append(index)
    for s in seq:
        w = words[s-1]
        tg = ' '.join(sorted(w.feats))
        print(f'"<blah>"\n\t"{w.lemma}" {w.upos} {tg} @{w.relation} #{update[w.index]}->{update[w.head]}')
    print()

cur = ''
for line in sys.stdin:
    if not line.strip():
        if cur:
            process_sent(parse_conllu(cur))
        cur = ''
    else:
        cur += line.strip() + '\n'
if cur:
    process_sent(parse_conllu(cur))
