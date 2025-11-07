from collections import Counter
import pickle

PKLFILE = 'hbo-grc.factors.pkl'

WEIGHTS = {
    'cohorts': 1,
    'missing': 3,
    'extra': 1,
    'extra_sq': 0,
    'ambig': 1,
    'ins': 1,
    'unk': 1,
}

def score(row):
    rule, count, factors = row
    return (sum(v*factors.get(k, 0) for k, v in WEIGHTS.items()),
            -count, rule)

with open(PKLFILE, 'rb') as fin:
    data = pickle.load(fin)
    for score, ncount, rule in sorted(map(score, data))[:20]:
        print(score, -ncount, rule)

