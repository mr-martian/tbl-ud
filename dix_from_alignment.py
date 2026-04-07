from collections import Counter, defaultdict
import utils

def get_sents(lang):
    with open(f'manual-dix/{lang}.conllu') as fin:
        yield from utils.conllu_sentences(fin)

def get_align():
    with open('manual-dix/align.txt') as fin:
        for line in fin:
            if not line:
                break
            ls = []
            for pair in line.split():
                a, b = pair.split('-')
                ls.append((int(a), int(b)))
            yield ls

SPEC = {
    'grc': {
        'NOUN': ['Gender'],
        'DET': ['PronType'],
        'PROPN': ['Gender'],
    },
    'hbo': {
        'NOUN': ['Gender'],
        'VERB': ['HebBinyan'],
        'AUX': ['HebBinyan'],
        'DET': ['PronType'],
        'PROPN': ['Gender'],
    },
}
def word2tup(word, lang):
    dct = utils.conllu_feature_dict(word.misc, True)
    dct.update(utils.conllu_feature_dict(word.feats, True))
    ret = [word.lemma, word.upos]
    for key in SPEC[lang].get(word.upos, []) + ['ExtPos']:
        if key in dct:
            ret.append(dct[key])
    return tuple(ret)

skip = utils.load_json_set('manual-dix/maybe-skip.json')
data = defaultdict(Counter)
for idx, (hsent, gsent, alg) in enumerate(
        zip(get_sents('hbo'), get_sents('grc'), get_align())):
    if idx in skip:
        continue
    hwords = list(utils.conllu_words(hsent))
    gwords = list(utils.conllu_words(gsent))
    for hi, gi in alg:
        ht = word2tup(hwords[hi], 'hbo')
        gt = word2tup(gwords[gi], 'grc')
        data[ht][gt] += 1

utils.write_dictionary(data, 'manual-dix/with-skip.dix')
