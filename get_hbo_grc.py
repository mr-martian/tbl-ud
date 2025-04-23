import collections
import glob
import sys
import unicodedata
import utils
import xml.etree.ElementTree as ET

def get_names():
    yield from glob.glob('/home/daniel/hbo-UD/macula-hebrew/WLC/nodes/01-Gen*.xml')
    yield from glob.glob('/home/daniel/hbo-UD/macula-hebrew/WLC/nodes/08-Rut*.xml')

words = {}
for fname in get_names():
    root = ET.parse(fname).getroot()
    for word in root.findall('.//Node[@Greek]'):
        if len(word) == 1 and word[0].tag == 'm':
            words[word[0].attrib['{http://www.w3.org/XML/1998/namespace}id']] = unicodedata.normalize('NFC', word.attrib['Greek'])

cs = utils.conllu_sentences
with open(sys.argv[1]) as hin, open(sys.argv[2]) as gin:
    for hsent, gsent in zip(cs(hin), cs(gin)):
        gwords = collections.defaultdict(list)
        for i, w in enumerate(utils.conllu_words(gsent)):
            gwords[unicodedata.normalize('NFC', w[1].lower())].append(i)
        for i, hw in enumerate(utils.conllu_words(hsent)):
            wid = utils.conllu_feature_dict(hw[9]).get('Ref[MACULA]')
            if wid not in words:
                continue
            for j in gwords[words[wid]]:
                print(f'{i}-{j}', end=' ')
        print('')
# TODO: maybe skip NOUN->DET mappings?
