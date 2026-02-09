import argparse
import collections
import utils

parser = argparse.ArgumentParser()
parser.add_argument('src')
parser.add_argument('tgt')
parser.add_argument('out')
args = parser.parse_args()

def best_pairs(cur):
    best = [cur[0]]
    for item in cur[1:]:
        if item[2] == best[0][2] and item[3] == best[0][3]:
            best.append(item)
        elif item[2] / item[3] > best[0][2] / best[0][3]:
            best = [item]
    return [item[:2] for item in best]

def prepare_words(sent):
    words = []
    lems = set()
    for w in utils.conllu_words(sent):
        key = (w[2], w[3])
        lems.add(key)
        if w[5] == '_':
            words.append((key, set(key)))
        else:
            words.append((key, set(w[5].split('|')) | set(key)))
    return words, lems

with (open(args.src) as fin1,
      open(args.tgt) as fin2,
      open(args.out, 'w') as fout):
    for src, tgt in zip(utils.conllu_sentences(fin1),
                        utils.conllu_sentences(fin2)):
        swords, slems = prepare_words(src)
        twords, tlems = prepare_words(tgt)
        rev_pairs = collections.defaultdict(list)
        forward = set()
        for i, (sl, st) in enumerate(swords):
            cur = []
            for j, (tl, tt) in enumerate(twords):
                if sl in tlems and sl != tl:
                    continue
                item = (i, j, len(st & tt), len(st | tt))
                rev_pairs[j].append(item)
                cur.append(item)
            forward.update(best_pairs(cur))
        reverse = set()
        for _, cur in rev_pairs.items():
            reverse.update(best_pairs(cur))
        pairs = forward & reverse
        sseen = set()
        tseen = set()
        final = []
        for i, j in sorted(pairs):
            if i in sseen or j in tseen:
                continue
            final.append(f'{i}-{j}')
            sseen.add(i)
            tseen.add(j)
        print(' '.join(final), file=fout)
