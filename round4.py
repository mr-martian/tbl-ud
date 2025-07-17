#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

from collections import Counter, defaultdict
import concurrent.futures
from dataclasses import dataclass, field
import os
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Optional

COHORT_WEIGHT = 10
READING_WEIGHT = 5
FEATURE_WEIGHT = 1

MAX_RULES = 10

@dataclass(frozen=True, order=True)
class Rule:
    rtype: str
    target: str
    tags: Optional[str] = None
    desttags: Optional[str] = None
    context: frozenset[str] = field(default_factory=frozenset)

    templates = {
        'REMOVE': 'REMOVE ({tags}) IF (0 ({target})) {ctx} ;',
        'APPEND': 'APPEND ({tags}) ({target}){ctx} ;',
        'ADDCOHORT': 'ADDCOHORT ("<ins>" {tags}) BEFORE ({target}){ctx} ;',
        'REMCOHORT': 'REMCOHORT ({target}){ctx} ;',
        'REMCOHORT-center': 'WITH ({target}) IF (p (*)) {ctx} {{\n\tSWITCHPARENT WITHCHILD (*) (*) ;\n\tREMCOHORT _C1_ ;\n}} ;',
        'SUBSTITUTE': 'SUBSTITUTE ({tags}) ({desttags}) ({target}){ctx} ;',
    }

    def as_relation_rule(self, key):
        ret = []
        for test in self.context:
            ret.append(f'ADDRELATION ({key}) ({self.target}) TO ({test}) ;')
        return '\n'.join(ret)

    def as_rule(self):
        ctx = ' '.join(f'({test})' for test in sorted(self.context))
        if ctx and self.rtype not in ['REMCOHORT-center', 'REMOVE']:
            ctx = ' IF ' + ctx
        return self.templates[self.rtype].format(
            target=self.target, tags=self.tags, desttags=self.desttags,
            ctx=ctx)

