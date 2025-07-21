#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

import argparse
from itertools import combinations
import sqlite3

PROFILE = False
profiler = None

if PROFILE:
    import cProfile
    profiler = cProfile.Profile()
    profiler.enable()

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('db')
parser.add_argument('--count', type=int, default=100,
                    help='number of templates to expand')
parser.add_argument('--ctx', type=int, default=2,
                    help='max context tests')
args = parser.parse_args()

con = sqlite3.connect(args.db)
cur = con.cursor()
cur.execute('CREATE TABLE context(rule, relation, window)')
con.commit()

with open(args.source, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin))

with open(args.target, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin))

def format_rule(rtype, target, tags=None, desttags=None, context=None):
    ctx = ' '.join(f'({test})' for test in sorted(context or []))
    if rtype == 'remove':
        return f'REMOVE ({tags}) IF (0 ({target})) {ctx} ;'
    elif rtype == 'append':
        return f'APPEND ({tags}) (*) IF (0 ({target})) {ctx} ;'
    elif rtype == 'addcohort':
        return f'ADDCOHORT ("<ins>" {tags}) BEFORE (*) IF (0 ({target})) {ctx} ;'
    elif rtype == 'rem-self':
        return f'REMCOHORT (*) IF (0 ({target})) {ctx} ;'
    elif rtype == 'rem-parent':
        return f'WITH (*) IF (0 ({target})) {ctx} {{\n\tSWITCHPARENT WITHCHILD (*) (*) ;\n\tREMCOHORT _C2_ ;\n}} ;'

    elif rtype == 'SUBSTITUTE':
        return f'SUBSTITUTE ({tags}) ({desttags}) (*) IF (0 ({target})) {ctx} ;'

def format_relation(target, context):
    ret = []
    ret.append(f'ADDRELATION (tr%s) (*) (0 ({target})) TO (0 (*)) ;')
    for test in context:
        ret.append(f'ADDRELATION (r%s) (*) (0 ({target})) TO ({test}) ;')
    return '\n'.join(ret)

def make_rule(target, context, dct):
    return (format_rule(target=target, context=context, **dct),
            format_relation(target, context))

def describe_cohort(cohort):
    yield f'{cohort.static.lemma} {cohort.static.tags[0]}'
    for r in cohort.readings:
        for t in r.tags:
            if '@' in t:
                yield t
        break

def gen_contexts(slw, idx, dct, include_parent=False):
    ctx = []
    pctx = []
    ds = slw.cohorts[idx].dep_self
    dh = slw.cohorts[idx].dep_parent
    for cohort in slw.cohorts:
        rel = None
        if cohort.dep_self == dh:
            rel = 'p'
        elif cohort.dep_parent == dh and cohort.dep_self != ds:
            rel = 's'
        elif cohort.dep_parent == ds:
            rel = 'c'
        if rel is not None:
            for desc in describe_cohort(cohort):
                tst = f'{rel} ({desc})'
                if include_parent and rel == 'p':
                    pctx.append(tst)
                else:
                    ctx.append(tst)
    tgt = list(describe_cohort(slw.cohorts[idx]))
    for t in tgt:
        if include_parent:
            for cp in pctx:
                for i in range(args.ctx):
                    for seq in combinations(ctx, i):
                        yield make_rule(t, set(seq+(cp,)), dct)
        else:
            for i in range(args.ctx+1):
                for seq in combinations(ctx, i):
                    yield make_rule(t, set(seq), dct)

cur.execute('SELECT COUNT(*) AS ct, rule, tags1, tags2, cohort_key FROM errors GROUP BY rule, tags1, tags2, cohort_key ORDER BY ct DESC LIMIT ?', (args.count,))

patterns = cur.fetchall()
for count, rule, tags1, tags2, ckey in patterns:
    rules = []
    cur.execute('SELECT window, cohort FROM errors WHERE rule = ? AND tags1 = ? AND tags2 = ? AND cohort_key = ?',
                (rule, tags1, tags2, ckey))
    for wnum, cnum in cur.fetchall():
        slw = source[wnum]
        for r in gen_contexts(
                slw, cnum,
                {'rtype': rule, 'tags': tags1, 'desttags': tags2},
                include_parent=(rule == 'rem-parent')):
            rules.append(r + (wnum,))
    cur.executemany('INSERT INTO context VALUES(?, ?, ?)', rules)
    con.commit()

if PROFILE:
    profiler.disable()
    profiler.dump_stats('round5.context2.stats')
