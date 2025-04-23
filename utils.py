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
            yield line.split('\t')

def conllu_feature_dict(field):
    if field == '_':
        return {}
    ret = {}
    for piece in field.split('|'):
        k, v = piece.split('=', 1)
        ret[k] = v
    return ret
