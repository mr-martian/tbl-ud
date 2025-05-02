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

def conllu_words(sent):
    for line in sent:
        if line.count('\t') == 9 and line.split('\t', 1)[0].isdigit():
            yield line.strip().split('\t')

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
