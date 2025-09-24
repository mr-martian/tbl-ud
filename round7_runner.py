#!/usr/bin/env python3

import argparse
import cg3
from collections import Counter
import concurrent.futures
import json
import os
import sqlite3
import subprocess
from tempfile import TemporaryDirectory

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('db')
parser.add_argument('--workers', type=int, default=5)
parser.add_argument('--generations', type=int, default=5)
parser.add_argument('--iterations', type=int, default=200)
args = parser.parse_args()

cols = ['cohorts', 'missing', 'extra', 'ambig', 'ins', 'unk']

should_init = (not os.path.exists(args.db))
con = sqlite3.connect(args.db)
cur = con.cursor()
if should_init:
    names = ', '.join(cols)
    cur.execute(f'CREATE TABLE weights({names}, score1, score_scale, state, UNIQUE({names}) ON CONFLICT IGNORE)')
    vals = ', '.join(['10']*len(cols))
    cur.execute(f'INSERT INTO weights VALUES({vals}, 0, 0, 0)')
    vals = ', '.join(['5']*len(cols))
    cur.execute(f'INSERT INTO weights VALUES({vals}, 0, 0, 0)')
    con.commit()

with open(args.source, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin, windows_only=True))

split = len(source) // 5

with open(args.target, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin, windows_only=True))

def score_window(slw, tlw, weights):
    score = 0
    score += weights['cohorts'] * abs(len(slw.cohorts) - len(tlw.cohorts))
    src_words = Counter((r.lemma, r.tags[0]) for c in slw.cohorts
                        for r in c.readings if 'SOURCE' not in r.tags)
    tgt_words = Counter((r.lemma, r.tags[0]) for c in tlw.cohorts
                        for r in c.readings if 'SOURCE' not in r.tags)
    extra = src_words - tgt_words
    missing = tgt_words - src_words
    score += weights['missing'] * missing.total()
    score += weights['extra'] * extra.total()
    score += weights['ambig'] * (src_words.total() - len(slw.cohorts))
    score += weights['ins'] * len([s for s in slw.cohorts
                                   if any(r.lemma == '"<ins>"'
                                          for r in s.readings)])
    score += weights['unk'] * sum([ct for (lm, tg), ct in src_words.items()
                                   if lm.startswith('"@')])
    return score

def score_range(system, fold, weights):
    ret = 0
    for i in range(fold*split, (fold+1)*split):
        ret += score_window(system[i], target[i], weights)
    return ret

def score_row(row):
    weights = dict(zip(cols, row))
    weight_str = json.dumps(weights)
    with TemporaryDirectory() as tmpdir:
        for g in range(args.generations):
            procs = []
            for i in range(5):
                if g == 0:
                    src = args.source
                else:
                    src = os.path.join(tmpdir, f'out_{g}_{i}.bin')
                out = os.path.join(tmpdir, f'out_{g+1}_{i}.bin')
                procs.append(subprocess.Popen(
                    ['python3', 'round7.py', src, args.target, out,
                     str(i), weight_str],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            for p in procs:
                p.wait()
        score1 = 0
        score_start = 0
        score_end = 0
        w1 = {k: 1 for k in cols}
        for i in range(5):
            fname = os.path.join(tmpdir, f'out_{args.generations}_{i}.bin')
            with open(fname, 'rb') as fin:
                data = list(cg3.parse_binary_stream(fin, windows_only=True))
                score1 += score_range(data, i, w1)
                score_start += score_range(source, i, weights)
                score_end += score_range(data, i, weights)
        return (score1, score_start / score_end, row[-1])

def add_neighbors(row, cur):
    qs = ', '.join(['?']*len(cols))
    ws = list(row[:len(cols)])
    shift = []
    sc = list(row[len(cols):len(cols)+2])
    for i in range(len(cols)):
        if ws[i] > 0:
            shift.append(ws[:i] + [ws[i]-1] + ws[i+1:] + sc)
        if ws[i] < 50:
            shift.append(ws[:i] + [ws[i]+1] + ws[i+1:] + sc)
        cur.executemany(f'INSERT INTO weights VALUES({qs}, ?, ?, 0)', shift)
        cur.execute('UPDATE weights SET state = 2 WHERE rowid = ?',
                    (row[-1],))

for idx in range(args.iterations):
    cur.execute('SELECT *, rowid FROM weights WHERE state < 2 ORDER BY score1 ASC LIMIT ?', (args.workers,))
    rows = cur.fetchall()
    print(idx)
    print(rows)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for row in rows:
            if row[-2] == 0:
                futures.append(executor.submit(score_row, row))
            else:
                add_neighbors(row, cur)
        results = []
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
        cur.executemany('UPDATE weights SET score1 = ?, score_scale = ?, state = 1 WHERE rowid = ?', results)
        con.commit()
