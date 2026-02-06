import argparse
import cg3
import utils

parser = argparse.ArgumentParser()
parser.add_argument('source', help='cg bin')
parser.add_argument('target', help='conllu')
parser.add_argument('align', help='word alignments (eflomal format)')
parser.add_argument('out', help='conllu')
args = parser.parse_args()

with (open(args.source, 'rb') as sin,
      open(args.target) as tin,
      open(args.align) as ain,
      open(args.out, 'w') as fout):
    for src, tgt, alg in zip(cg3.parse_binary_stream(sin, windows_only=True),
                             utils.conllu_sentences(tin),
                             ain):
        twords = []
        for w in utils.conllu_words(tgt):
            w[6] = '_'
            w[7] = '_'
            twords.append(w)
        idx = {}
        seen_tgt = set()
        for pair in alg.split():
            a, b = pair.split('-')
            if b in seen_tgt:
                continue
            seen_tgt.add(b)
            idx[int(a)] = int(b)
        links = []
        c2l = {}
        for i, c in enumerate(src.cohorts):
            rel = None
            for r in c.readings:
                for t in r.tags:
                    if t == 'SOURCE':
                        break
                    if t[0] == '@':
                        rel = t[1:]
                        break
                if rel:
                    break
            if rel:
                links.append((c.dep_self, c.dep_parent, rel))
            if i in idx:
                c2l[c.dep_self] = idx[i]
        for c, h, r in links:
            if c in c2l and (h in c2l or h == 0):
                cnum = c2l[c]
                if h == 0:
                    hnum = 0
                else:
                    hnum = c2l[h] + 1
                twords[cnum][6] = str(hnum)
                twords[cnum][7] = r
        for l in tgt:
            if l.startswith('#'):
                print(l.strip(), file=fout)
        for w in twords:
            print(*w, sep='\t', file=fout)
        print('', file=fout)
        break
