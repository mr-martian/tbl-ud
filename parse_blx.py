import argparse
from collections import Counter
import glob
import json
import re
import sys
from xml.etree import ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('split')
args = parser.parse_args()

verse_re = re.compile(r'^# sent_id = Masoretic-([A-Za-z]+)-(\d+):([\d-]+)-hbo$')

verses = []

with open(glob.glob(f'/home/daniel/hbo-UD/UD_Ancient_Hebrew-PTNK/*{args.split}*.conllu')[0]) as fin:
    for line in fin:
        if 'sent_id' in line:
            m = verse_re.match(line.strip())
            if not m:
                raise ValueError(f'weird sent_id {line.strip()}')
            if '-' in m.group(3):
                v1, v2 = m.group(3).split('-')
                verses.append((m.group(1), int(m.group(2)),
                               int(v1), int(v2)))
            else:
                verses.append((m.group(1), int(m.group(2)),
                               int(m.group(3)), int(m.group(3))))

root = ET.parse('blx.flextext').getroot()

def item_dict(node):
    return {it.attrib.get('type'): it.text for it in node.findall('item')}

def add_feat(word, feat, misc=False):
    idx = 9 if misc else 5
    if word[idx] == '_':
        word[idx] = feat
    else:
        word[idx] += '|' + feat

TAGS = {
    ('v:AV voice', 'AV'): 'Voice=AV',
    ('v:AV aspect', 'PFV.AV'): 'Aspect=PFV|Voice=AV',
    ('v:aspect/voice', 'PV.PFV'): 'Aspect=PFV|Voice=PV',
    ('v>v', 'DUR.PL'): 'Aspect=Dur|Number=Plur',
    ('v:PV voice', 'PV'): 'Voice=PV',
    ('v:AV aspect', 'CTPLT.AV'): 'Aspect=Ctplt|Voice=AV',
    ('v>v', 'DUR'): 'Aspect=Dur',
    ('v:PV aspect', 'CTPLT.nPV'): 'Aspect=Ctplt|Voice=nPV',
    ('v>v', 'POT'): 'Mood=Pot',
    ('v:LV voice', 'LV.v'): 'Voice=LV',
    ('v>v', 'ABL'): 'Mood=Abl',
    ('v:CV voice/aspect', 'CV.PFV'): 'Aspect=PFV|Voice=CV',
    ('adj:(Adjpre)', 'Adj.Pos'): 'Poss=Yes',
    ('v>v', 'CAUS'): 'Caus=Yes',
    ('v:AV voice', None): 'Voice=AV',
    ('n>n', 'COLL'): 'Number=Col',
    ('v>v', 'REC'): 'Voice=Rec',
    ('adj:(Adjpre)', 'Adj.Neg'): 'Polarity=Neg',
    ('v:AV voice', 'AV.um'): 'Voice=AV',
    ('v:LV aspect', 'CTPLT.nLV'): 'Aspect=Ctplt|Voice=nLV',
    ('v>n', 'ASSOC'): 'Nmlz=Yes',
    (None, 'PV'): 'Voice=PV',
    ('v>n', 'A.NOM.PL'): 'Nmlz=Yes|Number=Plur',
    ('v:CV voice/aspect', 'CV.CTPLT'): 'Aspect=Ctplt|Voice=CV',
    ('v:AV aspect', 'PFV.AV.pre'): 'Aspect=PFV|Voice=AV',
    (None, 'CV.CTPLT'): 'Aspect=Ctplt|Voice=CV',
    ('v:LV aspect', 'LV.PFV'): 'Aspect=PFV|Voice=LV',
    ('adj:(Adjpre)', 'Adj.PL.Pos'): 'Poss=Yes|Number=Plur',
    ('v:LV aspect', 'CTPLT.LV'): 'Aspect=Ctplt|Voice=LV',
    ('v:AV aspect', 'CTPLT.nAV'): 'Aspect=Ctplt|Voice=nAV',
    ('v:PV aspect', 'CONT.PV'): 'Aspect=Cont|Voice=PV',
    (None, 'CV.PFV'): 'Aspect=PFV|Voice=CV',
    ('v>v', 'REQ'): 'Mood=Req',
    ('v>n', 'place.of'): 'Nmlz=Yes|Loc=Yes',
    ('v:LV aspect', 'PFV.LV'): 'Aspect=PFV|Voice=LV',
    ('v>v', 'HAB-REC'): 'Aspect=Hab|Voice=Rec',
    ('v:CV voice/aspect', 'CV.CONT'): 'Aspect=Cont|Voice=CV',
    ('v:LV aspect', None): 'Voice=LV',
    ('v:LV voice', None): 'Voice=LV',
    ('v>v', 'PL.AC'): 'Pluraction=Yes',
    ('Num>Num', 'Num+th'): 'NumType=Ord',
    ('v:LV aspect', 'CONT.LV'): 'Aspect=Cont|Voice=LV',
    ('v>v', 'TR'): 'Voice=TR',
    ('v>adj', 'V.to.HabV'): 'Adjz=Yes',
    ('adj>adj', 'very.X'): 'Emph=Yes',
    ('v>n', None): 'Nmlz=Yes',
    ('Num>adv', 'X.each'): 'NumType=Dist',
    ('v>v', 'stem.redup'): 'Redup=Yes',
    ('v>n', 'A.NOM'): 'Nmlz=Yes',
    ('v:CV voice/aspect', None): 'Voice=CV',
    ('adj>adj', 'most'): 'Degree=Sup',
    ('adj:(Adjpre)', 'Adj.PL.Neg'): 'Polarity=Neg|Number=Plur',
}

