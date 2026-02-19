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

def clean_gloss(gloss, is_hbo):
    if is_hbo:
        return gloss.lstrip('<').rstrip('>')
    else:
        return gloss.lstrip('to-').replace('-', ' ').replace(';', ',')

def entries(sent, feats, freq, is_hbo):
    ret = collections.defaultdict(set)
    for word in utils.conllu_words(sent):
        dct = utils.conllu_feature_dict(word[9], True)
        dct.update(utils.conllu_feature_dict(word[5], True))
        ls = [word[2], word[3]]
        for f in feats[word[3]]:
            if f in dct:
                ls.append(dct[f])
        if 'Gloss' in dct:
            gl = clean_gloss(dct['Gloss'].split('=', 1)[1], is_hbo)
            ret[gl].add(tuple(ls))
        freq[tuple(ls)] += 1
    return ret

def same_gloss(src, tgt):
    if not src or not tgt:
        return False
    if tgt == 'to-'+src:
        return True
    if src in [t.strip() for t in tgt.split(',')]:
        return True
    return src == tgt

dix = collections.defaultdict(set)

lfreq = collections.Counter()
rfreq = collections.Counter()

SKIP_VERSES = ['31:51', '32:33', '35:21']
with open(args.source) as fin:
    source_sents = list(utils.conllu_sentences(fin))
    source_sents = [s for s in source_sents
                    if not any(x in s[0] for x in SKIP_VERSES)]
with open(args.target) as fin:
    target_sents = list(utils.conllu_sentences(fin))

src_same = set()
tgt_same = set()
src_not_same = set()
tgt_not_same = set()
for s1, s2 in zip(source_sents, target_sents):
    d1 = entries(s1, sfeats, lfreq, True)
    d2 = entries(s2, tfeats, rfreq, False)
    ss, ts, sns, tns = set(), set(), set(), set()
    for g1 in d1:
        sns.add(g1)
        for g2 in d2:
            tns.add(g2)
            if same_gloss(g1, g2):
                for e1 in d1[g1]:
                    dix[e1].update(d2[g2])
                ss.add(g1)
                ts.add(g2)
    src_same.update(ss)
    tgt_same.update(ts)
    src_not_same.update(sns - ss)
    tgt_not_same.update(tns - ts)

print(src_not_same - src_same)
print(tgt_not_same - tgt_same)

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
