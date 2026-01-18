import argparse
import collections
import glob
import subprocess
import unicodedata
import utils
from xml.etree import ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('version')
args = parser.parse_args()

form2strong = collections.defaultdict(set)
strong2form = collections.defaultdict(set)
form_freq = collections.Counter()

drop_chars = "(),.“‘–?!”:;’,?'.!,()"

for pfx in ['02', '03', '04', '05', '06', '09']:
    for fname in glob.glob(f'{args.version}/{pfx}*.usfm'):
        with open(fname) as fin:
            for w in fin.read().replace("’", "'").split():
                if 'strong=' not in w:
                    continue
                form = w.split('|')[0]
                if '+nd' in form:
                    form = form.split('\\')[0]
                for c in drop_chars:
                    form = form.strip(c)
                if form:
                    strong = w.split('"')[1]
                    form2strong[form].add(strong)
                    strong2form[strong].add(form)
                    form_freq[form] += 1

ana = b'\0'.join(f.encode('utf-8') for f in sorted(form2strong))
proc = subprocess.run(
    ['lt-proc', '-w', '-z',
     '/home/daniel/apertium/apertium-data/apertium-eng/eng.automorf.bin'],
    input=ana,
    capture_output=True)

from eng_tags import translate

form2tags = collections.defaultdict(set)

for we in proc.stdout.split(b'\0'):
    w = we.decode('utf-8')
    if w.count('^') != 1:
        # skip the ~2% that translate to phrases
        continue
    lu = w.split('^')[1].split('$')[0]
    rds = lu.split('/')
    form = rds[0]
    for r in rds[1:]:
        if '<' not in r:
            continue
        if '+' in r:
            continue
        if '<abbr>' in r:
            continue
        if '<attr>' in r:
            continue
        tags = translate(r)
        tags = tuple([t for t in tags if '=' not in t or 'LexCat' in t or 'Gender' in t])
        form2tags[form].add(tags)

HBO_SPEC = {
    'NOUN': ['Gender'],
    'VERB': ['HebBinyan'],
    'AUX': ['HebBinyan'],
    'DET': ['PronType'],
    'PROPN': ['Gender'],
}
def get_feats(line):
    ls = line.split('\t')
    lem = ls[2]
    upos = ls[3]
    feats = (ls[5] + '|' + ls[9]).split('|')
    tags = [lem, upos]
    for fn in HBO_SPEC.get(upos, []):
        tags += [f for f in feats if f.startswith(fn+'=')]
    strong = [f for f in feats if f.startswith('LId[Strongs]=')][0].split('=')[1]
    return (strong, tuple(tags))

strong2hbo = collections.defaultdict(set)
for fname in glob.glob('../hbo-UD/UD_Ancient_Hebrew-PTNK/*.conllu'):
    with open(fname) as fin:
        for line in fin:
            if 'LId[Strongs]' in line:
                strong, tags = get_feats(line)
                strong = strong.rstrip('+')
                if strong[0].isdigit():
                    strong = ''.join([c for c in strong if c.isdigit()])
                    strong = strong.rjust(4, '0')
                strong2hbo['H'+strong].add(tags)
#print([s for s in strong2hbo if s not in strong2form])
#print([s for s in strong2form if s not in strong2hbo])

strong2form['Hb'].add('in')
strong2form['Hc'].add('and')
strong2form['Hd'].add('the')
#strong2form['Hi'].add('') question mark
strong2form['Hk'].add('as')
strong2form['Hl'].add('to')
strong2form['Hm'].add('from')
#strong2form['Hs'].add('') short asher

pairs = collections.defaultdict(collections.Counter)
pos_pairs = collections.Counter()
for strong in strong2form:
    for hbo in strong2hbo[strong]:
        for form in strong2form[strong]:
            for eng in form2tags[form]:
                if utils.check_upos(hbo[1], eng[1]):
                    pairs[hbo][eng] = form_freq[form]
                    pos_pairs[(hbo[1], eng[1])] += 1
#for p in pos_pairs.most_common():
#    print(p)

utils.write_dictionary(pairs, f'generated/hbo-eng/{args.version}.dix')