class Learner:
    def __init__(self, source: str, target: str):
        self.source_fname = source
        self.target_fname = target

        self.source = self.load_file(self.source_fname)
        self.target = self.load_file(self.target_fname)

        #self.base_score = sum(self.score_window(s, t)
        #                      for s, t in zip(self.source, self.target))
        self.base_score = self.score_window(self.source[0], self.target[0])

    def load_file(self, fname: str):
        with open(fname, 'rb') as fin:
            return list(cg3.parse_binary_stream(fin))
        
    def run_grammar(self, gpath: str, opath: str, debug=True):
        with NamedTemporaryFile() as fgram:
            cc = subprocess.run(['cg-comp', gpath, fgram.name],
                                capture_output=True)
            cp = subprocess.run(
                ['/home/daniel/apertium/cg3/src/cg-proc', '-f3',
                 fgram.name, self.source_fname, opath],
                capture_output=True)
            if debug:
                print('')
                print(cc)
                print(cp)
            with open(opath, 'rb') as fout:
                yield from cg3.parse_binary_stream(fout)

    def calc_intersection(self, rules: list[tuple[int, Rule]],
                          gpath: str, opath: str):
        if not rules:
            return []
        with open(gpath, 'w') as fout:
            for i, (s, r) in enumerate(rules):
                fout.write(r.as_relation_rule(f'r{i}') + '\n')
        targets = defaultdict(set)
        contexts = defaultdict(set)
        for window in self.run_grammar(gpath, opath, True):
            for cohort in window.cohorts:
                for tag, heads in cohort.relations:
                    if tag[0] == 'r' and tag[1:].isdigit():
                        contexts[int(tag[1:])].update(heads)
                        targets[int(tag[1:])].add(cohort.dep_self)
        intersections = [set() for i in range(len(rules))]
        for i in range(len(rules)):
            for j in range(i):
                if (targets[i] & targets[j]
                    or targets[i] & contexts[j]
                    or targets[j] & contexts[i]):
                    intersections[i].add(j)
                    intersections[j].add(i)
        return intersections

    def describe_cohort(self, cohort):
        yield f'{cohort.static.lemma} {cohort.static.tags[0]}'

    def gen_contexts(self, slw, idx, dct):
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
                for desc in self.describe_cohort(cohort):
                    ctx.append(f'{rel} ({desc})')
        tgt = list(self.describe_cohort(slw.cohorts[idx]))
        for t in tgt:
            yield Rule(target=t, **dct)
            for c in ctx:
                yield Rule(target=t, context=frozenset([c]), **dct)

    def gen_rules(self, slw: cg3.Window, tlw: cg3.Window):
        src_words = set((r.lemma, r.tags[0]) for c in slw.cohorts
                        for r in c.readings)
        tgt_words = set((r.lemma, r.tags[0]) for c in tlw.cohorts
                        for r in c.readings)
        extra = src_words - tgt_words
        missing = tgt_words - src_words
        for idx, cohort in enumerate(slw.cohorts):
            words = set((r.lemma, r.tags[0]) for r in cohort.readings)
            if words.isdisjoint(tgt_words):
                yield from self.gen_contexts(slw, idx, {
                    'rtype': 'REMCOHORT-center' if any(
                        c.dep_parent == cohort.dep_self
                        for c in slw.cohorts) else 'REMCOHORT'})
                for m in missing:
                    yield from self.gen_contexts(slw, idx, {
                        'rtype': 'APPEND',
                        'tags': ' '.join(m),
                    })
            if len(words) > 1:
                print('REMOVE', words, cohort)
                for w in words:
                    yield from self.gen_contexts(slw, idx, {
                        'rtype': 'REMOVE',
                        'tags': ' '.join(w),
                    })
            for m in missing:
                yield from self.gen_contexts(slw, idx, {
                    'rtype': 'ADDCOHORT',
                    'tags': ' '.join(m),
                })
            # TODO: SUBSTITUTE

    def score_window(self, slw, tlw):
        #print(tlw)
        score = abs(len(slw.cohorts) - len(tlw.cohorts)) * COHORT_WEIGHT
        #print(f'{len(slw.cohorts)=}, {len(tlw.cohorts)=}, {score=}')
        src_words = set((r.lemma, r.tags[0]) for c in slw.cohorts
                        for r in c.readings)
        tgt_words = set((r.lemma, r.tags[0]) for c in tlw.cohorts
                        for r in c.readings)
        #print(f'{src_words=}')
        #print(f'{tgt_words=}')
        score += READING_WEIGHT * (len(src_words) - len(slw.cohorts))
        # TODO: handle ambiguity on target side
        score += READING_WEIGHT * len(src_words.symmetric_difference(tgt_words))
        # TODO: feature mismatches
        return score

    def score_rule(self, rule, gpath, opath):
        with open(gpath, 'w') as fout:
            fout.write('OPTIONS += addcohort-attach ;\n')
            fout.write(rule.as_rule())
        score = 0
        for slw, tlw in zip(self.run_grammar(gpath, opath), self.target):
            score += self.score_window(slw, tlw)
            break
        return (score, rule)

    def generate(self):
        with (concurrent.futures.ThreadPoolExecutor() as executor,
              TemporaryDirectory() as tmpdir):
            seen = set()
            future_to_rule = {}
            for slw, tlw in zip(self.source, self.target):
                for rule in self.gen_rules(slw, tlw):
                    if rule in seen:
                        continue
                    seen.add(rule)
                    gpath = os.path.join(tmpdir, f'g{len(seen):05}.cg3')
                    opath = os.path.join(tmpdir, f'o{len(seen):05}.bin')
                    future = executor.submit(
                        Learner.score_rule, self, rule, gpath, opath)
                    future_to_rule[future] = rule
                    if len(seen) > MAX_RULES:
                        break
                if len(seen) > MAX_RULES:
                    break
            rules = []
            print(self.base_score)
            for future in concurrent.futures.as_completed(future_to_rule):
                res = future.result()
                print(res[0], res[1].as_rule())
                if res[0] < self.base_score - 100: # TODO
                    rules.append(res)
            rules.sort()
            gpath = os.path.join(tmpdir, 'intersection.cg3')
            opath = os.path.join(tmpdir, 'intersection_output.bin')
            intersections = self.calc_intersection(rules, gpath, opath)
            added = set()
            for i, (score, rule) in enumerate(rules):
                if intersections[i] & added:
                    continue
                yield rule
                added.add(i)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('src')
    parser.add_argument('tgt')
    parser.add_argument('out')
    args = parser.parse_args()
    l = Learner(args.src, args.tgt)
    with open(args.out, 'a') as fout:
        for r in l.generate():
            fout.write('\n' + r.as_rule() + '\n')
