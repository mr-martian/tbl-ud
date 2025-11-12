from cg3 import parse_binary_stream
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import itertools

ALL_RULES = []

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

    def to_string(self):
        l = '|'.join(sorted(self.ltags)) or '_'
        r = '|'.join(sorted(self.rtags)) or '_'
        return f'{self.mode}\t{l}\t{r}\t{self.weight}'

def parse_rule(linenumber, line):
    global ALL_RULES
    ls = line.strip().split('\t')
    if len(ls) != 4:
        raise ValueError(f'{linenumber} does not have 4 columns')
    r = Rule()
    r.mode = ls[0]
    if ls[1] != '_':
        r.ltags = set(ls[1].split('|'))
    if ls[2] != '_':
        r.rtags = set(ls[2].split('|'))
    r.weight = float(ls[3])
    ALL_RULES.append(r)

def parse_rule_file(fname):
    with open(fname) as fin:
        for i, line in enumerate(fin, 1):
            if line.strip():
                parse_rule(i, line)

class WindowLinearizer:
    def __init__(self, window, extra_rules=None):
        self.layers = defaultdict(list)
        self.lrules = defaultdict(set)
        self.rrules = defaultdict(set)
        self.readings = {}
        self.linearized = {}
        self.shifts = []
        self.relations = defaultdict(set)
        self.weights = {}
        self.extra_rules = extra_rules or []
        self.heads = {}
        for cohort in window.cohorts:
            self.process_cohort(cohort)
        for head in self.layers:
            self.process_layer(head)
        self.sequence = list(self.extract(0))
        self.apply_shifts(self.sequence)

    def process_cohort(self, cohort):
        self.layers[cohort.dep_parent].append(cohort.dep_self)
        self.layers[cohort.dep_self].append(cohort.dep_self)
        self.heads[cohort.dep_self] = cohort.dep_parent
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            self.readings[cohort.dep_self] = [reading.lemma] + \
                [t for t in reading.tags if t != '<<<']
            for t in reading.tags:
                if t[0] == '@':
                    self.relations[t].add(cohort.dep_self)
                    break
            break
        pat = set(self.readings[cohort.dep_self])
        for i, r in enumerate(ALL_RULES + self.extra_rules):
            if r.ltags <= pat:
                if r.mode == 'MR':
                    self.shifts.append(cohort.dep_self)
                else:
                    self.lrules[cohort.dep_self].add(i)
            if r.rtags <= pat:
                self.rrules[cohort.dep_self].add(i)

    def calc_weights(self, head):
        if head in self.weights:
            return
        layer = self.layers[head]
        weights = [[0 for i in layer] for j in layer]
        for i, wi in enumerate(layer):
            for j, wj in enumerate(layer):
                if wj == head:
                    continue
                if i == j:
                    continue
                rules = self.lrules[wi] & self.rrules[wj]
                for ri in rules:
                    rl = (ALL_RULES + self.extra_rules)[ri]
                    if wi == head:
                        if rl.mode == 'L':
                            weights[j][i] += rl.weight
                        else:
                            weights[i][j] += rl.weight
                    elif rl.mode == 'S':
                        weights[i][j] += rl.weight
        self.weights[head] = weights

    def process_layer(self, head, temp_weights=None):
        layer = self.layers[head][:]
        if len(layer) == 1:
            self.linearized[head] = layer
            return
        self.calc_weights(head)

        def w(i, j):
            return (self.weights[head][i][j] +
                    (temp_weights or {}).get((layer[i], layer[j]), 0))

        best_row = [layer.index(head)]
        for n in range(len(layer)):
            if n in best_row:
                continue
            options = []
            before = [w(i, n) for i in best_row]
            after = [w(n, i) for i in best_row]
            score = sum(after)
            count = len([i for i in best_row if i < n])
            options = [(score, count, 0)]
            for i in range(len(best_row)):
                score -= after[i]
                score += before[i]
                if best_row[i] < n:
                    count += 1
                else:
                    count -= 1
                options.append((score, count, i+1))
            options.sort()
            best_row.insert(options[-1][-1], n)

        self.linearized[head] = [layer[n] for n in best_row]

    def extract(self, head):
        for i in self.linearized[head]:
            if i == head:
                yield i
            else:
                yield from self.extract(i)

    def apply_shifts(self, sequence, extra_shifts=None):
        for sh in (self.shifts + (extra_shifts or [])):
            for i, w in enumerate(sequence):
                if w == sh and i + 1 < len(sequence):
                    sequence[i], sequence[i+1] = sequence[i+1], sequence[i]
                    break

    def add_rule(self, rule, index=None):
        left = set()
        right = set()
        for cid, ctags in self.readings.items():
            if rule.ltags <= set(ctags):
                left.add(cid)
                if index is not None:
                    if rule.mode == 'MR':
                        self.shifts.append(cid)
                    else:
                        self.lrules[cid].add(index)
            if rule.rtags <= set(ctags):
                right.add(cid)
                if index is not None:
                    self.rrules[cid].add(index)
        update = set()
        temp_weights = {}
        extra_shifts = []
        def set_weight(head, a, b):
            nonlocal temp_weights, self, update
            update.add(head)
            if index is None:
                temp_weights[(a, b)] = rule.weight
            else:
                ai = self.layers[head].index(a)
                bi = self.layers[head].index(b)
                self.weights[head][ai][bi] += rule.weight
        if rule.mode == 'MR':
            extra_shifts = list(left)
        else:
            for head, layer in self.layers.items():
                if head in left and rule.mode in ['L', 'R']:
                    for r in layer:
                        if r == head or r not in right:
                            continue
                        a, b = (r, head) if rule.mode == 'L' else (head, r)
                        set_weight(head, a, b)
                elif rule.mode == 'S':
                    chs = set(layer) - {head}
                    for l in left & chs:
                        for r in right & chs:
                            if l == r:
                                continue
                            set_weight(head, l, r)
        orig_lin = {}
        for head in update:
            orig_lin[head] = self.linearized[head][:]
            self.process_layer(head, temp_weights)
        seq = list(self.extract(0))
        self.apply_shifts(seq, extra_shifts)

        assert(len(self.sequence) == len(seq))

        if index is None:
            self.linearized.update(orig_lin)
        else:
            self.sequence = seq
            self.shifts += extra_shifts
        return seq

    def get_weight_difference(self, head, left, right):
        l = self.layers[head].index(left)
        r = self.layers[head].index(right)
        return self.weights[head][l][r] - self.weights[head][r][l]

def linearize_file(fname):
    with open(fname, 'rb') as fin:
        for window in parse_binary_stream(fin, windows_only=True):
            wl = WindowLinearizer(window)
            seq = wl.sequence
            rd = wl.readings
            print('\n'.join(str(n) + ' '.join(rd[n]) for n in seq))
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
