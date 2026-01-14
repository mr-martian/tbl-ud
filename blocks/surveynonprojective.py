import collections
import json
import logging

from udapi.core.block import Block

class SurveyNonprojective(Block):
    def process_start(self):
        self.nonproj_types = collections.Counter()
        self.total_words = 0

    def log(self, node, nptype):
        self.nonproj_types[nptype] += 1
        if nptype == 'unknown':
            node.misc['Mark'] = nptype

    def is_first_child(self, node):
        for ch in node.parent.descendants:
            if ch.upos == 'PUNCT':
                continue
            if ch == node:
                return True
            return False

    def is_first_but_conj(self, node):
        for ch in node.parent.descendants:
            if ch.upos in ['PUNCT', 'SCONJ', 'CCONJ']:
                continue
            if ch == node:
                return True
            return False

    def process_node(self, node):
        self.total_words += 1
        if not node.is_nonprojective():
            return
        if all(node.precedes(n) or n.is_descendant_of(node)
               or n == node or n.upos == 'PUNCT'
               for n in node.parent.parent.unordered_descendants()):
            self.log(node, 'fronting')
            return
        if all(n.precedes(node) or n.is_descendant_of(node)
               or n == node or n.upos == 'PUNCT'
               for n in node.parent.parent.unordered_descendants()):
            self.log(node, 'backing')
            return
        if (node.parent.next_node and
            node.parent.next_node.parent == node.parent.parent and
            self.is_first_child(node.parent) and
            node.parent.precedes(node)):
            self.log(node, 'V2')
            return
        if (node.parent.next_node and
            node.parent.next_node.parent == node.parent.parent and
            self.is_first_but_conj(node.parent) and
            node.parent.precedes(node)):
            self.log(node, 'V2-but-conj')
            return
        self.log(node, 'unknown')

    def process_end(self):
        msg = []
        total = self.nonproj_types.total()
        for typ, count in self.nonproj_types.most_common():
            msg.append('%20s %10d %10.2f%%' % (typ, count, 100.0*count/total))
        msg.append('%20s %10d %10.2f%%' % ('TOTAL', total, 100))
        logging.warning('\n' + '\n'.join(msg) + '\n')
        print(json.dumps({'total': self.total_words,
                          'nonproj': self.nonproj_types}))
