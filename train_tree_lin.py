from linearize import *

def ud_get_paths(tree):
    paths = [None] * len(tree)
    def get_path(n):
        nonlocal paths
        if n == 0:
            return ''
        if paths[n-1] is None:
            pfx = tree[n-1].lemma + '@' + tree[n-1].deprel
            base = get_path(int(tree[n-1].head))
            paths[n-1] = pfx + base
        return paths[n-1]
    for w in tree:
        get_path(int(w.idx))
    return {i+1: paths[i] for i, w in enumerate(tree)}

def cg_get_paths(window):
    base_rels = []
    lems = []
    locs = {}
    for i, c in enumerate(window.cohorts):
        r = utils.primary_reading(c)
        locs[c.dep_self] = i
        base_rels.append([t for t in r.tags if t[0] == '@'][0])
        lems.append(r.lemma[1:-1])
    paths = [None] * len(window.cohorts)
    def get_path(ds):
        nonlocal paths
        if ds == 0:
            return ''
        n = locs[ds]
        if paths[n] is None:
            pfx = lems[n] + base_rels[n]
            base = get_path(window.cohorts[n].dep_parent)
            paths[n] = pfx + base
        return paths[n]
    for c in window.cohorts:
        get_path(c.dep_self)
    ret = defaultdict(list)
    for i, pth in enumerate(paths):
        ret[pth].append(i)
    return ret

@dataclass
class Sentence(BaseSentence):
    idmap: dict = field(default_factory=dict)

    def preprocess(self):
        spth = cg_get_paths(self.source)
        tpth = ud_get_paths(self.target)
        ct = Counter()
        for w in self.target:
            tp = tpth[int(w.idx)]
            i = ct[tp]
            ct[tp] += 1
            ch = self.source.cohorts[spth[tp][i]]
            self.idmap[ch.dep_self] = int(w.idx) - 1
        self.idmap[0] = -1

    def before(self, a, b):
        return self.idmap[a] < self.idmap[b]

@dataclass
class Trainer(BaseTrainer):
    sentence_class = Sentence

if __name__ == '__main__':
    t = Trainer()
    t.cli()
