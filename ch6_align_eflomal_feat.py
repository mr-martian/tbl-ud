import argparse
import collections
import subprocess
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
    lem_list = []
    for w in utils.conllu_words(sent):
        key = (w[2], w[3])
        lems.add(key)
        if w[5] == '_':
            words.append((key, set(key)))
        else:
            words.append((key, set(w[5].split('|')) | set(key)))
        lem_list.append(w[2])
    return words, lems, lem_list

ferf = set()
ferr = set()
lex = collections.Counter()

with (open(args.src) as fin1, open(args.tgt) as fin2,
      open(args.out + '.words', 'w') as fout):
    for src, tgt in zip(utils.conllu_sentences(fin1),
                        utils.conllu_sentences(fin2)):
        swords, slems, slem_ls = prepare_words(src)
        twords, tlems, tlem_ls = prepare_words(tgt)
        ferf.update(x[0] for x in slems)
        ferr.update(x[0] for x in tlems)
        for i, (sl, st) in enumerate(swords):
            cur = []
            for j, (tl, tt) in enumerate(twords):
                if sl in tlems and sl != tl:
                    continue
                num = len(st & tt)
                if num > 0:
                    item = (i, j, num, len(st | tt))
                    cur.append(item)
            if not cur:
                continue
            cur.sort(key=lambda it: it[2] / it[3])
            factor = cur[0][2] / cur[0][3]
            for a, b, num, dem in cur:
                lex[(slem_ls[a], tlem_ls[b])] += round((num / dem) / factor)
        print(' '.join(slem_ls), '|||', ' '.join(tlem_ls), file=fout)
with open(args.out + '.priors', 'w') as fout:
    for (s, t), n in sorted(lex.items()):
        print('LEX', s, t, n, sep='\t', file=fout)
    for s in sorted(ferf):
        print('FERF', s, 1, 1, sep='\t', file=fout)
    for t in sorted(ferf):
        print('FERR', t, 1, 1, sep='\t', file=fout)
subprocess.run(['eflomal-align', '-i', args.out+'.words',
                '--overwrite', '-p', args.out+'.priors',
                '-f', args.out])
