import utils
import sys
import json

cs = utils.conllu_sentences

def collect(s):
    for w in utils.conllu_words(s):
        if w[3] != 'PUNCT':
            yield {'lemma': w[2], 'upos': w[3],
                   'gloss': utils.conllu_feature_dict(w[9]).get('Gloss')}

data = []
with open(sys.argv[1]) as f1, open(sys.argv[2]) as f2:
    for i, (s1, s2) in enumerate(zip(cs(f1), cs(f2))):
        sid = utils.get_id(s1)
        if not sid:
            continue
        data.append({'sid': sid, 'src': list(collect(s1)),
                     'tgt': list(collect(s2))})
print(json.dumps(data))

# python3 get_parallel_words.py generated/hbo-grc/hbo.conllu generated/hbo-grc/grc.conllu > possible.json