UPOS = {
    'n': 'NOUN',
    'det': 'DET',
    'conn': 'CCONJ',
    'v': 'VERB',
    'pron': 'PRON',
    '_': 'UNK',
    'adj': 'ADJ',
    'Num': 'NUM',
    'adv': 'ADV',
    'prt': 'PART',
    'dem': 'DET',
    'prep': 'ADP',
    'interj': 'INTJ',
    'adj  (PosAdj)': 'ADJ',
    'PseudoV': 'AUX',
    'adj  (NegAdj)': 'ADJ',
    'interrog': 'PART',
    'v  (part)': 'VERB',
}

morph_data = Counter()

verse_idx = 0
skipped = set()
book = 'Genesis'
chapter = 0
verse = 0
words = []
def include():
    if verse_idx >= len(verses):
        return False
    v = verses[verse_idx]
    return v[1] == chapter and v[2] <= verse <= v[3]
def finish_verse():
    global words, verse_idx, morph_data
    if not include():
        words = []
    else:
        verse_idx += 1
        if not include():
            vs = verses[verse_idx-1]
            vn = str(vs[2])
            if vs[2] != vs[3]:
                vn += '-' + str(vs[3])
            print(f'# sent_id = {vs[0]}-{vs[1]}:{vn}')
            for i, w in enumerate(words, 1):
                w[0] = str(i)
                w[6] = str(i)
                if w[4] in UPOS:
                    w[3] = UPOS[w[4]]
                else:
                    morph_data[w[4]] += 1
                    w[3] = 'UNK'
                if w[2] == '_':
                    w[2] = w[1]
                print('\t'.join(w))
            words = []
            print()
for chapter_node in root:
    for it in chapter_node.findall('item'):
        if it.attrib.get('type') == 'title':
            if 'RUT' in it.text:
                book = 'Ruth'
                chapter = int(it.text.split()[2][0])
            else:
                book = 'Genesis'
                chapter = int(it.text.split()[2].lstrip('0'))
    verse = 0
    if verse_idx >= len(verses):
        break
    if book != verses[verse_idx][0]:
        continue
    punct_seq = []
    for word_node in chapter_node.iter('word'):
        cur_word = ['_'] * 10
        wd = item_dict(word_node)
        if wd.get('punct'):
            if wd['punct'] == '\\':
                punct_seq = ['\\']
            elif wd['punct'] == 'v':
                punct_seq.append('v')
            elif punct_seq == ['\\', 'v'] and wd['punct'].isdigit():
                finish_verse()
                verse = int(wd['punct'])
            else:
                punct_seq = []
            continue
        cur_word[1] = wd['txt']
        cur_word[4] = wd.get('pos', '_')
        if wd.get('gls'):
            add_feat(cur_word, 'Gloss='+wd['gls'], True)
        for morph_node in word_node.iter('morph'):
            md = item_dict(morph_node)
            typ = morph_node.attrib.get('type')
            if typ in ['root', 'stem', 'phrase']:
                cur_word[2] = md.get('cf', md.get('txt', '_'))
                if 'gls' in md:
                    add_feat(cur_word, 'MGloss='+md['gls'], True)
                if md.get('msa'):
                    cur_word[4] = md['msa']
            elif typ in ['enclitic', 'clitic']:
                words.append(cur_word)
                cur_word = ['_'] * 10
                cur_word[1] = md['txt']
                cur_word[2] = md['cf']
                if md.get('msa'):
                    cur_word[4] = md['msa']
                if md.get('gls'):
                    add_feat(cur_word, 'Gloss='+md['gls'], True)
            elif typ is None:
                # TODO: we may need these for generation?
                continue
            else:
                key = (md.get('msa'), md.get('gls'))
                if key in TAGS:
                    add_feat(cur_word, TAGS[key], False)
                else:
                    morph_data[key] += 1
        if cur_word[1]:
            words.append(cur_word)
    finish_verse()
    while verse_idx < len(verses) and chapter == verses[verse_idx][1]:
        skipped.add(verse_idx)
        skipped.add(verse_idx - 1)
        print(f'# sent_id = null{verse_idx}')
        v = ['_'] * 10
        v[0] = '1'
        print('\t'.join(v))
        print()
        verse_idx += 1

print(json.dumps(sorted(skipped)), file=sys.stderr)
#print(morph_data.most_common(), file=sys.stderr)
