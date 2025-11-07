#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

from collections import Counter
import os
import pickle
import sqlite3
import subprocess
from tempfile import TemporaryDirectory

RTYPES = ['remove', 'append', 'addcohort', 'rem-self', 'rem-parent']

COUNT = 100
SOURCEFILE = 'generated/hbo-grc/hbo.input.bin'
TARGETFILE = 'generated/hbo-grc/grc.gold.bin'
DB = 'hbo-grc.db'
PKLFILE_IN = 'hbo-grc.pickle'
PKLFILE_OUT = 'hbo-grc.factors.pkl'

with open(TARGETFILE, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin))

def get_data():
    with open(PKLFILE_IN, 'rb') as fin:
        while True:
            try:
                yield pickle.load(fin)
            except EOFError:
                break

def score_window(slw, tlw):
    factors = Counter()
    factors['cohorts'] = abs(len(slw.cohorts) - len(tlw.cohorts))
    src_words = Counter((r.lemma, r.tags[0]) for c in slw.cohorts
                        for r in c.readings)
    tgt_words = Counter((r.lemma, r.tags[0]) for c in tlw.cohorts
                        for r in c.readings)
    extra = src_words - tgt_words
    missing = tgt_words - src_words
    factors['missing'] = missing.total()
    factors['extra'] = extra.total()
    factors['extra_sq'] = sum([(n-1)*(n-1) for k, n in extra.items()
                               if k in tgt_words])
    factors['ambig'] = src_words.total() - len(slw.cohorts)
    factors['ins'] = len([s for s in slw.cohorts
                          if s.static.lemma == '"<ins>"'])
    factors['unk'] =  sum([ct for (lm, tg), ct in src_words.items()
                           if lm.startswith('"@')])
    # TODO: handle ambiguity on target side
    # TODO: feature mismatches
    return factors

results = []
for i, (count, rule, cohorts) in enumerate(get_data()):
    if i % 10 == 0: print(i)
    results.append((
        rule, count,
        sum(map(score_window, cohorts, target), start=Counter()),
    ))

with open(PKLFILE_OUT, 'wb') as fout:
    pickle.dump(results, fout)
