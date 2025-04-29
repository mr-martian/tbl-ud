import argparse
import eflomal
import json
import re
import sys
import utils

parser = argparse.ArgumentParser()
parser.add_argument('outfile')
parser.add_argument('features', nargs='+')
parser.add_argument('--skip', action='store')
args = parser.parse_args()

features = []
dictify = set()
for f in args.features:
    if f.isdigit():
        features.append((int(f), None))
    else:
        n, k = f.split(':')
        features.append((int(n), k))
        dictify.add(int(n))

skip = None
if args.skip:
    skip = re.compile(args.skip)

ids = utils.IDGiver()
corpus = []
for sent in utils.conllu_sentences(sys.stdin):
    if skip and skip.search(sent[0]):
        continue
    line = []
    for word in utils.conllu_words(sent):
        feats = {n: utils.conllu_feature_dict(word[n], with_prefix=True)
                 for n in dictify}
        ls = []
        for n, k in features:
            if k is None:
                ls.append(word[n])
            else:
                ls.append(feats[n].get(k))
        line.append(ids[tuple(ls)])
        print(word[2], end=' ')
    corpus.append(line)
    print('', end='\n')

with open(args.outfile, 'w') as fout:
    json.dump({'words': ids.id2item, 'sents': corpus}, fout)

print(len(corpus), file=sys.stderr)
