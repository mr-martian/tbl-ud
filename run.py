#!/usr/bin/env python3.9

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional
from itertools import combinations, chain, product
import subprocess
import tempfile

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
    target: bool = False
    relevant: bool = False
    context: list[int] = field(default_factory=list)

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
                self.context.append(int(piece[6:]))
            elif piece.startswith('ID:'):
                self.id = int(piece[3:])
            elif ':' in piece and piece.split(':')[0].isupper():
                self.target = True

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

    def possible_contexts(self):
        def combo(ls):
            return chain.from_iterable(combinations(ls, i) for i in range(3))
        components = [
            ('source_lemma', sorted(set(['', self.source_lemma]))),
            #('source_tags', combo(self.source_tags)),
            # static tags don't exist for rule targets, so this is
            # a bit more complicated - skip for now
            ('target_lemma', sorted(set(['', self.target_lemma]))),
            ('target_tags', combo(self.target_tags)),
            ('relation', sorted(set(['', self.relation]))),
        ]
        keys = [x[0] for x in components]
        values = [x[1] for x in components]
        for op in product(*values):
            yield Cohort(**dict(zip(keys, op)))

@dataclass
class Sentence:
    words: list[Cohort] = field(default_factory=list)
    has_target: bool = False
    context: set[int] = field(default_factory=set)
    id2idx: dict[int, int] = field(default_factory=dict)

    def add_word(self, word):
        if word.target:
            self.has_target = True
        if word.id:
            self.id2idx[word.id] = len(self.words)
            if word.id in self.context:
                word.relevant = True
        for i in word.context:
            if i in self.id2idx:
                self.words[self.id2idx[i]].relevant = True
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

@dataclass
class Context:
    position: str = ''
    cohort: Cohort = field(default_factory=Cohort)

    @property
    def in_rule(self):
        return f'({self.position} {self.cohort.as_pattern})'

    def make_rule(self, target: Cohort, fout):
        fout.write(f'ADDRELATION (ctx) {target.as_pattern} TO {self.in_rule} ;\n')

@dataclass
class Rule:
    rule: str = ''
    params: str = ''
    target: Cohort = field(default_factory=Cohort)
    context: list[Context] = field(default_factory=list)

    def as_str(self):
        if self.rule == 'REMCOHORT':
            ret = 'REMCOHORT ' + self.target.as_pattern
            if self.context:
                ret += ' IF ' + ' '.join(c.in_rule for c in self.context)
            ret += ' ;'
            return ret

possible_rules = [('REMCOHORT', '')]
possible_positions = ['p']
max_context = 3

def all_positions():
    for i in range(1, max_context+1):
        yield from combinations(possible_positions, i)

def generate_deletion_rules(sentence, idx):
    target = sentence.words[idx]
    for target_set in target.possible_contexts():
        if target_set.as_pattern == '(*)':
            continue
        yield Rule(rule='REMCOHORT', target=target_set)

def generate_rules(current, target):
    cdict = current.get_word_set()
    tdict = target.get_word_set()
    deletable = []
    for word in cdict:
        if word not in tdict or len(cdict[word]) > len(tdict[word]):
            for d in cdict[word]:
                yield from generate_deletion_rules(current, d)

def apply_grammar(grammar: str, infile: str, outfile: str) -> None:
    subprocess.run(
        ['vislcg3', '-g', grammar, '-I', infile, '-O', outfile, '--dep-delimit'],
        capture_output=True,
    )

def run_rule(rule, infile):
    with tempfile.NamedTemporaryFile('w+') as grammar:
        for ctx in rule.context:
            ctx.make_rule(rule.target, grammar)
        grammar.write(rule.as_str())
        grammar.flush()
        with tempfile.NamedTemporaryFile('w+') as outfile:
            apply_grammar(grammar.name, infile, outfile.name)
            yield from read_stream(outfile)

def load_corpus(src_fname, tgt_fname):
    with open(src_fname) as fsrc, open(tgt_fname) as ftgt:
        return list(zip(read_stream(fsrc), read_stream(ftgt)))

def score_example(pred, tgt):
    pw = pred.get_word_set()
    tw = tgt.get_word_set()
    score = 0
    for k in tw:
        if k not in pw:
            score += len(tw[k])
        else:
            score += abs(len(tw[k]) - len(pw[k]))
    for k in pw:
        if k not in tw:
            score += len(pw[k])
    return score

def score_rule(rule, infile, corpus):
    score = 0
    misfires = []
    for (src, tgt), out in zip(corpus, run_rule(rule, infile)):
        old = score_example(src, tgt)
        new = score_example(out, tgt)
        if new > old:
            misfires.append((src, tgt, out))
        score += (new - old)
    return score, misfires

def main(infile, outfile):
    corpus = load_corpus(infile, outfile)
    rules = {}
    by_score = defaultdict(list)
    for src, tgt in corpus:
        for r in generate_rules(src, tgt):
            k = r.as_str()
            if k in rules:
                continue
            score, miss = score_rule(r, infile, corpus)
            rules[k] = (r, score, miss)
            by_score[score].append(k)
            # TODO: negative contexts
            print('  ', k, score, len(miss))
    best = min(by_score.keys())
    if best >= 0:
        return None
    return rules[by_score[best][0]][0]

# - for each cohort that needs to be changed
#   - check misfires to see if we can generate negative contexts
#   - cache rules so we don't rerun rules that get the same string
# - add top rule
# - for top N rules
#   - check if independent from added rules
#   - add if so

if __name__ == '__main__':
    import sys
    infile = sys.argv[1]
    target = sys.argv[2]
    grammar = sys.argv[3]
    n = 0
    while True:
        rule = main(infile, target)
        if rule is None:
            break
        with open(grammar, 'a') as fout:
            print('adding rule', rule.as_str())
            fout.write(rule.as_str() + '\n')
        apply_grammar(grammar, infile, f'output/{n}.txt')
        infile = f'output/{n}.txt'
        n += 1
