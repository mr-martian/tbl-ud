import argparse
import collections
import glob
import json
import re
import subprocess
import unicodedata
import utils
from xml.etree import ElementTree as ET

strong2eng = collections.defaultdict(set)

implicit = re.compile(r'\[[^\[\]]+\]|\([^()]+\)|’s|[?!~]')

stop_words = set([
    'am', 'are', 'is', 'were', 'be', 'being', 'become', 'became',
    'may', 'let', 'has', 'have', 'had', 'will', 'do', 'did',
    'him', 'her', 'it', 'them', 'I', 'you', 'they', 'me', 'he', 'it',
    'of', 'the', 'to', 'a', 'an', 'O',
])

def clean_hbo_gloss(g):
    if not g:
        return []
    g = implicit.sub('', g).replace('.', ' ').split()
    if any(w not in stop_words for w in g):
        g = [w for w in g if w not in stop_words]
    return g

for pfx in ['01', '08']:
    for fname in glob.glob(f'../hbo-UD/macula-hebrew/WLC/nodes/{pfx}-*.xml'):
        blob = ET.parse(fname)
        for m in blob.getroot().iter('m'):
            if 'oshb-strongs' in m.attrib:
                s = m.attrib['oshb-strongs']
                strong2eng[s].update(clean_hbo_gloss(m.attrib.get('english')))
                strong2eng[s].update(clean_hbo_gloss(m.attrib.get('gloss')))

eng2blx = collections.defaultdict(set)

blx_feats = set()

def clean_blx_gloss(g):
    if not g:
        return []
    if g.startswith('to.'):
        g = g[3:]
    if g.startswith('be.'):
        g = g[3:]
    g = g.replace('.Noun', '').replace('.Verb', '').replace('.Adjective', '')
    return re.split(r'[\W\d]+', g)

for fname in glob.glob('generated/blx/blx.*.conllu'):
    with open(fname) as fin:
        for word in utils.conllu_words(fin):
            misc = utils.conllu_feature_dict(word[9])
            feats = utils.conllu_feature_dict(word[5], True)
            ls = [word[2], word[3]]
            for key in ['Voice', 'Caus']:
                if key in feats:
                    ls.append(feats[key])
            ls = tuple(ls)
            for key in ['Gloss', 'MGloss']:
                for piece in clean_blx_gloss(misc.get(key)):
                    eng2blx[piece].add(ls)
            blx_feats.update(utils.conllu_feature_dict(word[5]).keys())

strong2hbo = collections.defaultdict(set)
HBO_SPEC = {
    'NOUN': ['Gender'],
    'VERB': ['HebBinyan'],
    'AUX': ['HebBinyan'],
    'DET': ['PronType'],
    'PROPN': ['Gender'],
}
for fname in glob.glob('../hbo-UD/UD_Ancient_Hebrew-PTNK/*.conllu'):
    with open(fname) as fin:
        for word in utils.conllu_words(fin):
            if 'LId[Strongs]' in word[9]:
                s = word[9].split('LId[Strongs]=')[1].split('|')[0]
                parts = [word[2], word[3]]
                feats = utils.conllu_feature_dict(word[5], True)
                for f in HBO_SPEC.get(word[3], []):
                    if f in feats:
                        parts.append(feats[f])
                strong2hbo[s].add(tuple(parts))

pairs = collections.defaultdict(collections.Counter)
for strong in strong2eng:
    for hbo in strong2hbo[strong]:
        for eng in strong2eng[strong]:
            for blx in eng2blx[eng]:
                if utils.check_upos(hbo[1], blx[1]):
                    pairs[hbo][blx] += 1

utils.write_dictionary(pairs, 'generated/blx/blx.dix')
with open('generated/blx/blx.feats.json', 'w') as fout:
    print(json.dumps(sorted(blx_feats)), file=fout)
