#!/usr/bin/env python3

from stream import Cohort
from rules import Context, Rule
from learner import Learner

from collections import Counter
from dataclasses import replace

class ParserLearner(Learner):
    def initial_rules(self, current, target):
        for wid, idx in current.id2idx.items():
            if (tidx := target.id2idx.get(wid)) is None:
                continue
            cur = current.words[idx]
            tgt = target.words[tidx]
            if not cur.target_tags or not tgt.target_tags:
                continue
            ts = Cohort(target_tags=[cur.target_tags[0]])
            if (cur.pos == cur.head or cur.head == -1) and tgt.pos != tgt.head:
                r = Rule('SETPARENT SAFE', target=ts)
                if cur.relation != tgt.relation:
                    if not cur.relation:
                        r.rule = 'MAP-SETPARENT'
                        r.params = '@'+tgt.relation
                    else:
                        r.rule = 'SUBSTITUTE-SETPARENT'
                        r.params = ['@'+cur.relation, '@'+tgt.relation]
                if tgt.head == 0:
                    r.ctx_target=Context('@0')
                else:
                    parent = target.words[tgt.head-1]
                    if parent.target_tags:
                        loc = '-1**' if tgt.head < tgt.pos else '1**'
                        pat = Cohort(target_tags=[parent.target_tags[0]])
                        r.ctx_target = Context(loc, pat)
                yield r
            elif cur.relation != tgt.relation:
                if not cur.relation:
                    yield Rule(rule='MAP', params='@'+tgt.relation, target=ts)
                else:
                    yield Rule(rule='SUBSTITUTE',
                               params=['@'+cur.relation, '@'+tgt.relation],
                               target=ts)

    def gather_contexts(self, word, pos, count, contexts):
        for c in word.possible_contexts_single():
            ct = Context(pos, c)
            k = ct.in_rule
            contexts[k] = ct
            count[k] += 1

    def gather_positions(self, corpus, contexts, ids):
        main = Counter()
        ctx = Counter()
        for src, src_idx, tgt, tgt_idx in self.get_words(corpus, ids):
            #for i in range(-2, 3):
            #    if src_idx + i in range(len(corpus)):
            #        self.gather_contexts(src.words[src_idx+i], str(i), main, contexts)
            for s in src.siblings(src_idx):
                self.gather_contexts(s, 's', main, contexts)
            for c in src.children(src_idx):
                self.gather_contexts(c, 'c', main, contexts)
            if (p := src.parent(src_idx)) is not None:
                self.gather_contexts(p, 'p', main, contexts)
            # TODO: how to we figure out the contextual target?
        return main, ctx

    def modify_rule(self, corpus, rule):
        ctx = {}
        pos, cpos = self.gather_positions(corpus, ctx, rule.positive)
        neg, cneg = self.gather_positions(corpus, ctx, rule.negative)
        for k, c in ctx.items():
            if pos[k] - neg[k] > 2:
                yield rule.add_test(c)
            elif neg[k] - pos[k] > 2:
                yield rule.add_test(replace(c, position='NEGATE '+c.position))

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
