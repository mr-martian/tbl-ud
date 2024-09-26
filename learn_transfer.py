#!/usr/bin/env python3

from rules import Context, Rule
from learner import Learner

class TransferLearner(Learner):
    @staticmethod
    def generate_rules(current, target, sentence_index):
        for wid, idx in current.id2idx.items():
            if wid in target.id2idx:
                continue
            target = current.words[idx]
            for target_set in target.possible_contexts():
                if target_set.as_pattern == '(*)':
                    continue
                yield Rule(rule='REMCOHORT', target=target_set, examples=[(sentence_index, idx)])

    @staticmethod
    def generate_negative_rules(rule, src, tgt):
        for i, w in enumerate(src.words):
            if rule.target.match(w):
                for s in src.siblings(i):
                    for pc in s.possible_contexts():
                        yield Rule(rule.rule, rule.params, rule.target, rule.context + [Context('NEGATE s', pc)])

    @staticmethod
    def score_example(src, tgt):
        sw = set(src.id2idx.keys())
        tw = set(tgt.id2idx.keys())
        return len(sw.symmetric_difference(tw))

if __name__ == '__main__':
    TransferLearner().main()
