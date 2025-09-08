#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import sqlite3

RTYPES = ['remove', 'append', 'addcohort', 'rem-self', 'rem-parent']

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
parser.add_argument('--count', type=int, default=25,
                    help='number of templates to expand')
parser.add_argument('--ctx', type=int, default=2,
                    help='max context tests')
parser.add_argument('--beam', type=int, default=25,
                    help='max instantiations of a single pattern')
args = parser.parse_args()

con = sqlite3.connect(args.db)
cur = con.cursor()
cur.execute('CREATE TABLE context(rtype, rule TEXT, relation TEXT, count INT)')
con.commit()

with open(args.source, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin))

with open(args.target, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin))

def format_rule(rtype, target, tags=None, desttags=None, context=None):
    ls = []
    if rtype == 'rem-parent':
        ls = [c for c in context if c[0] == 'p'] + sorted(
            [c for c in context if c[0] != 'p'])
    else:
        ls = sorted(context or [])
    ctx = ' '.join(f'({test})' for test in ls)
    if rtype == 'remove':
        return f'REMOVE ({tags}) IF (0 ({target})) {ctx} ;'
    elif rtype == 'append':
        return f'APPEND ({tags}) (*) IF (0 ({target})) {ctx} ;'
    elif rtype == 'addcohort':
        return f'ADDCOHORT ("<ins>" {tags} @dep) BEFORE (*) IF (0 ({target})) {ctx} ;'
    elif rtype == 'rem-self':
        return f'REMCOHORT (*) IF (0 ({target})) (NEGATE c (*)) {ctx} ;'
    elif rtype == 'rem-parent':
        return f'WITH (*) IF (0 ({target})) {ctx} {{\n\tSWITCHPARENT WITHCHILD (*) (*) ;\n\tREMCOHORT _C2_ ;\n}} ;'

    elif rtype == 'SUBSTITUTE':
        return f'SUBSTITUTE ({tags}) ({desttags}) (*) IF (0 ({target})) {ctx} ;'

def format_relation(target, context):
    ret = []
    ret.append(f'ADDRELATION (tr{{NUM}}) (*) (0 ({target})) TO (0 (*)) ;')
    for test in context:
        ret.append(f'ADDRELATION (r{{NUM}}) (*) (0 ({target})) TO ({test}) ;')
    # TODO: NEGATE
    return '\n'.join(ret)

def get_rel(cohort):
    for r in cohort.readings:
        for t in r.tags:
            if t[0] == '@':
                return t

all_rels = set(get_rel(c) for w in source for c in w.cohorts)

def describe_cohort(cohort):
    rel = get_rel(cohort) or ''
    if cohort.static.tags:
        yield f'{cohort.static.lemma} {cohort.static.tags[0]} {rel}'
    for rd in cohort.readings:
        yield f'{rd.tags[0]} {rel}'
        yield f'{rd.lemma} {rd.tags[0]} {rel}'
        # TODO: features

def collect_contexts(slw, idx, dct):
    ds = slw.cohorts[idx].dep_self
    dh = slw.cohorts[idx].dep_parent
    s_rel = set()
    c_rel = set()
    for cohort in slw.cohorts:
        if cohort.dep_self == dh:
            dct['p'].update(set(describe_cohort(cohort)))
        elif cohort.dep_parent == dh and cohort.dep_self != ds:
            dct['s'].update(set(describe_cohort(cohort)))
            s_rel.add(get_rel(cohort))
        elif cohort.dep_parent == ds:
            dct['c'].update(set(describe_cohort(cohort)))
            c_rel.add(get_rel(cohort))
    dct['t'].update(set(describe_cohort(slw.cohorts[idx])))
    #dct['negs'].update(all_rels - s_rel)
    #dct['negc'].update(all_rels - c_rel)

def rel_ranges(include_parent):
    mn = 1 if include_parent else 0
    for n in range(1, args.ctx+1):
        for i_p in range(mn, 2):
            for i_s in range(n-i_p+1):
                yield i_p, i_s, (n-i_p-i_s)

def gen_rules(contexts, dct, include_parent=False):
    ct = args.count >> 2
    cp = [(f'p ({k})',v) for k,v in contexts['p'].most_common(ct)]
    cs = [(f's ({k})',v) for k,v in contexts['s'].most_common(ct)]
    cs += [(f'NEGATE s ({k})',v) for k,v in contexts['negs'].most_common(ct)]
    cc = [(f'c ({k})',v) for k,v in contexts['c'].most_common(ct)]
    cc += [(f'NEGATE c ({k})',v) for k,v in contexts['negc'].most_common(ct)]
    for i_p, i_s, i_c in rel_ranges(include_parent):
        for t_p in combinations(cp, i_p):
            for t_s in combinations(cs, i_s):
                for t_c in combinations(cc, i_c):
                    seq = t_p + t_s + t_c
                    ctx = tuple([s[0] for s in seq])
                    count = min(s[1] for s in seq)
                    for tgc, tgi in contexts['t'].most_common(ct):
                        yield (dct['rtype'],
                               format_rule(target=tgc, context=ctx, **dct),
                               format_relation(tgc, ctx),
                               min(count, tgi))

patterns = []
for rt in RTYPES:
    cur.execute('SELECT COUNT(*) AS ct, rule, tags1, tags2, cohort_key FROM errors WHERE rule = ? GROUP BY rule, tags1, tags2, cohort_key ORDER BY ct DESC LIMIT ?', (rt, args.count))
    patterns += cur.fetchall()

for count, rule, tags1, tags2, ckey in patterns:
    cur.execute('SELECT window, cohort FROM errors WHERE rule = ? AND tags1 = ? AND tags2 = ? AND cohort_key = ?',
                (rule, tags1, tags2, ckey))
    dct = defaultdict(Counter)
    for wnum, cnum in cur.fetchall():
        slw = source[wnum]
        collect_contexts(slw, cnum, dct)
    rules = list(gen_rules(
        dct,
        {'rtype': rule, 'tags': tags1, 'desttags': tags2},
        include_parent=(rule == 'rem-parent')))
    rules.sort(key=lambda x: x[3], reverse=True)
    cur.executemany('INSERT INTO context VALUES(?, ?, ?, ?)',
                    rules[:args.beam])
    con.commit()

if PROFILE:
    profiler.disable()
    profiler.dump_stats('round5.context2.stats')
