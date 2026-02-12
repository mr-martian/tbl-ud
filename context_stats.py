from tree_sitter import Language, Parser
import tree_sitter_cg
import argparse
from collections import Counter, defaultdict
import re

parser = argparse.ArgumentParser()
parser.add_argument('mode', type=int, choices=[12, 13])
parser.add_argument('grammar')
args = parser.parse_args()

def identify_rule(node, data):
    if args.mode == 12:
        w1 = data[node.start_byte:].split()[0]
        if w1 == b'REMOVE':
            return 'remove'
        elif w1 == b'APPEND':
            return 'append'
        elif w1 == b'ADDCOHORT':
            return 'addcohort'
        elif w1 == b'REMCOHORT':
            return 'rem-self'
        elif w1 == b'WITH':
            return 'rem-parent'
        elif w1 == b'SUBSTITUTE':
            return 'substitute'
        return 'some_rule'
    else:
        if node.type == 'rule_with':
            rng = data[node.start_byte:node.end_byte]
            if b'SELECT' in rng:
                return 'replace'
            elif b'REMCOHORT' in rng:
                return 'func2feat'
            elif b'ADDCOHORT' in rng:
                return 'feat2func'
            elif b'VSTR:$1' in rng:
                return 'agreement'
            else:
                return 'feat-from-func'
        elif node.type == 'rule_substitute_etc':
            return 'add-feat'
        elif node.type == 'rule_addcohort':
            return 'addcohort'
        elif data[node.start_byte:].startswith(b'REMOVE'):
            return 'remove'
        else:
            return 'remcohort'

upos_re = re.compile(r'\b(ADJ|ADP|ADV|AUX|CCONJ|DET|INTJ|NOUN|NUM|PART|PRON|PROPN|PUNCT|SCONJ|SYM|VERB|X|UNK)\b')
def identify_test(node, rtype, data):
    s = data[node.start_byte:node.end_byte]
    for op in [b'-', b'+', b'LINK']:
        if args.mode == 12 and op == b'LINK':
            continue
        s = s.split(op)[0]
    if s.startswith(b'NEGATE') or s == b'(*)':
        return 'structural'
    ret = []
    if b'"' in s:
        ret.append('lem')
    if b'@' in s:
        ret.append('rel')
    if upos_re.search(s.decode('utf-8')):
        ret.append('upos')
    if b'=' in s:
        ret.append('feat')
    return '-'.join(ret) or 'other'

p = Parser(Language(tree_sitter_cg.language()))
with open(args.grammar, 'rb') as fin:
    data = fin.read()
    tree = p.parse(data).root_node
    ct = Counter()
    by_type = defaultdict(Counter)
    has_lem = 0
    no_lem = 0
    for node in tree.children:
        if not node.type.startswith('rule'):
            continue
        rtype = identify_rule(node, data)
        ct[rtype] += 1
        lem = False
        for ch in node.children:
            if ch.type in ['contexttest', 'rule_target']:
                ctype = identify_test(ch, rtype, data)
                by_type[rtype][ctype] += 1
                if ctype == 'other':
                    print(data[ch.start_byte:ch.end_byte])
                if 'lem' in ctype:
                    lem = True
        if lem:
            has_lem += 1
        else:
            no_lem += 1
    print(ct.most_common())
    for key in by_type:
        print(key, by_type[key].most_common())
    print(f'{has_lem=}, {no_lem=}, {has_lem/(has_lem+no_lem):.4}')
