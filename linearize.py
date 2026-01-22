from cg3 import parse_binary_stream, Window
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
    # F = front (place child before first aunt)
    # B = back (place child after last aunt)

    def to_string(self):
        l = '|'.join(sorted(self.ltags)) or '_'
        r = '|'.join(sorted(self.rtags)) or '_'
        return f'{self.mode}\t{l}\t{r}\t{self.weight}'

def parse_rule(linenumber, line):
    ls = line.strip().split('\t')
    if len(ls) != 4:
        raise ValueError(f'Line {linenumber} does not have 4 columns')
    r = Rule()
    r.mode = ls[0]
    if ls[1] != '_':
        r.ltags = set(ls[1].split('|'))
    if ls[2] != '_':
        r.rtags = set(ls[2].split('|'))
    r.weight = float(ls[3])
    return r

def parse_rule_file(fname, to_global=True):
    ret = []
    with open(fname) as fin:
        for i, line in enumerate(fin, 1):
            if line.strip():
                ret.append(parse_rule(i, line))
    if to_global:
        global ALL_RULES
        ALL_RULES += ret
    return ret

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
        self.heads = {0: 0}
        self.fronting = defaultdict(Counter)
        self.backing = defaultdict(Counter)
        self.extra_fronting = defaultdict(Counter)
        self.extra_backing = defaultdict(Counter)
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
                        elif rl.mode == 'R':
                            weights[i][j] += rl.weight
                        elif rl.mode == 'B':
                            self.backing[self.heads[wi]][wj] += rl.weight
                        elif rl.mode == 'F':
                            self.fronting[self.heads[wi]][wj] += rl.weight
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

    def is_moved(self, i):
        gp = self.heads[self.heads[i]]
        fw = self.fronting[gp][i] + self.extra_fronting[gp][i]
        bw = self.backing[gp][i] + self.extra_backing[gp][i]
        return ((fw - max(bw, 0)) > 0 or (bw - max(fw, 0)) > 0)

    def extract(self, head):
        front_plain = self.fronting[head] + self.extra_fronting[head]
        back_plain = self.backing[head] + self.extra_backing[head]
        # double + because negative backing != fronting
        front = +(front_plain - (+back_plain))
        back = +(back_plain - (+front_plain))
        for n, w in front.most_common():
            yield from self.extract(n)
        for i in self.linearized[head]:
            if i == head:
                yield i
            elif self.is_moved(i):
                continue
            else:
                yield from self.extract(i)
        for n, w in reversed(back.most_common()):
            yield from self.extract(n)

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
                elif head in left and rule.mode in ['F', 'B']:
                    for r in layer:
                        if r == head or r not in right:
                            continue
                        gp = self.heads[head]
                        if index is None:
                            if rule.mode == 'F':
                                self.extra_fronting[gp][r] += rule.weight
                            else:
                                self.extra_backing[gp][r] += rule.weight
                        else:
                            if rule.mode == 'F':
                                self.fronting[gp][r] += rule.weight
                            else:
                                self.backing[gp][r] += rule.weight
        orig_lin = {}
        for head in update:
            orig_lin[head] = self.linearized[head][:]
            self.process_layer(head, temp_weights)
        seq = list(self.extract(0))
        self.apply_shifts(seq, extra_shifts)

        assert(len(self.sequence) == len(seq))

        if index is None:
            self.linearized.update(orig_lin)
            self.extra_fronting.clear()
            self.extra_backing.clear()
        else:
            self.sequence = seq
            self.shifts += extra_shifts
        return seq

    def get_weight_difference(self, head, left, right):
        l = self.layers[head].index(left)
        r = self.layers[head].index(right)
        return self.weights[head][l][r] - self.weights[head][r][l]

def linearize_file(fname, format='cg'):
    with open(fname, 'rb') as fin:
        for idx, window in enumerate(parse_binary_stream(
                fin, windows_only=True)):
            wl = WindowLinearizer(window)
            seq = wl.sequence
            rd = wl.readings
            if format == 'conllu':
                print('# sent_id = s%d' % idx)
            for i, n in enumerate(seq, 1):
                h = wl.heads[n]
                if h != 0:
                    h = seq.index(h) + 1
                if format == 'cg':
                    print('"<surf>"\n\t' + ' '.join(rd[n]), f'#{i}->{h}')
                else:
                    tags = rd[n]
                    feats = [t for t in tags if '=' in t]
                    rels = [t for t in tags if t[0] == '@']
                    rel = '_'
                    if rels:
                        rel = rels[0][1:]
                    print(i, '_', tags[0][1:-1], tags[1], '_',
                          ('|'.join(feats) or '_'), h, rel, '_', '_',
                          sep='\t')
            print()

