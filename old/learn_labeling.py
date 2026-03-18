#!/usr/bin/env python3

from stream import Cohort
from rules import Context, Rule
from learner import Learner

from collections import Counter, defaultdict
from dataclasses import replace

class LabelLearner(Learner):
    mapping_prefix = '%'

    def baseline_rules(self, corpus, fout):
        count = defaultdict(Counter)
        for src, tgt in zip(corpus.source, corpus.target):
            for sw, tw in src.paired_words(tgt):
                if tw and tw.label and sw.target_tags:
                    count[sw.lemma_and_pos][tw.label] += 1
        top = defaultdict(list)
        for key in count:
            mx = count[key].most_common()[0][0]
            top[mx].append(key)
        for k, ws in sorted(top.items()):
            ls = ' '.join(f'("{x[0]}" tgt:{x[1]})' for x in sorted(ws))
            fout.write(f'LIST map-{k} = {ls} ;\n')
            fout.write(f'MAP (%{k}) map-{k} ;\n')

    def initial_rules(self, current, target):
        for sw, tw in current.paired_words(target):
            if tw is None:
                continue
            if sw.label == tw.label:
                continue
            if not sw.label:
                yield Rule(rule='MAP', params='%'+tw.label,
                           target=tw.pos_context())
                yield Rule(rule='MAP', params='%'+tw.label,
                           target=tw.lemma_pos_context())
            else:
                tl = '%'+tw.label if tw.label else '*'
                yield Rule(rule='SUBSTITUTE', target=tw.lemma_pos_context(),
                           params=['%'+sw.label, tl])

    @staticmethod
    def score_example(src, tgt):
        score = 0
        pos = []
        neg = []
        for sw, tw in src.paired_words(tgt):
            if tw is None:
                score += 1
                continue
            score += int(sw.label != tw.label)
            if sw.target:
                if sw.label == tw.label:
                    pos.append(sw.id)
                else:
                    neg.append(sw.id)
        return score, pos, neg
            
    def gather_contexts(self, word, pos, count, contexts):
        for c in word.possible_contexts_single():
            ct = Context(pos, c)
            k = ct.in_rule
            contexts[k] = ct
            count[k] += 1

    def gather_positions(self, corpus, contexts, ids):
        ct = Counter()
        for src, src_idx, tgt, tgt_idx in self.get_words(corpus, ids):
            for s in src.siblings(src_idx):
                self.gather_contexts(s, 's', ct, contexts)
            for c in src.children(src_idx):
                self.gather_contexts(c, 'c', ct, contexts)
            if (p := src.parent(src_idx)) is not None:
                self.gather_contexts(p, 'p', ct, contexts)
        return ct

    def modify_rule(self, corpus, rule):
        if not rule.negative:
            return
        ctx = {}
        pos = self.gather_positions(corpus, ctx, rule.positive)
        neg = self.gather_positions(corpus, ctx, rule.negative)
        for k, c in ctx.items():
            print(f'\t\tmodify: {k=}, {pos[k]=}, {neg[k]=}')
            if pos[k] - neg[k] > 2:
                yield rule.add_test(c)
            elif neg[k] - pos[k] > 2:
                yield rule.add_test(replace(c, position='NEGATE '+c.position))

if __name__ == '__main__':
    LabelLearner().main()
    
