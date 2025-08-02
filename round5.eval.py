#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

import argparse
from collections import Counter, defaultdict
import concurrent.futures
from dataclasses import dataclass, field
import os
import sqlite3
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Optional

RTYPES = ['remove', 'append', 'addcohort', 'rem-self', 'rem-parent']

PROFILE = False
profiler = None

if PROFILE:
    import cProfile
    profiler = cProfile.Profile()
    profiler.enable()

COHORT_WEIGHT = 10
READING_WEIGHT = 5
FEATURE_WEIGHT = 1

MAX_RULES = 100

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('db')
parser.add_argument('out')
parser.add_argument('--count', type=int, default=25,
                    help='number of rules to try')
args = parser.parse_args()

with open(args.source, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin))

with open(args.target, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin))

con = sqlite3.connect(args.db)
cur = con.cursor()

def score_window(slw, tlw):
    score = 0
    #score = abs(len(slw.cohorts) - len(tlw.cohorts)) * 5
    src_words = Counter((r.lemma, r.tags[0]) for c in slw.cohorts
                        for r in c.readings)
    tgt_words = Counter((r.lemma, r.tags[0]) for c in tlw.cohorts
                        for r in c.readings)
    #extra = src_words - tgt_words
    missing = tgt_words - src_words
    score += 20 * missing.total()
    #score += 5 * extra.total()
    score += 5 * (src_words.total() - len(slw.cohorts))
    score += len([s for s in slw.cohorts if s.static.lemma == '"<ins>"'])
    # TODO: handle ambiguity on target side
    # TODO: feature mismatches
    return score

base_score = sum(score_window(s, t) for s, t in zip(source, target))

def old_run_grammar(gpath: str, opath: str):
    with NamedTemporaryFile() as fgram:
        cc = subprocess.run(['cg-comp', gpath, fgram.name],
                            capture_output=True)
        cp = subprocess.run(
            ['bash', 'binformat_workaround.sh',
             fgram.name, args.source, opath],
            capture_output=True)
        with open(opath, 'rb') as fout:
            yield from cg3.parse_binary_stream(fout)

def run_grammar(gpath, opath):
    subprocess.run(['/home/daniel/apertium/cg3/src/cg-proc',
                    '-f3', gpath, args.source, opath],
                   capture_output=True)
    with open(opath, 'rb') as fout:
        yield from cg3.parse_binary_stream(fout)

def calc_intersection(rules: list, gpath: str, opath: str):
    if not rules:
        return []
    with open(gpath, 'w') as fout:
        for i, (s, r) in enumerate(rules):
            fout.write(r[2].replace('{NUM}', str(i)) + '\n')
    targets = defaultdict(set)
    contexts = defaultdict(set)
    for window in run_grammar(gpath, opath):
        for cohort in window.cohorts:
            for tag, heads in cohort.relations.items():
                if tag[0] == 'r' and tag[1:].isdigit():
                    contexts[int(tag[1:])].update(heads)
                elif tag.startswith('tr') and tag[2:].isdigit():
                    targets[int(tag[2:])].add(cohort.dep_self)
    intersections = [set() for i in range(len(rules))]
    for i in range(len(rules)):
        for j in range(i):
            if (targets[i] & targets[j]
                or targets[i] & contexts[j]
                or targets[j] & contexts[i]):
                intersections[i].add(j)
                intersections[j].add(i)
    return intersections

def score_rule(rule, gpath, opath):
    with open(gpath, 'w') as fout:
        fout.write('OPTIONS += addcohort-attach ;\n')
        fout.write('DELIMITERS = "<$$$>" ;\n')
        fout.write(rule[1])
    score = 0
    for slw, tlw in zip(run_grammar(gpath, opath), target):
        score += score_window(slw, tlw)
    return (score, rule)

def get_rules():
    for rt in RTYPES:
        cur.execute('SELECT count, rule, relation FROM context WHERE rtype = ? ORDER BY count LIMIT ?', (rt, args.count))
        yield from cur.fetchall()

def generate():
    with (concurrent.futures.ThreadPoolExecutor() as executor,
          TemporaryDirectory() as tmpdir):
        seen = set()
        future_to_rule = {}
        for i, row in enumerate(get_rules()):
            gpath = os.path.join(tmpdir, f'g{i:05}.cg3')
            opath = os.path.join(tmpdir, f'o{i:05}.bin')
            future = executor.submit(score_rule, row, gpath, opath)
            future_to_rule[future] = row
        rules = []
        print(base_score)
        print(tmpdir)
        for i, future in enumerate(concurrent.futures.as_completed(future_to_rule)):
            res = future.result()
            print(f'{i:04}', res[0], res[1][1])
            if res[0] < base_score:
                rules.append(res)
        rules.sort()
        gpath = os.path.join(tmpdir, 'intersection.cg3')
        opath = os.path.join(tmpdir, 'intersection_output.bin')
        intersections = calc_intersection(rules, gpath, opath)
        added = set()
        new_words = set()
        for i, (score, rule) in enumerate(rules):
            if intersections[i] & added:
                continue
            if rule[1][0] == 'A':
                key = rule[1].split(')')[0]
                if key in new_words:
                    continue
                new_words.add(key)
            yield score, rule
            added.add(i)

with open(args.out, 'a') as fout:
    fout.write(f'# {base_score=}\n')
    for s, r in generate():
        fout.write(f'\n# {s}\n{r[1]}\n')

if PROFILE:
    profiler.disable()
    profiler.dump_stats('round5.eval.stats')
