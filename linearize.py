from cg3 import parse_binary_stream
from collections import defaultdict
from dataclasses import dataclass, field
import itertools
import sqlite3

ALL_RULES = []
TAGS_TO_RULES = defaultdict(set)

@dataclass
class Rule:
    ltags: set = field(default_factory=set) # parent or left sibling
    rtags: set = field(default_factory=set) # child or right sibling
    weight: float = 0
    mode: str = 'L'
    # L = child on left
    # R = child on right
    # S = siblings in listed order
    # MR = shift right one space

def parse_rule(linenumber, line):
    global ALL_RULES, TAGS_TO_RULES
    ls = line.strip().split('\t')
    if len(ls) != 4:
        raise ValueError(f'{linenumber} does not have 4 columns')
    r = Rule()
    r.mode = ls[0]
    r.ltags = set(ls[1].split('|'))
    r.rtags = set(ls[2].split('|'))
    r.weight = float(ls[3])
    for t in r.ltags | r.rtags:
        TAGS_TO_RULES[t].add(len(ALL_RULES))
    ALL_RULES.append(r)

def parse_rule_file(fname):
    with open(fname) as fin:
        for i, line in enumerate(fin, 1):
            if line.strip():
                parse_rule(i, line)

class WindowLinearizer:
    def __init__(self, window):
        self.layers = defaultdict(list)
        self.lrules = defaultdict(set)
        self.rrules = defaultdict(set)
        self.readings = {}
        self.linearized = {}
        self.shifts = []
        self.relations = defaultdict(set)
        for cohort in window.cohorts:
            self.process_cohort(cohort)
        for head in self.layers:
            self.process_layer(head)
        self.sequence = list(self.extract(0))
        for sh in self.shifts:
            for i, w in enumerate(self.sequence):
                if w[0] == sh and i + 1 < len(self.sequence):
                    self.sequence[i], self.sequence[i+1] = self.sequence[i+1], self.sequence[i]
                    break

    def process_cohort(self, cohort):
        self.layers[cohort.dep_parent].append(cohort.dep_self)
        self.layers[cohort.dep_self].append(cohort.dep_self)
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            self.readings[cohort.dep_self] = [reading.lemma] + reading.tags
            for t in reading.tags:
                if t[0] == '@':
                    self.relations[t].add(cohort.dep_self)
                    break
            break
        pat = set(self.readings[cohort.dep_self])
        for i, r in enumerate(ALL_RULES):
            if r.ltags <= pat:
                if r.mode == 'MR':
                    self.shifts.append(cohort.dep_self)
                else:
                    self.lrules[cohort.dep_self].add(i)
            if r.rtags <= pat:
                self.rrules[cohort.dep_self].add(i)

    def process_layer(self, head):
        layer = self.layers[head]
        if len(layer) == 1:
            self.linearized[head] = layer
            return
        weights = [[0 for i in layer] for j in layer]
        for i, wi in enumerate(layer):
            for j, wj in enumerate(layer):
                if wj == head:
                    continue
                if i == j:
                    continue
                rules = self.lrules[wi] & self.rrules[wj]
                for ri in rules:
                    rl = ALL_RULES[ri]
                    if wi == head:
                        if rl.mode == 'L':
                            weights[j][i] += rl.weight
                        else:
                            weights[i][j] += rl.weight
                    elif rl.mode == 'S':
                        weights[i][j] += rl.weight
        best_row = layer
        best_score = 0
        for row in itertools.permutations(list(range(len(layer)))):
            score = 0
            for idx, i in enumerate(row):
                for j in row[idx+1:]:
                    score += weights[i][j]
            if score > best_score:
                best_row = [layer[i] for i in row]
                best_score = score
        self.linearized[head] = best_row

    def extract(self, head):
        for i in self.linearized[head]:
            if i == head:
                yield (i, self.readings[i])
            else:
                yield from self.extract(i)

def linearize_file(fname):
    with open(fname, 'rb') as fin:
        for window in parse_binary_stream(fin, windows_only=True):
            seq = WindowLinearizer(window).sequence
            print('\n'.join(' '.join(w[1]) for w in seq))
            # TODO: how best to output?
            break # @TEST TODO

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('rules')
    parser.add_argument('input')
    args = parser.parse_args()

    parse_rule_file(args.rules)
    linearize_file(args.input)
