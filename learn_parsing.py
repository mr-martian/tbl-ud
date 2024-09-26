#!/usr/bin/env python3

from rules import Context, Rule
from learner import Learner

class ParserLearner(Learner):
    @staticmethod
    def generate_rules(current, target, sentence_index):
        for wid, idx in current.id2idx.items():
            if (tidx := target.id2idx.get(wid)) is None:
                continue
            cur = current.words[idx]
            tgt = target.words[tidx]
            if cur.relation != tgt.relation:
                for ts in cur.possible_contexts(include_source=False):
                    if ts.as_pattern == '(*)':
                        continue
                    yield Rule(rule='MAP', params='@'+tgt.relation, target=ts, examples=[(sentence_index, idx)])

    @staticmethod
    def generate_negative_rules(rule, src, tgt):
        for i, w in enumerate(src.words):
            if rule.target.match(w):
                for s in src.siblings(i):
                    for pc in s.possible_contexts():
                        yield Rule(rule.rule, rule.params, rule.target, rule.context + [Context('NEGATE s', pc)])

    @staticmethod
    def score_example(src, tgt):
        score = 0
        for wid, ti in tgt.id2idx.items():
            si = src.id2idx.get(wid)
            if si is None:
                score += 2
                continue
            sw = src.words[si]
            tw = tgt.words[ti]
            score += int(sw.head != tw.head)
            score += int(sw.relation != tw.relation)
        return score

if __name__ == '__main__':
    ParserLearner().main()
