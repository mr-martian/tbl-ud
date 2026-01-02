import argparse
import sys
import utils

parser = argparse.ArgumentParser()
parser.add_argument('order', nargs='+')
parser.add_argument('--count', type=int)
parser.add_argument('--surface', action='store_true')
parser.add_argument('--feats_file', action='store')
args = parser.parse_args()

def order(upos):
    for key in args.order:
        if ':' in key:
            a, b = key.split(':')
            if a == upos:
                yield b
        else:
            yield key

all_feats = set()

for idx, sent in enumerate(utils.conllu_sentences(sys.stdin), 1):
    line = []
    for word in utils.conllu_words(sent):
        feats = utils.conllu_feature_dict(word[5], with_prefix=True)
        misc = utils.conllu_feature_dict(word[9], with_prefix=True)
        w = '^'
        if args.surface:
            w += word[1]+'/'
        w += word[2]+'<'+word[3]+'>'
        seq = list(order(word[3]))
        for key in seq:
            v = feats.get(key) or misc.get(key)
            if v:
                all_feats.add(key)
                w += '<'+v+'>'
        for key, val in sorted(feats.items()):
            if key not in seq:
                all_feats.add(key)
                w += '<'+val+'>'
        w += f'<#{word[0]}→{word[6]}><@{word[7]}>$'
        line.append(w)
    print(' '.join(line))

    if args.count and idx == args.count:
        break

if args.feats_file:
    import json
    with open(args.feats_file, 'w') as fout:
        fout.write(json.dumps(sorted(all_feats)))
