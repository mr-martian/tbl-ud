#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import sqlite3
from typing import Optional

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('db')
parser.add_argument('--count', type=int, default=100,
                    help='number of templates to expand')
args = parser.parse_args()

con = sqlite3.connect(args.db)
cur = con.cursor()
cur.execute('CREATE TABLE context(rule, relation, window)')
con.commit()

with open(args.source, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin))

with open(args.target, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin))

@dataclass(frozen=True, order=True)
class Rule:
    rtype: str
    target: str
    tags: Optional[str] = None
    desttags: Optional[str] = None
    context: frozenset[str] = field(default_factory=frozenset)

    templates = {
        'remove': 'REMOVE ({tags}) IF (0 ({target})) {ctx} ;',
        'append': 'APPEND ({tags}) (*) IF (0 ({target})){ctx} ;',
        'addcohort': 'ADDCOHORT ("<ins>" {tags}) BEFORE (*) IF (0 ({target})){ctx} ;',
        'rem-self': 'REMCOHORT (*) IF (0 ({target})){ctx} ;',
        'rem-parent': 'WITH (*) IF (0 ({target})){ctx} {{\n\tSWITCHPARENT WITHCHILD (*) (*) ;\n\tREMCOHORT _C2_ ;\n}} ;',
        'SUBSTITUTE': 'SUBSTITUTE ({tags}) ({desttags}) (*) IF (0 ({target})) {ctx} ;',
    }

    def as_relation_rule(self, key):
        ret = []
        ret.append(f'ADDRELATION (t{key}) (*) (0 ({self.target})) TO (0 (*)) ;')
        for test in self.context:
            ret.append(f'ADDRELATION ({key}) (*) (0 ({self.target})) TO ({test}) ;')
        return '\n'.join(ret)

    def as_rule(self):
        ctx = ' '.join(f'({test})' for test in sorted(self.context))
        if ctx:
            ctx = ' ' + ctx
        return self.templates[self.rtype].format(
            target=self.target, tags=self.tags, desttags=self.desttags,
            ctx=ctx)

def describe_cohort(cohort):
    yield f'{cohort.static.lemma} {cohort.static.tags[0]}'

def gen_contexts(slw, idx, dct, include_parent=False):
    ctx = []
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
                ctx.append(f'{rel} ({desc})')
    tgt = list(describe_cohort(slw.cohorts[idx]))
    for t in tgt:
        if not include_parent:
            yield Rule(target=t, **dct)
        for c in ctx:
            if include_parent and c[0] != 'p':
                continue
            yield Rule(target=t, context=frozenset([c]), **dct)

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
            rules.append((r.as_rule(), r.as_relation_rule('{key}'), wnum))
    cur.executemany('INSERT INTO context VALUES(?, ?, ?)', rules)
    con.commit()

