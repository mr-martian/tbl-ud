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
parser.add_argument('--init_step', type=int, default=5)
parser.add_argument('--delta_step', type=int, default=5)
parser.add_argument('--threshold_step', type=int, default=1)
args = parser.parse_args()

WEIGHTS = {'cohorts': 1, 'missing': 1, 'extra': 1,
           'ambig': 1, 'ins': 1, 'unk': 1}
WEIGHT_STR = json.dumps(WEIGHTS)

START = {
    'count_init': 25,
    'count_delta': 5,
    'beam_init': 25,
    'beam_delta': 5,
    'rule_count_init': 25,
    'rule_count_delta': 5,
    'threshold': 2,
}
cols = sorted(START.keys())
cmdargs = [k[:-5] for k in cols if k.endswith('_init')]

should_init = (not os.path.exists(args.db))
con = sqlite3.connect(args.db)
cur = con.cursor()
if should_init:
    names = ', '.join(cols)
    vals = ', '.join([str(START[k]) for k in cols])
    cur.execute(f'CREATE TABLE params({names}, score, state, UNIQUE({names}) ON CONFLICT IGNORE)')
    cur.execute(f'INSERT INTO params VALUES({vals}, 0, 0)')
    con.commit()

with open(args.source, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin, windows_only=True))

split = len(source) // 5

with open(args.target, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin, windows_only=True))

def score_window(slw, tlw):
    score = 0
    score += WEIGHTS['cohorts'] * abs(len(slw.cohorts) - len(tlw.cohorts))
    src_words = Counter((r.lemma, r.tags[0]) for c in slw.cohorts
                        for r in c.readings if 'SOURCE' not in r.tags)
    tgt_words = Counter((r.lemma, r.tags[0]) for c in tlw.cohorts
                        for r in c.readings if 'SOURCE' not in r.tags)
    extra = src_words - tgt_words
    missing = tgt_words - src_words
    score += WEIGHTS['missing'] * missing.total()
    score += WEIGHTS['extra'] * extra.total()
    score += WEIGHTS['ambig'] * (src_words.total() - len(slw.cohorts))
    #score += WEIGHTS['ins'] * len([s for s in slw.cohorts
    #                               if any(r.lemma == '"<ins>"'
    #                                      for r in s.readings)])
    #score += WEIGHTS['unk'] * sum([ct for (lm, tg), ct in src_words.items()
    #                               if lm.startswith('"@')])
    return score

def score_range(system, fold):
    ret = 0
    for i in range(fold*split, (fold+1)*split):
        ret += score_window(system[i], target[i])
    return ret

def score_row(row):
    params = dict(zip(cols, row))
    cmds = []
    for i in range(5):
        d = {}
        for k in cmdargs:
            d[k] = params[k+'_init']
        cmds.append(d)
    exclusions = [[] for i in range(5)]
    with TemporaryDirectory() as tmpdir:
        for g in range(args.generations):
            procs = []
            for i in range(5):
                if g == 0:
                    src = args.source
                else:
                    src = os.path.join(tmpdir, f'out_{g}_{i}.bin')
                out = os.path.join(tmpdir, f'out_{g+1}_{i}.bin')
                cmd = ['python3', 'round9.py', src, args.target, out,
                       str(i), WEIGHT_STR, json.dumps(exclusions[i])]
                for k, v in cmds[i].items():
                    cmd += ['--'+k, str(v)]
                #print(cmd)
                procs.append(subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            for i, p in enumerate(procs):
                p.wait()
                if p.returncode:
                    print(p.stderr.read().decode('utf-8'))
                    raise ValueError('something went wrong')
                err = p.stderr.read().decode('utf-8').splitlines()
                rc = int(err[0].strip())
                exclusions[i] += json.loads(err[1])
                if rc <= params['threshold']:
                    for k in cmdargs:
                        cmds[i][k] += params[k+'_delta']
            score = 0
            for i in range(5):
                fname = os.path.join(tmpdir, f'out_{g+1}_{i}.bin')
                with open(fname, 'rb') as fin:
                    data = list(cg3.parse_binary_stream(fin, windows_only=True))
                    score += score_range(data, i)
            print(g+1, score)
        score = 0
        for i in range(5):
            fname = os.path.join(tmpdir, f'out_{args.generations}_{i}.bin')
            with open(fname, 'rb') as fin:
                data = list(cg3.parse_binary_stream(fin, windows_only=True))
                score += score_range(data, i)
        return (score, row[-1])

def add_neighbors(row, cur):
    return
    qs = ', '.join(['?']*len(cols))
    ws = list(row[:len(cols)])
    shift = []
    sc = list(row[len(cols):len(cols)+1])
    for i, c in enumerate(cols):
        n = getattr(args, c.split('_')[-1] + '_step')
        if ws[i] >= n:
            shift.append(ws[:i] + [ws[i]-n] + ws[i+1:] + sc)
        if ws[i] <= n*10:
            shift.append(ws[:i] + [ws[i]+n] + ws[i+1:] + sc)
        cur.executemany(f'INSERT INTO params VALUES({qs}, ?, 0)', shift)
        cur.execute('UPDATE params SET state = 2 WHERE rowid = ?',
                    (row[-1],))

for idx in range(args.iterations):
    cur.execute('SELECT *, rowid FROM params WHERE state < 2 ORDER BY score ASC LIMIT ?', (args.workers,))
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
        cur.executemany('UPDATE params SET score = ?, state = 1 WHERE rowid = ?', results)
        con.commit()
