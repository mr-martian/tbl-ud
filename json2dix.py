import argparse
import collections
import json
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('json1')
parser.add_argument('json2')
parser.add_argument('align')
parser.add_argument('out')
parser.add_argument('--exclude', '-e', action='append')
args = parser.parse_args()

pair_skip_lr = collections.defaultdict(set)
pair_skip_rl = collections.defaultdict(set)
pair_skip_lr['PUNCT'].add(None)
pair_skip_rl['PUNCT'].add(None)
for ex in args.exclude or []:
    a, b = ex.split(':')
    if a:
        pair_skip_lr[a].add(b or None)
    if b:
        pair_skip_rl[b].add(a or None)
def should_skip(l, r):
    if l == r:
        return False
    if None in pair_skip_lr[l] or None in pair_skip_rl[r]:
        return True
    return r in pair_skip_lr[l] or l in pair_skip_rl[r]

with open(args.json1) as fin:
    data1 = json.load(fin)

with open(args.json2) as fin:
    data2 = json.load(fin)

word_pairs = set()
with open(args.align) as fin:
    for i, line in enumerate(fin):
        for pair in line.split():
            n1, n2 = pair.split('-')
            n1 = int(n1)
            n2 = int(n2)
            w1 = data1['words'][data1['sents'][i][n1]]
            w2 = data2['words'][data2['sents'][i][n2]]
            if should_skip(w1[1], w2[1]):
                continue
            word_pairs.add((tuple(w1), tuple(w2)))

tag_pairs = collections.Counter()
dix = ET.Element('dictionary')
ET.SubElement(dix, 'alphabet')
sdefs = ET.SubElement(dix, 'sdefs')
section = ET.SubElement(dix, 'section', id='main', type='standard')
tags = set()
for w1, w2 in sorted(word_pairs, key=str):
    e = ET.SubElement(section, 'e')
    e.tail = '\n    '
    p = ET.SubElement(e, 'p')
    l = ET.SubElement(p, 'l')
    l.text = w1[0]
    for t in w1[1:]:
        if t is None: continue
        tags.add(t)
        ET.SubElement(l, 's', n=t)
    r = ET.SubElement(p, 'r')
    r.text = w2[0]
    for t in w2[1:]:
        if t is None: continue
        tags.add(t)
        ET.SubElement(r, 's', n=t)
    tag_pairs[(w1[1], w2[1])] += 1
for t in sorted(tags):
    ET.SubElement(sdefs, 'sdef', n=t)
ET.indent(sdefs, level=1)
with open(args.out, 'wb') as fout:
    tree = ET.ElementTree(dix)
    tree.write(fout, encoding='utf-8', xml_declaration=True)
print(tag_pairs.most_common())
