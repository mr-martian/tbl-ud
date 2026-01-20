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

def parse_conllu(block):
    ret = []
    for line in block.splitlines():
        cols = line.strip().split('\t')
        if len(cols) != 10 or not cols[0].isdigit():
            continue
        feats = set() if cols[5] == '_' else set(cols[5].split('|'))
        ret.append(APWord(lemma='"'+cols[2]+'"',
                          pos=cols[2],
                          tags=feats | {'@'+cols[7]}))
    return ret


@dataclass
class Sentence(BaseSentence):
    source_words: dict = field(default_factory=dict)
    alignments: dict = field(default_factory=dict)

    @staticmethod
    def from_input(src, tgt):
        ret = Sentence(source=src, target=tgt)
        ret.heads[0] = 0
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
        ret.wl = WindowLinearizer(ret.source)
        return ret

    def describe_word(self, wid):
        yield from self.source_words[wid].describe()

    def before(self, a, b):
        # is a unambiguously before b in the target data?
        return self.alignments[a][-1] < self.alignments[b][0]

def load_corpus(src, tgt):
    with open(src, 'rb') as fin:
        source = list(parse_binary_stream(fin, windows_only=True))

    #with open(tgt) as fin:
    #    target = [parse_apertium(block) for block in fin.read().split('\n\n')]
    with open(tgt) as fin:
        target = [parse_conllu(block) for block in fin.read().split('\n\n')]

    return [Sentence.from_input(s, t) for s, t in zip(source, target)]

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

    with open(args.output_rules, 'w') as fout:

        if args.initial_rules:
            parse_rule_file(args.initial_rules)
            with open(args.initial_rules) as fin:
                fout.write(fin.read() + '\n')

        corpus = load_corpus(args.source, args.target)

        for i in range(args.iterations):
            print(i)
            rule = generate_rule(corpus, args.count)
            if rule is None:
                break
            fout.write(rule.to_string() + '\n')
            for sent in corpus:
                sent.wl.add_rule(rule, len(ALL_RULES))
            ALL_RULES.append(rule)
