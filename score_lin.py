import argparse
from nltk.translate.bleu_score import corpus_bleu
from nltk.metrics import edit_distance
import utils

parser = argparse.ArgumentParser()
parser.add_argument('src')
parser.add_argument('tgt')
args = parser.parse_args()

ref = []
hyp = []

total_ed = 0
norm_ed = 0
all_words = 0
max_loss = 0
wer = 0

with (open(args.src) as fsrc, open(args.tgt) as ftgt):
    for ss, st in zip(utils.conllu_sentences(fsrc),
                      utils.conllu_sentences(ftgt)):
        sw = [w[2] for w in utils.conllu_words(ss)]
        tw = [w[2] for w in utils.conllu_words(st)]
        hyp.append(sw)
        ref.append([tw])
        ig = utils.IDGiver()
        se = ''.join(chr(ig[w] + 60) for w in sw)
        te = ''.join(chr(ig[w] + 60) for w in tw)
        ed = edit_distance(se, te, transpositions=True)
        total_ed += ed
        norm_ed += float(ed) / len(sw)
        all_words += len(sw)
        max_loss += len(sw) ** 2
        wer += edit_distance(sw, tw, transpositions=True) / len(sw)

print('BLEU', corpus_bleu(ref, hyp), 'sentence-averaged ED', norm_ed/len(hyp), 'corpus-averaged ED', float(total_ed)/all_words, 'max loss', max_loss, 'WER', 100.0 * wer / len(hyp))
