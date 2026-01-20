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

@dataclass
class Sentence(BaseSentence):
    idmap: dict = field(default_factory=dict)

    @staticmethod
    def from_input(src, tgt):
        ret = Sentence(source=src, target=tgt)
        ret.heads[0] = 0
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
        ret.wl = WindowLinearizer(ret.source)
        return ret

    def before(self, a, b):
        return self.idmap[a] < self.idmap[b]

    def describe_word(self, wid):
        w = self.target[self.idmap[wid]]
        # TODO: features
        yield {'@'+w.relation}
        yield {w.upos}
        yield {'"'+w.lemma+'"', w.upos}
        yield {'"'+w.lemma+'"', w.relation}

@dataclass
class Trainer(BaseTrainer):
    def load_corpus(self, src, tgt):
        with open(src, 'rb') as fin:
            source = list(parse_binary_stream(fin, windows_only=True))

        with open(tgt) as fin:
            target = [parse_conllu(block)
                      for block in fin.read().split('\n\n')]

        for s, t in zip(source, target):
            align_tree(s, t)
            self.corpus.append(Sentence.from_input(s, t))

if __name__ == '__main__':
    t = Trainer()
    t.cli()
