import json

def same_gloss(src, tgt):
    if not src or not tgt:
        return False
    if tgt == 'to-'+src:
        return True
    if src in tgt.split(','):
        return True
    return src == tgt

with open('actual.json') as fin:
    add = set((x['sl'], x['su'], x['tl'], x['tu']) for x in json.load(fin))
with open('possible.json') as fin:
    blob = json.load(fin)
    for sent in blob:
        for src in sent['src']:
            for tgt in sent['tgt']:
                if same_gloss(src['gloss'], tgt['gloss']):
                    add.add((src['lemma'], src['upos'],
                             tgt['lemma'], tgt['upos']))

with open('actual.json', 'w') as fout:
    fout.write(json.dumps([dict(list(zip(['sl', 'su', 'tl', 'tu'], tup))) for tup in add]))

