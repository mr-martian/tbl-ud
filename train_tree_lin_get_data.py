from train_tree_lin import *

import argparse
import random
import sys
import utils

parser = argparse.ArgumentParser()
parser.add_argument('--max', type=int, default=-1)
args = parser.parse_args()

ENUMERATED_RELS = {'conj', 'parataxis', 'advcl', 'mark', 'cc'}

def process_sent(words):
    plain = []
    merge = defaultdict(list)
    for w in words:
        if w.deprel in ENUMERATED_RELS:
            merge[(w.deprel, w.head)].append(int(w.idx))
        else:
            plain.append((int(w.idx),))
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
        tg = '' if w.feats == '_' else w.feats.replace('|', ' ')
        print(f'"<blah>"\n\t"{w.lemma}" {w.upos} {tg} @{w.deprel} #{update[int(w.idx)]}->{update[int(w.head)]}')
    print()

for n, sent in enumerate(utils.conllu_sentences(sys.stdin)):
    if n == args.max:
        break
    process_sent(list(utils.conllu_words(sent)))
