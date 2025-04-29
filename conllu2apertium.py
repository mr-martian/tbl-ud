import argparse
import sys
import utils

parser = argparse.ArgumentParser()
parser.add_argument('order', nargs='+')
args = parser.parse_args()

for sent in utils.conllu_sentences(sys.stdin):
    line = []
    for word in utils.conllu_words(sent):
        feats = utils.conllu_feature_dict(word[5], with_prefix=True)
        misc = utils.conllu_feature_dict(word[9], with_prefix=True)
        w = '^'+word[2]+'<'+word[3]+'>'
        for key in args.order:
            v = feats.get(key) or misc.get(key)
            if v:
                w += '<'+v+'>'
        for key, val in sorted(feats.items()):
            if key not in args.order:
                w += '<'+val+'>'
        w += f'<#{word[0]}→{word[6]}><@{word[7]}>$'
        line.append(w)
    print(' '.join(line))

