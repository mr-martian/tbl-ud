import collections
from dataclasses import dataclass, field
import functools
import itertools

@dataclass
class Reading:
    lemma: str = ''
    tags: list[str] = field(default_factory=list)
    special_tags: list[str] = field(default_factory=list)
    active: bool = True

    @staticmethod
    def from_line(s):
        ls = s.split()
        ret = Reading()
        if ls[0] == ';':
            ret.active = False
            ls = ls[1:]
        if ls[0].startswith('"') and ls[0].endswith('"'):
            ret.lemma = ls[0][1:-1]
            if ret.lemma.startswith('<') and ret.lemma.endswith('>'):
                ret.lemma = ret.lemma[1:-1]
            ls = ls[1:]
        for tag in ls:
            if tag.startswith('src:') or tag.startswith('tgt:'):
                ret.tags.append(tag[4:])
            elif tag[0].isalpha():
                ret.tags.append(tag)
            else:
                ret.special_tags.append(tag)
        return ret

    @functools.cached_property
    def relation(self):
        for t in self.special_tags:
            if t.startswith('@'):
                return t

    @functools.cached_property
    def dep_info(self):
        for t in self.special_tags:
            if t.startswith('#'):
                s, h = t[1:].split('→')
                return (int(s), int(h))

@dataclass
class Cohort:
    source: Reading
    target: list[Reading]

    @staticmethod
    def from_lines(lines):
        return Cohort(Reading.from_line(lines[0]),
                      [Reading.from_line(l) for l in lines[1:]])

    @functools.cached_property
    def id(self):
        for r in self.target:
            for t in r.special_tags:
                if t.startswith('ID:'):
                    return int(t[3:])

    def all_readings(self):
        yield self.source
        yield from self.target

    @functools.cached_property
    def upos_set(self):
        return set(r.tags[0] for r in self.all_readings())

    @functools.cached_property
    def dep_info(self):
        for r in self.all_readings():
            if r.dep_info:
                return r.dep_info

    @functools.cached_property
    def relation(self):
        for r in self.all_readings():
            if r.relation:
                return r.relation

@dataclass
class Sentence:
    words: list[Cohort]

    @staticmethod
    def from_lines(lines):
        print(''.join(lines))
        ls = []
        last = 0
        alt_lines = lines + ['"']
        for i in range(1, len(alt_lines)):
            if alt_lines[i].startswith('"'):
                ls.append(Cohort.from_lines(alt_lines[last:i]))
                last = i
        return Sentence(ls)

    @functools.cached_property
    def by_upos(self):
        d = collections.defaultdict(list)
        for i, w in enumerate(self.words):
            for u in w.upos_set:
                d[u].append(i)
        return d

    @functools.cached_property
    def root(self):
        for i, w in enumerate(self.words):
            if w.dep_info and w.dep_info[1] == 0:
                return i

    def children(self, idx):
        n = self.words[idx].dep_info[0]
        for i, w in enumerate(self.words):
            if w.dep_info and w.dep_info[1] == n:
                yield i

def read_stream(fin):
    cur = []
    for line in fin:
        if not line.strip():
            yield Sentence.from_lines(cur)
            cur = []
        else:
            cur.append(line)
    if cur:
        yield Sentence.from_lines(cur)

def cohort_distance(c1, c2):
    c1_data = [(r.lemma, r.relation) for r in c1.all_readings()]
    c2_data = [(r.lemma, r.relation) for r in c2.all_readings()]
    dist = 0
    for i in range(2):
        if set(x[i] for x in c1_data).isdisjoint(set(x[i] for x in c2_data)):
            dist += 1
    return dist

def best_alignment(s1, s2):
    pos_list = set(s1.by_upos.keys()) & set(s2.by_upos.keys())
    print(s1.by_upos)
    print(s2.by_upos)
    print(pos_list)
    possible = collections.defaultdict(dict)
    for u in pos_list:
        for i1 in s1.by_upos[u]:
            for i2 in s2.by_upos[u]:
                possible[i1][i2] = cohort_distance(s1.words[i1], s2.words[i2])
    print(possible)

    @functools.cache
    def count_descendants1(i):
        return 1 + sum(count_descendants1(j) for j in s1.children(i))
    @functools.cache
    def count_descendants2(i):
        return 1 + sum(count_descendants2(j) for j in s2.children(i))

    cache = collections.defaultdict(list)
    debug = False
    BEAM = 30
    UNALIGNED_PENALTY = 3
    def check_subtree(i1, i2, flip):
        nonlocal cache
        if (i1, i2, flip) not in cache:
            cache[(i1, i2, flip)] = sorted(
                check_subtree_new(i1, i2, flip),
                key=lambda x: x[1])[:BEAM] or [({}, 0)]
        return cache[(i1, i2, flip)]
    def check_subtree_new(i1, i2, flip):
        nonlocal debug
        if i1 == 1 and False:
            debug = True
        if debug:
            print(f'check_subtree_new({i1=}, {i2=})')
        if i2 in possible[i1]:
            w = possible[i1][i2]
            w += UNALIGNED_PENALTY * (count_descendants1(i1) - 1)
            w += UNALIGNED_PENALTY * (count_descendants2(i2) - 1)
            yield {i1: i2}, w
            c1 = []
            conj1 = []
            for i in s1.children(i1):
                if s1.words[i].relation in ['@conj', '@parataxis']:
                    conj1.append(i)
                else:
                    c1.append(i)
            c2 = []
            conj2 = []
            for i in s2.children(i2):
                if s2.words[i].relation in ['@conj', '@parataxis']:
                    conj2.append(i)
                else:
                    c2.append(i)
            if len(conj1) != len(conj2):
                c1 += conj1
                conj1 = []
                c2 += conj2
                conj2 = []
            c2 += [None]*len(c1)
            done = set()
            for cs in itertools.permutations(c2, len(c1)):
                if debug:
                    print(f'{c1=}, {cs=}')
                if cs in done:
                    continue
                for ds in itertools.product(*[
                        check_subtree(j1, j2, False)
                        for j1, j2 in zip(c1 + conj1, cs + tuple(conj2))]):
                    if debug:
                        print(f'{ds=}')
                    d = {i1: i2}
                    w = possible[i1][i2]
                    for d2, w2 in ds:
                        d.update(d2)
                        w += w2
                    for n in c1:
                        if n not in d.keys():
                            w += UNALIGNED_PENALTY * count_descendants1(n)
                    for n in c2:
                        if n is not None and n not in d.values():
                            w += UNALIGNED_PENALTY * count_descendants2(n)
                    if debug:
                        print(f'\tyield {d=}, {w=}')
                    if len(d) > 1:
                        yield d, w
                done.add(cs)
        if i1 == 1:
            debug = False
    min_w = float('inf')
    min_d = {}
    for d, w in check_subtree(s1.root, s2.root, False):
        #w += (len(s1.words) - len(d)) * 4
        #w += (len(s2.words) - len(d)) * 4
        #if 1 in d:
        #    print(f'\t{w=}, {d=}')
        #print(d, w)
        if w < min_w:
            #print(f'{w=}, {d=}')
            min_w = w
            min_d = d
    for i1, i2 in sorted(min_d.items()):
        print(i1, i2, s1.words[i1].source.lemma, s2.words[i2].source.lemma)
    #print(cache)

if __name__ == '__main__':
    import sys
    with open(sys.argv[1]) as f1, open(sys.argv[2]) as f2:
        for i, (s1, s2) in enumerate(zip(read_stream(f1), read_stream(f2))):
            #print(s1)
            #print(s2)
            print(best_alignment(s1, s2))
            if i == 3:
                break
