import glob
import utils

def get_rels(fname):
    with open(fname) as fin:
        return [w.deprel for w in utils.conllu_words(fin)]
            

ref = get_rels('ud-treebanks-v2.17/UD_Ancient_Greek-PTNK/grc_ptnk-ud-dev.conllu')

for fname in sorted(glob.glob('cv_data/*/dev.*.connect.conllu')):
    rels = get_rels(fname)
    score = len([1 for a,b in zip(rels, ref) if a == b])
    print(f'{(100*score/len(ref)):0.2f}', fname)
