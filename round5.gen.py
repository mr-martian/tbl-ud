#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

import argparse
import sqlite3

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('db')
args = parser.parse_args()

con = sqlite3.connect(args.db)
cur = con.cursor()
cur.execute('CREATE TABLE errors(rule, tags1, tags2, window, cohort, cohort_key)')
con.commit()

with open(args.source, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin))

with open(args.target, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin))

def desc_r(reading):
    ret = reading.lemma
    if reading.tags:
        ret += ' ' + reading.tags[0]
    return ret
def desc_c(cohort):
    return desc_r(cohort.static)

for window, (slw, tlw) in enumerate(zip(source, target)):
    rules = []
    src_words = set(desc_r(r) for c in slw.cohorts for r in c.readings)
    tgt_words = set(desc_r(r) for c in tlw.cohorts for r in c.readings)
    extra = src_words - tgt_words
    missing = tgt_words - src_words
    for idx, cohort in enumerate(slw.cohorts):
        suf = (window, idx, desc_c(cohort))
        words = set(desc_r(r) for r in cohort.readings)
        if words.isdisjoint(tgt_words):
            children = [(i, desc_c(c)) for i, c in enumerate(slw.cohorts)
                        if c.dep_parent == cohort.dep_self]
            if children:
                for ch in children:
                    rules.append(('rem-parent', '', '', window)+ch)
            else:
                rules.append(('rem-self', '', '')+suf)
            # TODO: what if we're translating to another det-det lang?
            if 'CCONJ' not in suf[2] and 'DET' not in suf[2]:
                for m in missing:
                    if 'PUNCT' in m:
                        if not ('<ins>' in suf[2] or 'PUNCT' in suf[2]):
                            continue
                    rules.append(('append', m, '')+suf)
        if len(words) > 1:
            for w in words:
                rules.append(('remove', w, '')+suf)
        for m in missing:
            rules.append(('addcohort', m, '')+suf)
        # TODO: SUBSTITUTE
    cur.executemany('INSERT INTO errors VALUES(?, ?, ?, ?, ?, ?)', rules)
    con.commit()

