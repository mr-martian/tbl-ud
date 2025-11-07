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

@dataclass
class Rule:
    rule_type: str
    target: str # TODO
    target2: str # TODO
    context: str # TODO
    tags: str # TODO
    tags2: str # TODO
    
