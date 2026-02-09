import argparse
import utils

parser = argparse.ArgumentParser()
parser.add_argument('source', help='conllu')
parser.add_argument('target', help='conllu')
parser.add_argument('align', help='word alignments (eflomal format)')
parser.add_argument('out', help='conllu')
args = parser.parse_args()

with (open(args.source) as sin,
      open(args.target) as tin,
      open(args.align) as ain,
      open(args.out, 'w') as fout):
    for src, tgt, alg in zip(utils.conllu_sentences(sin),
                             utils.conllu_sentences(tin),
                             ain):
        twords = []
        for w in utils.conllu_words(tgt):
            twords.append(w._replace(deprel='_', head='_'))
        idx = {}
        seen_tgt = set()
        for pair in alg.split():
            a, b = pair.split('-')
            if b in seen_tgt:
                continue
            seen_tgt.add(b)
            idx[int(a)] = int(b)
        links = []
        for w in utils.conllu_words(src):
            if w.deprel:
                h = int(w.head)
                i = int(w.idx)
                if i-1 in idx:
                    loc = idx[i-1]
                    if h == 0:
                        twords[loc] = twords[loc]._replace(
                            head='0', deprel='root')
                    elif h-1 in idx:
                        twords[loc] = twords[loc]._replace(
                            head=str(idx[h-1]+1), deprel=w.deprel)
        for l in tgt:
            if l.startswith('#'):
                print(l.strip(), file=fout)
        for w in twords:
            print(*w, sep='\t', file=fout)
        print('', file=fout)
