from collections import Counter, defaultdict
import glob
import unicodedata
from xml.etree import ElementTree as ET

GRC_SPEC = {
    'NOUN': ['Gender'],
    'DET': ['PronType'],
    'PROPN': ['Gender'],
}
HBO_SPEC = {
    'NOUN': ['Gender'],
    'VERB': ['HebBinyan'],
    'AUX': ['HebBinyan'],
    'DET': ['PronType'],
    'PROPN': ['Gender'],
}

def norm(s):
    return unicodedata.normalize('NFC', s.lower())

form2strong = defaultdict(set)

for fname in glob.glob('/home/daniel/hbo-UD/macula-hebrew/WLC/nodes/*.xml'):
    tree = ET.parse(fname)
    for node in tree.getroot().iter('Node'):
        if 'Greek' not in node.attrib:
            continue
        form = norm(node.attrib['Greek'])
        for m in node.iter('m'):
            if 'oshb-strongs' in m.attrib:
                form2strong[form].add(m.attrib['oshb-strongs'])

strong2tags = defaultdict(set)

def parse_feats(field):
    if field == '_':
        return []
    return field.split('|')
def iter_words(fname):
    with open(fname) as fin:
        for line in fin:
            ls = line.rstrip().split('\t')
            if len(ls) != 10:
                continue
            yield (ls[1], ls[2], ls[3], parse_feats(ls[5]),
                   parse_feats(ls[9]))
def get_feats(spec, upos, feats, misc):
    ret = []
    for fn in spec.get(upos, []) + ['ExtPos']:
        ret += [f for f in feats if f.startswith(fn+'=')]
        ret += [f for f in misc if f.startswith(fn+'=')]
    return ret

grc_good = 0
grc_bad = 0
grc_bad_forms = set()
for fname in glob.glob('/home/daniel/UD_Ancient_Greek-PTNK/*.conllu'):
    for form, lem, upos, feats, misc in iter_words(fname):
        form = norm(form)
        if form not in form2strong:
            grc_bad += 1
            grc_bad_forms.add(form)
            continue
        grc_good += 1
        data = [lem, upos] + get_feats(GRC_SPEC, upos, feats, misc)
        for s in form2strong[form]:
            strong2tags[s].add(tuple(data))

pairs = set()

for fname in glob.glob('/home/daniel/hbo-UD/UD_Ancient_Hebrew-PTNK/*.conllu'):
    for form, lem, upos, feats, misc in iter_words(fname):
        ls = [m.split('=')[1] for m in misc if m.startswith('LId[Strongs]')]
        data = [lem, upos] + get_feats(HBO_SPEC, upos, feats, misc)
        for s in ls:
            for tg in strong2tags[s]:
                pairs.add((tuple(data), tg))

root = ET.Element('dictionary')
ET.SubElement(root, 'alphabet')
sdefs = ET.SubElement(root, 'sdefs')
section = ET.SubElement(root, 'section', id='main', type='standard')
tags = set()
for lt, rt in sorted(pairs):
    e = ET.SubElement(section, 'e')
    e.tail = '\n    '
    p = ET.SubElement(e, 'p')
    l = ET.SubElement(p, 'l')
    l.text = lt[0]
    for t in lt[1:]:
        if t is None: continue
        tags.add(t)
        ET.SubElement(l, 's', n=t)
    r = ET.SubElement(p, 'r')
    r.text = rt[0]
    for t in rt[1:]:
        if t is None: continue
        tags.add(t)
        ET.SubElement(r, 's', n=t)
for t in sorted(tags):
    ET.SubElement(sdefs, 'sdef', n=t)
ET.indent(sdefs, level=1)
with open('generated/hbo-grc/macula.dix', 'wb') as fout:
    tree = ET.ElementTree(root)
    tree.write(fout, encoding='utf-8', xml_declaration=True)
