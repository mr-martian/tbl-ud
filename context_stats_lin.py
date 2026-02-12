import glob
import re
from collections import Counter, defaultdict

upos_re = re.compile(r'\b(ADJ|ADP|ADV|AUX|CCONJ|DET|INTJ|NOUN|NUM|PART|PRON|PROPN|PUNCT|SCONJ|SYM|VERB|X|UNK)\b')

langs = defaultdict(Counter)
for fname in glob.glob('lin-exp-data/*.lin'):
    lang = fname.split('/')[-1].split('-')[0]
    with open(fname) as fin:
        for line in fin:
            if not line:
                continue
            key = []
            if '"' in line:
                key.append('lem')
            if '@' in line:
                key.append('rel')
            if upos_re.search(line):
                key.append('upos')
            if '=' in line:
                key.append('feat')
            langs[lang]['-'.join(key) or 'other'] += 1

for lang in langs:
    print(lang, langs[lang].most_common())
    print('\t', sum(langs[lang][k] for k in langs[lang] if 'lem' in k) / langs[lang].total())
