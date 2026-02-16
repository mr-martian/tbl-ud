class IDGiver:
    def __init__(self):
        self.id2item = []
        self.item2id = {}
    def __getitem__(self, item):
        if isinstance(item, int):
            return self.id2item[item]
        else:
            if item not in self.item2id:
                self.item2id[item] = len(self.id2item)
                self.id2item.append(item)
            return self.item2id[item]

def conllu_sentences(fin):
    cur = []
    for line in fin:
        if not line.strip():
            if cur:
                yield cur
            cur = []
        else:
            cur.append(line)
    if cur:
        yield cur

from collections import namedtuple
ud_word = namedtuple('UDWord', ['idx', 'form', 'lemma', 'upos', 'xpos', 'feats', 'head', 'deprel', 'deps', 'misc'])
def conllu_words(sent):
    for line in sent:
        if line.count('\t') == 9 and line.split('\t', 1)[0].isdigit():
            yield ud_word(*line.strip().split('\t'))

def conllu_feature_dict(field, with_prefix=False):
    if field == '_':
        return {}
    ret = {}
    for piece in field.split('|'):
        if '=' not in piece:
            import sys
            print([piece, field], file=sys.stderr)
        k, v = piece.split('=', 1)
        ret[k] = piece if with_prefix else v
    return ret

def get_id(sentence):
    for line in sentence:
        if line.startswith('# sent_id ='):
            return line.split('=')[1].strip()

def parallel_sentences(fname1, fname2):
    with open(fname1) as f1, open(fname2) as f2:
        yield from zip(conllu_sentences(f1), conllu_sentences(f2))

def write_dictionary(entries, fname):
    # entries is defaultdict(Counter)
    from xml.etree import ElementTree as ET
    root = ET.Element('dictionary')
    ET.SubElement(root, 'alphabet')
    sdefs = ET.SubElement(root, 'sdefs')
    section = ET.SubElement(root, 'section', id='main', type='standard')
    tags = set()
    for lt in sorted(entries.keys()):
        rts = entries[lt].most_common()
        for n, (rt, freq) in enumerate(rts):
            if freq < rts[0][1] // 10: # TODO: document factor
                break
            e = ET.SubElement(section, 'e', w=str(n))
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
    with open(fname, 'wb') as fout:
        tree = ET.ElementTree(root)
        tree.write(fout, encoding='utf-8', xml_declaration=True)

def check_upos(h, g):
    if h == '_' or g == '_':
        return False
    if h == 'DET':
        if g in ['NOUN', 'VERB', 'AUX', 'ADP', 'ADV']:
            return False
    if h == 'PROPN':
        return (g in ['NOUN', 'PROPN'])
    if h == 'CCONJ':
        return (g == 'CCONJ')
    if g == 'CCONJ':
        return (h == 'CCONJ')
    if g == 'DET':
        if h in ['NOUN', 'VERB', 'AUX', 'ADP', 'ADV']:
            return False
    if h == 'ADP':
        if g in ['ADJ', 'NOUN', 'VERB', 'AUX', 'PRON']:
            return False
    if h in ['VERB', 'NOUN']:
        if g in ['PRON', 'ADP', 'ADV']:
            return False
    if h == 'NOUN' and g == 'AUX':
        return False
    return True

def primary_reading(cohort):
    for r in cohort.readings:
        if 'SOURCE' in r.tags:
            continue
        return r

def load_json_set(path):
    if not path:
        return set()
    import json
    with open(path) as fin:
        return set(json.loads(fin.read()))
