import argparse
from collections import defaultdict, Counter
from itertools import product
import utils

from nltk.metrics import edit_distance
from nltk.translate.bleu_score import corpus_bleu, SmoothingFunction

parser = argparse.ArgumentParser()
parser.add_argument('hypothesis')
parser.add_argument('reference')
parser.add_argument('dix', nargs='+')
args = parser.parse_args()

dix_raw = defaultdict(lambda: defaultdict(Counter))
for fname in args.dix:
    with open(fname) as fin:
        for w in utils.conllu_words(fin):
            feats = {w.upos}
            if w.feats != '_':
                feats.update(w.feats.split('|'))
            dix_raw[w.lemma][frozenset(feats)][w.form.lower()] += 1

dix = {}
RATIO = 5
COUNT = 3
MAX_SENTS = 1000
for k1, v1 in dix_raw.items():
    dix[k1] = []
    for k2, v2 in v1.items():
        ls = v2.most_common(COUNT)
        dix[k1].append((k2, set([k3 for k3, v3 in ls
                                 if v3*RATIO >= ls[0][1]])))
    dix[k1].sort(key=lambda x: len(x[0]), reverse=True)

hypothesis = []
hypothesis_lem = []
with open(args.hypothesis) as fin:
    for n, sent in enumerate(utils.conllu_sentences(fin)):
        words = []
        lemmas = []
        for w in utils.conllu_words(sent):
            key = {w.upos}
            if w.feats != '_':
                key.update(w.feats.split('|'))
            key = frozenset(key)
            cur = set()
            for k, v in dix.get(w.lemma, []):
                if k <= key:
                    cur.update(v)
                    break
            words.append(cur or {'@'+w.lemma.lower()})
            lemmas.append(w.lemma.lower())
        options = [list(x) for x in product(*words)]
        if len(options) > MAX_SENTS:
            options = options[:MAX_SENTS]
        hypothesis.append(options)
        hypothesis_lem.append(lemmas)
        if n % 10 == 0:
            print(n)

reference = []
reference_lem = []
with open(args.reference) as fin:
    for sent in utils.conllu_sentences(fin):
        words = list(utils.conllu_words(sent))
        reference.append([w.form.lower() for w in words])
        reference_lem.append([w.lemma.lower() for w in words])

print(hypothesis[0])
print(reference[0])

weights = [
    (1.0,),
    (0.5, 0.5),
    (0.334, 0.333, 0.333),
    (0.25, 0.25, 0.25, 0.25),
]
print(corpus_bleu(hypothesis, reference, weights=weights, smoothing_function=SmoothingFunction().method1))

total_wer = 0
num_words = 0
for a, b in zip(hypothesis_lem, reference_lem):
    total_wer += edit_distance(a, b)
    num_words += len(b)
print('ED:', 100.0 * total_wer / num_words)
