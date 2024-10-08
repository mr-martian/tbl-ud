from stream import Sentence
from rules import Corpus, Rule, apply_grammar, run_rule

import argparse
import concurrent.futures
import os
import tempfile

class Learner:
    def __init__(self):
        self.infile = None
        self.outfile = None
        self.grammar = None

    @staticmethod
    def generate_rules(src: Sentence, tgt: Sentence, sentence_index: int):
        yield from []

    @staticmethod
    def generate_negative_rules(rule: Rule, src: Sentence, tgt: Sentence):
        yield from []

    @staticmethod
    def score_example(pred: Sentence, tgt: Sentence) -> int:
        return 0

    def positive_rules(self, corpus):
        for i in range(len(corpus)):
            if corpus.scores[i] == 0:
                continue
            yield from self.generate_rules(corpus.source[i], corpus.target[i], i)

    def negative_rules(self, keys, corpus):
        for k in keys:
            r = corpus.rules[k]
            for i in r.negative:
                yield from self.generate_negative_rules(r, corpus.source[i],
                                                        corpus.target[i])

    def add_rules(self, corpus, rule_gen):
        rule_count = 0
        with (tempfile.TemporaryDirectory() as tmpdir,
              concurrent.futures.ThreadPoolExecutor() as executor):
            future_to_rule = {}
            for r in rule_gen:
                rule_count += 1
                fout = os.path.join(tmpdir, f'out.{rule_count}.txt')
                future = executor.submit(run_rule, r, self.infile, fout)
                future_to_rule[future] = (r, fout)
            for future in concurrent.futures.as_completed(future_to_rule):
                r, fout = future_to_rule[future]
                corpus.add_rule(r, fout, self.score_example)

    def next_rule(self):
        corpus = Corpus.load(self.infile, self.outfile, self.score_example)
        self.add_rules(corpus, self.positive_rules(corpus))
        keys = list(corpus.rules.keys())
        self.add_rules(corpus, self.negative_rules(keys, corpus))
        if not corpus.rules:
            print('  No further rules generated')
            return []
        ret = []
        for score in sorted(corpus.by_score.keys()):
            if score >= 0:
                break
            for key in corpus.by_score[score]:
                rule = corpus.rules[key]
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
            apply_grammar(self.grammar, args.source, self.infile, trace=False)
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
                    print('adding rule', s, f'{r.affected=}, {r.relevant=}')
                    fout.write('\n' + s + '\n')
            i += 1
            self.infile = os.path.join(args.dir, f'step{i:05}.txt')
            apply_grammar(self.grammar, args.source, self.infile, trace=False)
