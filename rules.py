from stream import Cohort, Sentence, read_stream

from collections import defaultdict
from dataclasses import dataclass, field, replace
import subprocess
import tempfile
import textwrap
from typing import Optional

@dataclass
class Context:
    position: str = ''
    cohort: Cohort = field(default_factory=Cohort)

    @property
    def in_rule(self):
        return f'({self.position} {self.cohort.as_pattern})'

    def make_rule(self, target: Cohort, fout, num):
        ir = self.in_rule.replace('NEGATE', '')
        fout.write(f'ADDRELATION (ctx{num}) {target.as_pattern} TO {ir} ;\n')

def apply_grammar(grammar: str, infile: str, outfile: str, trace: bool = True) -> None:
    tr = ['--trace'] if trace else []
    subprocess.run(
        ['vislcg3', '-g', grammar, '-I', infile, '-O', outfile, '--dep-delimit', '--print-ids'] + tr,
        capture_output=True,
    )

@dataclass
class Rule:
    rule: str = ''
    params: str = ''
    target: Cohort = field(default_factory=Cohort)
    context: list[Context] = field(default_factory=list)
    ctx_target: Optional[Context] = None
    ctx_context: list[Context] = field(default_factory=list)
    positive: set[int] = field(default_factory=set)
    negative: set[int] = field(default_factory=set)
    score: int = 0
    relevant: set[int] = field(default_factory=set)
    affected: set[int] = field(default_factory=set)

    def context_str(self, ctx, add_if):
        ret = ' '.join(c.in_rule for c in ctx)
        if ret:
            ret = ' ' + ret
            if add_if:
                ret = ' IF' + ret
        return ret

    def as_str(self):
        if self.rule == 'REMCOHORT':
            return f'REMCOHORT {self.target.as_pattern}{self.context_str(self.context, True)} ;'
        elif self.rule == 'MAP':
            return f'MAP ({self.params}) {self.target.as_pattern}{self.context_str(self.context, True)} ;'
        elif self.rule == 'SUBSTITUTE':
            return f'SUBSTITUTE ({self.params[0]}) ({self.params[1]}) {self.target.as_pattern}{self.context_str(self.context, True)} ;'
        elif self.rule in ['SETPARENT', 'SETPARENT SAFE']:
            return f'{self.rule} {self.target.as_pattern} TO {self.ctx_target.in_rule}{self.context_str(self.ctx_context, False)}{self.context_str(self.context, True)} ;'
        elif self.rule == 'MAP-SETPARENT':
            ctx = [replace(self.ctx_target, position=self.ctx_target.position+'X')]
            ctx += self.context
            ctx += [replace(c, position=c.position+'x') for c in self.ctx_context]
            return textwrap.dedent(f'''\
            WITH REMEMBERX KEEPORDER {self.target.as_pattern}
                IF (NOT p (*)) {self.context_str(ctx, False)} {{
              MAP ({self.params}) (*) ;
              SETPARENT (*) TO (jC1 (*)) ;
            }};''')
        elif self.rule == 'SUBSTITUTE-SETPARENT':
            ctx = [replace(self.ctx_target, position=self.ctx_target.position+'X')]
            ctx += self.context
            ctx += [replace(c, position=c.position+'x') for c in self.ctx_context]
            return textwrap.dedent(f'''\
            WITH REMEMBERX KEEPORDER {self.target.as_pattern}
                IF (NOT p (*)) {self.context_str(ctx, False)} {{
              SUBSTITUTE ({self.params[0]}) ({self.params[1]}) (*) ;
              SETPARENT (*) TO (jC1 (*)) ;
            }};''')
        return f'; # {self.rule=}'

    def independent(self, other):
        return (self.relevant.isdisjoint(other.affected) and
                self.affected.isdisjoint(other.relevant) and
                self.affected.isdisjoint(other.affected))

    def all_context(self):
        yield from self.context
        if self.ctx_target:
            yield self.ctx_target
        yield from self.ctx_context

    def run(self, infile: str, outfile: str):
        with tempfile.NamedTemporaryFile('w+') as grammar:
            for i, ctx in enumerate(self.all_context(), 1):
                ctx.make_rule(self.target, grammar, i)
            grammar.write(self.as_str())
            grammar.flush()
            apply_grammar(grammar.name, infile, outfile)

    def add_test(self, test: Context):
        for i, c in enumerate(self.context):
            if c.position != test.position:
                continue
            if c.cohort.match(test.cohort):
                return self
            if test.cohort.match(c.cohort):
                ctx = self.context[:i] + [test] + self.context[i+1:]
                return replace(self, context=ctx)
        return replace(self, context=self.context + [test])

@dataclass
class Corpus:
    source: list[Sentence] = field(default_factory=list)
    target: list[Sentence] = field(default_factory=list)
    scores: list[int] = field(default_factory=list)
    id2sent: dict[int, int] = field(default_factory=dict)

    def __len__(self):
        return min(len(self.source), len(self.target))

    def test_rule(self, rule: Rule, infile: str, outfile: str, score_example):
        rule.run(infile, outfile)
        rule.score = 0
        rule.negative = []
        with open(outfile) as fin:
            for i, out in enumerate(read_stream(fin)):
                old = self.scores[i]
                new = score_example(out, self.target[i])
                if new > old:
                    rule.negative.update(out.affected)
                else:
                    rule.positive.update(out.affected)
                rule.score += (new - old)
                rule.relevant.update(out.relevant)
                rule.affected.update(out.affected)

    @staticmethod
    def load(src_fname: str, tgt_fname: str, score_example) -> 'Corpus':
        with open(src_fname) as fsrc, open(tgt_fname) as ftgt:
            c = Corpus(list(read_stream(fsrc)), list(read_stream(ftgt)))
            c.scores = [score_example(s, t) for s, t in zip(c.source, c.target)]
            for i in range(len(c)):
                for j in c.target[i].id2idx.keys():
                    c.id2sent[j] = i
            return c
