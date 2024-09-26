from stream import Cohort, Sentence, read_stream

from collections import defaultdict
from dataclasses import dataclass, field
import subprocess
import tempfile

@dataclass
class Context:
    position: str = ''
    cohort: Cohort = field(default_factory=Cohort)

    @property
    def in_rule(self):
        return f'({self.position} {self.cohort.as_pattern})'

    def make_rule(self, target: Cohort, fout):
        ir = self.in_rule.replace('NEGATE', '')
        fout.write(f'ADDRELATION (ctx) {target.as_pattern} TO {ir} ;\n')

@dataclass
class Rule:
    rule: str = ''
    params: str = ''
    target: Cohort = field(default_factory=Cohort)
    context: list[Context] = field(default_factory=list)
    examples: list[tuple[int, int]] = field(default_factory=list)
    negative: list[int] = field(default_factory=list)
    score: int = 0
    relevant: set[int] = field(default_factory=set)
    affected: set[int] = field(default_factory=set)

    def as_str(self):
        if self.rule == 'REMCOHORT':
            ret = 'REMCOHORT ' + self.target.as_pattern
            if self.context:
                ret += ' IF ' + ' '.join(c.in_rule for c in self.context)
            ret += ' ;'
            return ret
        elif self.rule == 'MAP':
            ret = f'MAP ({self.params}) {self.target.as_pattern}'
            if self.context:
                ret += ' IF ' + ' '.join(c.in_rule for c in self.context)
            ret += ' ;'
            return ret

    def independent(self, other):
        return (self.relevant.isdisjoint(other.affected) and
                self.affected.isdisjoint(other.relevant) and
                self.affected.isdisjoint(other.affected))

def apply_grammar(grammar: str, infile: str, outfile: str, trace: bool = True) -> None:
    tr = ['--trace'] if trace else []
    subprocess.run(
        ['vislcg3', '-g', grammar, '-I', infile, '-O', outfile, '--dep-delimit', '--print-ids'] + tr,
        capture_output=True,
    )

def run_rule(rule: Rule, infile: str):
    with tempfile.NamedTemporaryFile('w+') as grammar:
        for ctx in rule.context:
            ctx.make_rule(rule.target, grammar)
        grammar.write(rule.as_str())
        grammar.flush()
        with tempfile.NamedTemporaryFile('w+') as outfile:
            apply_grammar(grammar.name, infile, outfile.name)
            yield from read_stream(outfile)

@dataclass
class Corpus:
    source: list[Sentence] = field(default_factory=list)
    target: list[Sentence] = field(default_factory=list)
    scores: list[int] = field(default_factory=list)
    rules: dict[str, Rule] = field(default_factory=dict)
    by_score: defaultdict = field(default_factory=lambda: defaultdict(list))

    def __len__(self):
        return min(len(self.source), len(self.target))

    def add_rule(self, rule: Rule, infile: str, score_example):
        key = rule.as_str()
        if key in self.rules:
            self.rules[key].examples += rule.examples
            return

        rule.score = 0
        rule.negative = []
        for i, out in enumerate(run_rule(rule, infile)):
            old = self.scores[i]
            new = score_example(out, self.target[i])
            if new > old:
                rule.negative.append(i)
            rule.score += (new - old)
            rule.relevant.update(out.relevant)
            rule.affected.update(out.affected)

        self.rules[key] = rule
        self.by_score[rule.score].append(key)
        print('  ', key, rule.score, len(rule.negative))

    @staticmethod
    def load(src_fname: str, tgt_fname: str, score_example) -> 'Corpus':
        with open(src_fname) as fsrc, open(tgt_fname) as ftgt:
            c = Corpus(list(read_stream(fsrc)), list(read_stream(ftgt)))
            c.scores = [score_example(s, t) for s, t in zip(c.source, c.target)]
            return c