@dataclass
class BaseSentence:
    source: Window = None
    target: list = field(default_factory=list)
    tagset: set = field(default_factory=set)
    heads: dict = field(default_factory=dict)
    base_score: int = 0
    wl: WindowLinearizer = None

    @staticmethod
    def from_input(src, tgt):
        raise NotImplementedError

    def before(self, a, b):
        # return True if a is unambiguously before b in the correct order
        raise NotImplementedError

    def describe_word(self, wid):
        raise NotImplementedError

    def wrong_pairs(self, seq=None):
        s = seq or self.wl.sequence
        for idx, i in enumerate(s):
            for j in s[idx:]:
                if self.before(j, i):
                    yield i, j

    def score(self, rule):
        seq = self.wl.add_rule(rule)
        return len(list(self.wrong_pairs(seq)))

    def weight(self, head, i, j):
        return max(self.wl.get_weight_difference(head, i, j) + 1, 1)

    def expand_rule(self, left, right, mode, weight):
        for ltags in self.describe_word(left):
            if mode == 'MR':
                yield Rule(ltags=ltags, mode=mode)
                continue
            for rtags in self.describe_word(right):
                yield Rule(ltags=ltags, rtags=rtags, weight=weight,
                           mode=mode)

    def gen_rules(self):
        self.base_score = 0
        for i, j in self.wrong_pairs():
            self.base_score += 1
            if self.heads[i] == j:
                yield from self.expand_rule(j, i, 'R', self.weight(j, i, j))
            elif self.heads[j] == i:
                yield from self.expand_rule(i, j, 'L', self.weight(i, i, j))
            elif self.heads[i] == self.heads[j]:
                h = self.heads[i]
                yield from self.expand_rule(j, i, 'S', self.weight(h, i, j))
            elif (self.heads[i] == self.heads[self.heads[j]] and
                  self.before(i, self.heads[j]) and
                  all(self.before(i, x) or self.heads[i] != self.heads[x]
                      for x in self.wl.sequence)):
                w = 1 - self.wl.fronting[self.heads[i]][j]
                w += max(self.wl.backing[self.heads[i]][j], 0)
                yield from self.expand_rule(self.heads[j], j, 'F', w)
            elif (self.heads[j] == self.heads[self.heads[i]] and
                  self.before(self.heads[i], j) and
                  all(self.before(x, i) or self.heads[i] != self.heads[x]
                      for x in self.wl.sequence)):
                w = 1 - self.wl.backing[self.heads[j]][i]
                w += max(self.wl.fronting[self.heads[j]][i], 0)
                yield from self.expand_rule(self.heads[i], i, 'F', w)
            # TODO: un-front, un-back
            elif (self.wl.sequence.index(i) + 1 == self.wl.sequence.index(j)
                  and not any(self.before(j, x) and self.before(x, i)
                              for x in self.wl.sequence)):
                yield from self.expand_rule(i, None, 'MR', 0)
            else:
                pass # no pattern, see if changes elsewhere fix it

@dataclass
class BaseTrainer:
    corpus: list = field(default_factory=list)
    iterations: int = 10
    count: int = 100

    def load_corpus(self, source, target):
        raise NotImplementedError

    def generate_rule(self):
        rule_freq = Counter()
        rules = {}
        for sent in self.corpus:
            for rule in sent.gen_rules():
                rs = rule.to_string()
                rule_freq[rs] += 1
                if rs not in rules:
                    rules[rs] = rule
        print('starting score', sum(s.base_score for s in self.corpus))
        results = []
        for rs, _ in rule_freq.most_common(self.count):
            rule = rules[rs]
            diff = 0
            for sent in self.corpus:
                if rule.ltags < sent.tagset and rule.rtags < sent.tagset:
                    diff += sent.score(rule) - sent.base_score
            #print(diff, rs)
            if diff < 0:
                results.append((diff, rule))
        if results:
            results.sort(key=lambda x: (x[0], x[1].to_string()))
            print('SELECT', results[0][0], results[0][1])
            return results[0][1]

    def training_loop(self, fout):
        global ALL_RULES
        for i in range(self.iterations):
            print(i)
            rule = self.generate_rule()
            if rule is None:
                break
            fout.write(rule.to_string() + '\n')
            for sent in self.corpus:
                sent.wl.add_rule(rule, len(ALL_RULES))
            ALL_RULES.append(rule)

    def cli(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('source')
        parser.add_argument('target')
        parser.add_argument('output_rules')
        parser.add_argument('--initial_rules', action='store')
        parser.add_argument('--iterations', type=int, default=10)
        parser.add_argument('--count', type=int, default=100)
        args = parser.parse_args()
        self.iterations = args.iterations
        self.count = args.count

        with open(args.output_rules, 'w') as fout:

            if args.initial_rules:
                parse_rule_file(args.initial_rules)
                with open(args.initial_rules) as fin:
                    fout.write(fin.read() + '\n')

            self.load_corpus(args.source, args.target)

            self.training_loop(fout)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('rules')
    parser.add_argument('input')
    parser.add_argument('--format', choices=['cg', 'conllu'], default='cg')
    args = parser.parse_args()

    parse_rule_file(args.rules)
    linearize_file(args.input, format=args.format)
