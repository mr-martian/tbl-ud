from dataclasses import dataclass, field
from itertools import combinations, chain

@dataclass
class Cohort:
    source_lemma: str = ''
    source_tags: list[str] = field(default_factory=list)
    target_lemma: str = ''
    target_tags: list[str] = field(default_factory=list)
    relation: str = ''
    pos: int = 0
    head: int = 0
    id: int = 0
    relation_id: int = 0
    target: bool = False
    relevant: bool = False
    context: set[int] = field(default_factory=set)

    def add_line(self, line):
        for piece in line.split():
            if piece[0] == '"' and piece[-1] == '"':
                lm = piece[1:-1]
                if lm[0] == '<' and lm[-1] == '>':
                    self.source_lemma = lm[1:-1]
                else:
                    self.target_lemma = lm
            elif piece.startswith('@'):
                self.relation = piece[1:]
            elif piece.startswith('src:'):
                self.source_tags.append(piece[4:])
            elif piece.startswith('tgt:'):
                self.target_tags.append(piece[4:])
            elif piece[0] == '#':
                a, b = piece[1:].split('->')
                self.pos = int(a)
                self.head = int(b)
            elif piece.startswith('R:ctx:'):
                self.context.add(int(piece[6:]))
            elif piece.startswith('ID:'):
                self.relation_id = int(piece[3:])
            elif piece.startswith('WID:'):
                self.id = int(piece[4:])
            elif ':' in piece and piece.split(':')[0].isupper():
                self.target = True
            else:
                self.target_tags.append(piece)

    @property
    def lemma_and_pos(self):
        if self.target_tags:
            return (self.target_lemma, self.target_tags[0])
        else:
            return (self.target_lemma, '')

    @property
    def as_pattern(self):
        ls = []
        if self.source_lemma:
            ls.append(f'"<{self.source_lemma}>"')
        elif self.target_lemma:
            ls.append(f'"{self.target_lemma}"')
        for t in self.source_tags:
            ls.append(f'src:{t}')
        for t in self.target_tags:
            ls.append(f'tgt:{t}')
        if self.relation:
            ls.append(f'@{self.relation}')
        if not ls:
            ls.append('*')
        return f'({" ".join(ls)})'

    def possible_contexts(self, include_source=True):
        for rel in sorted(set(['', self.relation]), reverse=True):
            ops = [0, 1, 2] if rel else [1, 2]
            tag_ops = (combinations(self.target_tags, i) for i in ops)
            for tags in chain.from_iterable(tag_ops):
                yield Cohort(relation=rel, target_tags=tags)
                if self.source_lemma and include_source:
                    yield Cohort(relation=rel, target_tags=tags,
                                 source_lemma=self.source_lemma)
                if self.target_lemma:
                    yield Cohort(relation=rel, target_tags=tags,
                                 target_lemma=self.target_lemma)

    def match(self, other):
        return (self.source_lemma in ['', other.source_lemma] and
                set(self.source_tags) <= set(other.source_tags) and
                self.target_lemma in ['', other.target_lemma] and
                set(self.target_tags) <= set(other.target_tags) and
                self.relation in ['', other.relation])

@dataclass
class Sentence:
    words: list[Cohort] = field(default_factory=list)
    has_target: bool = False
    context: set[int] = field(default_factory=set)
    id2idx: dict[int, int] = field(default_factory=dict)
    relation_id2idx: dict[int, int] = field(default_factory=dict)

    def add_word(self, word):
        if word.target:
            self.has_target = True
        if word.id:
            self.id2idx[word.id] = len(self.words)
        if word.relation_id:
            if word.relation_id in self.context:
                word.relevant = True
        for i in word.context:
            if i in self.relation_id2idx:
                self.words[self.relation_id2idx[i]].relevant = True
            self.context.add(i)
        self.words.append(word)

    def __len__(self):
        return len(self.words)

    def __bool__(self):
        return bool(self.words)

    def get_word_set(self):
        ret = defaultdict(list)
        for i, w in enumerate(self.words):
            ret[w.lemma_and_pos].append(i)
        return ret

    def parent(self, word_idx: int):
        for c in self.words:
            if c.pos == self.words[word_idx].head:
                return c

    def children(self, word_idx: int):
        for c in self.words:
            if c.head == self.words[word_idx].pos:
                yield c

    def siblings(self, word_idx: int):
        for c in self.words:
            if c.head == self.words[word_idx].head:
                yield c

    @property
    def relevant(self):
        return set(w.id for w in self.words if w.relevant)

    @property
    def affected(self):
        return set(w.id for w in self.words if w.target)

def read_stream(fin):
    cur_sent = Sentence()
    cur_word = Cohort()
    blank = True
    for line in fin:
        if not line.strip():
            continue
        if line[0] == '"':
            if not blank:
                if cur_word.pos == 1:
                    if cur_sent:
                        yield cur_sent
                    cur_sent = Sentence()
                cur_sent.add_word(cur_word)
                cur_word = Cohort()
                blank = True
            cur_word.add_line(line)
            blank = False
        elif line[0] == '\t':
            cur_word.add_line(line)
            blank = False
    if not blank:
        cur_sent.add_word(cur_word)
    if cur_sent:
        yield cur_sent
