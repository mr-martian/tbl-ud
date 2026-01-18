from collections import Counter, defaultdict
import glob
import unicodedata
import utils
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
form2sdbh = defaultdict(set)

strong2form = defaultdict(set)
sdbh2form = defaultdict(set)

for fname in glob.glob('/home/daniel/hbo-UD/macula-hebrew/WLC/nodes/*.xml'):
    tree = ET.parse(fname)
    for node in tree.getroot().iter('Node'):
        if 'Greek' not in node.attrib:
            continue
        form = norm(node.attrib['Greek'])
        for m in node.iter('m'):
            if 'oshb-strongs' in m.attrib:
                form2strong[form].add(m.attrib['oshb-strongs'])
                strong2form[m.attrib['oshb-strongs']].add(form)
            if 'SDBH' in m.attrib:
                form2sdbh[form].add(m.attrib['SDBH'])
                sdbh2form[m.attrib['SDBH']].add(form)

strong_count = Counter(len(v) for v in strong2form.values())
sdbh_count = Counter(len(v) for v in sdbh2form.values())
print(f'{strong_count.most_common()=}, {sdbh_count.most_common()=}')

strong2tags = defaultdict(set)
sdbh2tags = defaultdict(set)

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

grc_tag_freq = Counter()

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
        data = tuple([lem, upos] + get_feats(GRC_SPEC, upos, feats, misc))
        for s in form2strong[form]:
            strong2tags[s].add(data)
        for s in form2sdbh[form]:
            sdbh2tags[s].add(data)
        grc_tag_freq[data] += 1

entries = defaultdict(Counter)

for fname in glob.glob('/home/daniel/hbo-UD/UD_Ancient_Hebrew-PTNK/*.conllu'):
    for form, lem, upos, feats, misc in iter_words(fname):
        ls = [m.split('=')[1] for m in misc if m.startswith('LId[Strongs]')]
        data = [lem, upos] + get_feats(HBO_SPEC, upos, feats, misc)
        for s in ls:
            for tg in strong2tags[s]:
                if utils.check_upos(data[1], tg[1]):
                    entries[tuple(data)][tg] = grc_tag_freq[tg]

utils.write_dictionary(entries, 'generated/hbo-grc/macula.dix')
