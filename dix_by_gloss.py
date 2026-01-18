import argparse
import collections
import utils
from xml.etree import ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('output')
parser.add_argument('--sfeats', '-s', action='append')
parser.add_argument('--tfeats', '-t', action='append')
args = parser.parse_args()

def process_feat_list(ls):
    ret = collections.defaultdict(list)
    for pos in ls or []:
        pieces = pos.split(':')
        ret[pieces[0]] = pieces[1:]
    return ret

sfeats = process_feat_list(args.sfeats)
tfeats = process_feat_list(args.tfeats)

def entries(sent, feats, freq):
    ret = collections.defaultdict(set)
    for word in utils.conllu_words(sent):
        dct = utils.conllu_feature_dict(word[9], True)
        dct.update(utils.conllu_feature_dict(word[5], True))
        ls = [word[2], word[3]]
        for f in feats[word[3]]:
            if f in dct:
                ls.append(dct[f])
        ret[dct.get('Gloss')].add(tuple(ls))
        freq[tuple(ls)] += 1
    return ret

def same_gloss(src, tgt):
    if not src or not tgt:
        return False
    if tgt == 'to-'+src:
        return True
    if src in tgt.split(','):
        return True
    return src == tgt

dix = collections.defaultdict(set)

lfreq = collections.Counter()
rfreq = collections.Counter()

for s1, s2 in utils.parallel_sentences(args.source, args.target):
    d1 = entries(s1, sfeats, lfreq)
    d2 = entries(s2, tfeats, rfreq)
    for g1 in d1:
        for g2 in d2:
            if same_gloss(g1, g2):
                for e1 in d1[g1]:
                    dix[e1].update(d2[g2])

root = ET.Element('dictionary')
ET.SubElement(root, 'alphabet')
sdefs = ET.SubElement(root, 'sdefs')
section = ET.SubElement(root, 'section', id='main', type='standard')
tags = set()
for w1 in sorted(dix.keys()):
    seq = sorted(((rfreq[w2], w2) for w2 in dix[w1]), reverse=True)
    for n, (freq, w2) in enumerate(seq):
        e = ET.SubElement(section, 'e', w=str(n))
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
for t in sorted(tags):
    ET.SubElement(sdefs, 'sdef', n=t)
ET.indent(sdefs, level=1)
with open(args.output, 'wb') as fout:
    tree = ET.ElementTree(root)
    tree.write(fout, encoding='utf-8', xml_declaration=True)
