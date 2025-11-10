from linearize import *

@dataclass
class UDWord:
    cgid: int = 0
    headid: int = 0
    lemma: str = ''
    upos: str = ''
    relation: str = ''
    feats: set = field(default_factory=set)
    index: int = 0
    head: int = -1

def parse_conllu(block):
    ret = []
    for line in block.splitlines():
        cols = line.strip().split('\t')
        if len(cols) != 10 or not cols[0].isdigit():
            continue
        feats = set() if cols[5] == '_' else set(cols[5].split('|'))
        ret.append(UDWord(index=int(cols[0]),
                          lemma=cols[2],
                          upos=cols[3],
                          feats=feats,
                          head=int(cols[6]),
                          relation=cols[7]))
    return ret

ENUMERATED_RELS = {'conj', 'parataxis', 'advcl', 'mark', 'cc'}

def ud_get_paths(tree):
    base_rels = []
    enum = Counter()
    for i, w in enumerate(tree):
        r = w.relation
        if r in ENUMERATED_RELS:
            n = enum[(r, w.head)]
            enum[(r, w.head)] += 1
            r += str(n)
        base_rels.append(r)
    paths = [None] * len(tree)
    def get_path(n):
        nonlocal paths
        if n == 0:
            return ''
        if paths[n-1] is None:
            paths[n-1] = tree[n-1].lemma + '@' + base_rels[n-1] + get_path(tree[n-1].head)
        return paths[n-1]
    for w in tree:
        get_path(w.index)
    return {i+1: paths[i] for i, w in enumerate(tree)}

def cg_get_paths(window):
    base_rels = []
    lems = []
    locs = {}
    enum = Counter()
    for i, c in enumerate(window.cohorts):
        locs[c.dep_self] = i
        for r in c.readings:
            if 'SOURCE' in r.tags:
                continue
            base_rels.append([t for t in r.tags if t[0] == '@'][0])
            lems.append(r.lemma[1:-1])
            break
        if base_rels[-1][1:] in ENUMERATED_RELS:
            n = enum[(base_rels[-1], c.dep_parent)]
            enum[(base_rels[-1], c.dep_parent)] += 1
            base_rels[-1] += str(n)
    paths = [None] * len(window.cohorts)
    def get_path(ds):
        nonlocal paths
        if ds == 0:
            return ''
        n = locs[ds]
        if paths[n] is None:
            paths[n] = lems[n] + base_rels[n] + get_path(window.cohorts[n].dep_parent)
        return paths[n]
    for c in window.cohorts:
        get_path(c.dep_self)
    return {pth: i for i, (lm, pth) in enumerate(zip(lems, paths))}

def align_tree(src, tgt):
    spth = cg_get_paths(src)
    tpth = ud_get_paths(tgt)
    if len(spth) != len(tpth):
        print(spth)
        print(tpth)
        c = Counter(tpth.values())
        print(c.most_common(3))
        raise ValueError()
    for w in tgt:
        ch = src.cohorts[spth[tpth[w.index]]]
        w.cgid = ch.dep_self
        w.headid = ch.dep_parent

from cg3 import Window
@dataclass
class Sentence:
    source: Window = None
    target: list = field(default_factory=list)
    tagset: set = field(default_factory=set)
    idmap: dict = field(default_factory=dict)
    heads: dict = field(default_factory=dict)
    base_score: int = None

    @staticmethod
    def from_input(src, tgt):
        ret = Sentence(source=src, target=tgt)
        ss = set()
        for cohort in src.cohorts:
            for reading in cohort.readings:
                if 'SOURCE' in reading.tags:
                    continue
                ret.tagset.add(reading.lemma)
                ret.tagset.update(reading.tags)
                break
            ss.add(cohort.dep_self)
        ts = set()
        for i, word in enumerate(tgt):
            ret.idmap[word.cgid] = i
            ret.heads[word.cgid] = word.headid
            ts.add(word.cgid)
        return ret

    def score(self, extra_rules):
        wl = WindowLinearizer(self.source, extra_rules)
        seq = [s[0] for s in wl.sequence]
        score = 0
        # TODO: is this the best metric?
        for idx, i in enumerate(seq):
            for j in seq[idx:]:
                if self.idmap[j] < self.idmap[i]:
                    score += 1
        return score

    def describe_word(self, wid):
        w = self.target[self.idmap[wid]]
        # TODO: features
        yield {'@'+w.relation}
        yield {w.upos}
        yield {'"'+w.lemma+'"', w.upos}
        yield {'"'+w.lemma+'"', w.relation}

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
                if self.idmap[j] < self.idmap[i]:
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
        target = [parse_conllu(block) for block in fin.read().split('\n\n')]

    ret = []
    i = 0
    for s, t in zip(source, target):
        i += 1
        align_tree(s, t)
        ret.append(Sentence.from_input(s, t))
    return ret

def generate_rule(corpus, count=100):
    rule_freq = Counter()
    rules = {}
    for sent in corpus:
        for rule in sent.gen_rules():
            rs = rule.to_string()
            rule_freq[rs] += 1
            if rs not in rules:
                rules[rs] = rule
    print('starting score', sum(s.base_score for s in corpus))
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
