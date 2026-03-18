from stream import Sentence
from rules import Corpus, Rule, apply_grammar

import argparse
import concurrent.futures
from collections import defaultdict
import os
import tempfile

MAX_RULES = 1000
MIN_BENEFIT = 2

class Learner:
    mapping_prefix = '@'

    def __init__(self):
        self.infile = None
        self.outfile = None
        self.grammar = None

    def initial_rules(self, src: Sentence, tgt: Sentence):
        yield from []

    def modify_rule(self, corpus: Corpus, rule: Rule):
        yield from []

    @staticmethod
    def score_example(pred: Sentence, tgt: Sentence) -> int:
        return 0

    def get_words(self, corpus: Corpus, ids: set[int]):
        for i in sorted(ids):
            si = corpus.id2sent[i]
            s = corpus.source[si]
            t = corpus.target[si]
            sw = s.id2idx[i]
            tw = t.id2idx[i]
            yield s, sw, t, tw

    def generate_initial_rules(self, corpus):
        for i in range(len(corpus)):
            if corpus.scores[i] <= 0:
                continue
            yield from self.initial_rules(corpus.source[i], corpus.target[i])

    def generate_modified_rules(self, corpus, rule_names):
        for k in rule_names:
            r = self.rules[k]
            if len(r.positive) < MIN_BENEFIT:
                continue
            yield from self.modify_rule(corpus, r)

    def process_iterator(self, corpus, tmpdir, executor, iterator):
        future_to_rule = {}
        rule_count = len(self.rules)
        new = []
        for r in iterator:
            k = r.as_str()
            if k in self.seen:
                continue
            self.seen.add(k)
            rule_count += 1
            added = True
            fout = os.path.join(tmpdir, f'out.{rule_count:05}.txt')
            future = executor.submit(corpus.test_rule, r, self.infile, fout,
                                     self.score_example, self.mapping_prefix)
            future_to_rule[future] = r
            new.append(k)
            if rule_count > MAX_RULES:
                break
        for future in concurrent.futures.as_completed(future_to_rule):
            r = future_to_rule[future]
            k = r.as_str()
            self.rules[k] = r
            self.by_score[r.score].append(k)
            print(f'    tried {k.replace("\n", " ")} {r.score=}, {len(r.positive)=}, {len(r.negative)=}')
        # TODO: beam search based on len(pos) and/or len(neg)?
        return new

    def add_rules(self, corpus):
        self.rules = {}
        self.by_score = defaultdict(list)
        self.seen = set()
        with (tempfile.TemporaryDirectory() as tmpdir,
              concurrent.futures.ThreadPoolExecutor() as executor):
            new = self.process_iterator(corpus, tmpdir, executor,
                                        self.generate_initial_rules(corpus))
            while new:
                new = self.process_iterator(
                    corpus, tmpdir, executor,
                    self.generate_modified_rules(corpus, new),
                )

                if len(self.seen) > MAX_RULES:
                    break

    def next_rule(self):
        corpus = Corpus.load(self.infile, self.outfile, self.score_example)
        self.add_rules(corpus)
        keys = list(self.rules.keys())
        if not self.rules:
            print('  No further rules generated')
            return []
        ret = []
        for score in sorted(self.by_score.keys()):
            if score >= 0:
                break
            for key in self.by_score[score]:
                rule = self.rules[key]
                if all(r.independent(rule) for r in ret):
                    ret.append(rule)
        if not ret:
            print('  No rules provide a net benefit')
        return ret

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('source')
        parser.add_argument('target')
        parser.add_argument('grammar')
        parser.add_argument('--dir', '-d', action='store', default='steps')
        args = parser.parse_args()
        self.outfile, self.grammar = args.target, args.grammar

        os.makedirs(args.dir, exist_ok=True)

        i = 0
        self.infile = os.path.join(args.dir, f'step00000.txt')
        if os.path.isfile(self.grammar):
            apply_grammar(self.grammar, args.source, self.infile, trace=False, prefix=self.mapping_prefix)
        elif hasattr(self, 'baseline_rules'):
            corpus = Corpus.load(args.source, self.outfile, self.score_example)
            with open(self.grammar, 'w') as fout:
                self.baseline_rules(corpus, fout)
            apply_grammar(self.grammar, args.source, self.infile, trace=False, prefix=self.mapping_prefix)
        else:
            with open(args.source) as fin, open(self.infile, 'w') as fout:
                fout.write(fin.read())
        while True:
            rules = self.next_rule()
            if not rules:
                break
            with open(self.grammar, 'a') as fout:
                for r in rules:
                    s = r.as_str()
                    print('adding rule', s.replace('\n', ' '), f'{r.score=}, {len(r.positive)=}, {len(r.negative)=}')
                    fout.write('\n' + s + '\n')
            i += 1
            self.infile = os.path.join(args.dir, f'step{i:05}.txt')
            apply_grammar(self.grammar, args.source, self.infile, trace=False, prefix=self.mapping_prefix)
