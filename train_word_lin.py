from linearize import *
from cg3 import Window
from functools import cached_property

@dataclass
class APWord:
    lemma: str = ''
    pos: str = ''
    tags: set = field(default_factory=set)

    @cached_property
    def relation(self):
        for t in self.tags:
            if t[0] == '@':
                return t

    def describe(self):
        yield {self.relation}
        yield {self.pos}
        yield {self.lemma, self.pos}
        yield {self.lemma, self.relation}

def parse_apertium(line):
    # be very lazy for now
    words = []
    for blob in line.split('^'):
        blob2 = blob.split('>$')
        if len(blob2) == 1:
            continue
        ls = blob2[0].split('><')
        w = APWord()
        w.lemma, w.pos = ls[0].split('<')
        w.lemma = '"' + w.lemma + '"'
        w.tags.update(ls[1:])
        words.append(w)
    return words

@dataclass
class Sentence:
    source: Window = None
    source_words: dict = field(default_factory=dict)
    target: list = field(default_factory=list)
    tagset: set = field(default_factory=set)
    alignments: dict = field(default_factory=dict)
    heads: dict = field(default_factory=dict)
    base_score: int = None

    @staticmethod
    def from_input(src, tgt):
        ret = Sentence(source=src, target=tgt)
        ttags = defaultdict(list)
        all_ttags = []
        for i, w in enumerate(tgt):
            ttags[(w.lemma, w.pos)].append((i, w.tags))
            all_ttags.append((i, w.tags | {w.lemma, w.pos}))
        ss = set()
        for cohort in src.cohorts:
            for reading in cohort.readings:
                if 'SOURCE' in reading.tags:
                    continue
                ret.tagset.add(reading.lemma)
                ret.tagset.update(reading.tags)
                key = set(reading.tags[1:])
                ret.source_words[cohort.dep_self] = APWord(
                    lemma=reading.lemma, pos=reading.tags[0], tags=key)
                comp = ttags[(reading.lemma, reading.tags[0])]
                if not comp:
                    comp = all_ttags
                    key |= {reading.lemma, reading.tags[0]}
                options = defaultdict(list)
                for i, tg in comp:
                    options[(len(tg & key), len(tg | key))].append(i)
                ls = sorted(options.keys(), key=lambda x: x[0]/x[1])
                ret.alignments[cohort.dep_self] = options[ls[-1]]
                ret.heads[cohort.dep_self] = cohort.dep_parent
                break
        return ret

    def score(self, extra_rules):
        wl = WindowLinearizer(self.source, extra_rules)
        seq = [s[0] for s in wl.sequence]
        score = 0
        # TODO: is this the best metric?
        for idx, i in enumerate(seq):
            for j in seq[idx:]:
                # if they're obviously wrong
                if self.alignments[j][-1] < self.alignments[i][0]:
                    score += 1
        return score

    def describe_word(self, wid):
        yield from self.source_words[wid].describe()

    def expand_rule(self, left, right, mode, weight):
        for ltags in self.describe_word(left):
            for rtags in self.describe_word(right):
                yield Rule(ltags=ltags, rtags=rtags, weight=weight,
                           mode=mode)

    def gen_rules(self):
        wl = WindowLinearizer(self.source)
        seq = [s[0] for s in wl.sequence]
        self.base_score = 0
        for idx, i in enumerate(seq):
            for j in seq[idx:]:
                if self.alignments[j][-1] < self.alignments[i][0]:
                    self.base_score += 1
                    if self.heads[i] == j:
                        yield from self.expand_rule(
                            j, i, 'R',
                            max(wl.get_weight_difference(j, i, j) + 1, 1))
                    elif self.heads[j] == i:
                        yield from self.expand_rule(
                            i, j, 'L',
                            max(wl.get_weight_difference(i, i, j) + 1, 1))
                    elif self.heads[i] == self.heads[j]:
                        h = self.heads[i]
                        yield from self.expand_rule(
                            j, i, 'S',
                            max(wl.get_weight_difference(h, i, j) + 1, 1))
                    else:
                        pass # TODO: shift rules

def load_corpus(src, tgt):
    with open(src, 'rb') as fin:
        source = list(parse_binary_stream(fin, windows_only=True))

    with open(tgt) as fin:
        target = [parse_apertium(block) for block in fin.read().split('\n\n')]

    return [Sentence.from_input(s, t) for s, t in zip(source, target)]

def generate_rule(corpus, count=100):
    rule_freq = Counter()
    rules = {}
    for sent in corpus:
        for rule in sent.gen_rules():
            rs = rule.to_string()
            rule_freq[rs] += 1
            if rs not in rules:
                rules[rs] = rule
    print(sum(s.base_score for s in corpus))
    results = []
    for rs, _ in rule_freq.most_common(count):
        rule = rules[rs]
        diff = 0
        for sent in corpus:
            if rule.ltags < sent.tagset and rule.rtags < sent.tagset:
                diff += sent.score([rule]) - sent.base_score
        #print(diff, rs)
        if diff < 0:
            results.append((diff, rule))
    if results:
        results.sort(key=lambda x: (x[0], x[1].to_string()))
        print('SELECT', results[0][0], results[0][1])
        return results[0][1]

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('target')
    parser.add_argument('output_rules')
    parser.add_argument('--initial_rules', action='store')
    parser.add_argument('--iterations', type=int, default=10)
    parser.add_argument('--count', type=int, default=100)
    args = parser.parse_args()

    corpus = load_corpus(args.source, args.target)

    with open(args.output_rules, 'w') as fout:

        if args.initial_rules:
            parse_rule_file(args.initial_rules)
            with open(args.initial_rules) as fin:
                fout.write(fin.read() + '\n')

        for i in range(args.iterations):
            print(i)
            rule = generate_rule(corpus, args.count)
            if rule is None:
                break
            fout.write(rule.to_string() + '\n')
            ALL_RULES.append(rule)
