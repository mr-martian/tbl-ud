#!/usr/bin/env python3

from rules import Context, Rule
from learner import Learner

from collections import defaultdict
import itertools

def group_nodes(t, i):
    d = defaultdict(list)
    if i == -1:
        for c in t.roots():
            d[c.relation].append(c)
    else:
        for c in t.children(i):
            d[c.relation].append(c)
    return d

def align_layer(t1, t2, n1, n2):
    ch1 = group_nodes(t1, n1)
    ch2 = group_nodes(t2, n2)
    dct = {}
    score = 0
    for rel in ch1:
        if rel not in ch2:
            # TODO: more symmetric errors?
            for c in ch1[rel]:
                score += 1
                score += len(t1.descendants(c.pos))
            continue
        dct2 = {}
        s2 = 1000000000000000
        for i in range(max(len(ch1[rel]) - len(ch2[rel]), 1)):
            for pm in itertools.permutations(ch2[rel]):
                dct3 = {}
                s3 = 0
                for c1, c2 in zip(ch1[rel][i:], pm):
                    dct4, s4 = align_layer(t1, t2, t1.id2idx[c1.id],
                                           t2.id2idx[c2.id])
                    dct3.update(dct4)
                    s3 += s4
                if s3 < s2:
                    dct2 = dct3
                    s2 = s3
        dct.update(dct2)
        score += s2
    return dct, score

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
