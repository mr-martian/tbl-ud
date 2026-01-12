TAGS = {
    'vblex': 'VERB',
    'sg': 'Number=Sing',
    'n': 'NOUN',
    'pres': 'Tense=Pres',
    'inf': 'VerbForm=Inf',
    'imp': 'Mood=Imp',
    'pl': 'Number=Plur',
    'past': 'Tense=Past',
    'adj': 'ADJ',
    'pp': ['VerbForm=Part', 'Tense=Past'],
    'p3': 'Person=3',
    'np': 'PROPN',
    'adv': 'ADV',
    'ant': 'LexCat=Ant',
    'm': 'Gender=Masc',
    'subs': 'VerbForm=Ger',
    'pprs': ['VerbForm=Part', 'Tense=Pres'],
    'ger': 'VerbForm=Ger',
    'sep': 'LexCat=Sep',
    'sint': 'LexCat=Sint',
    'num': 'NUM',
    'prn': 'PRON',
    'mf': 'Gender=Fem,Masc',
    'pr': 'ADP',
    'det': 'DET',
    'sp': 'Number=Plur,Sing',
    'top': 'LexCat=Top',
    'ind': 'Mood=Ind',
    'cnjadv': ['ADV', 'LexCat=Cnj'],
    'vbmod': 'AUX',
    'f': 'Gender=Fem',
    'cog': 'LexCat=Cog',
    'pos': 'Case=Gen',
    'cnjsub': 'SCONJ',
    'ord': 'NumType=Ord',
    'comp': 'Degree=Cmp',
    'p1': 'Person=1',
    'qnt': 'LexCat=Qnt',
    'itg': 'PronType=Int',
    'dem': 'PronType=Dem',
    'prs': 'PronType=Prs',
    'vbser': 'AUX',
    'cnjcoo': 'CCONJ',
    'p2': 'Person=2',
    'nt': 'Gender=Neut',
    'vbdo': 'AUX',
    'subj': 'Case=Nom',
    'preadv': ['ADV', 'LexCat=Pre'],
    'nom': 'Case=Nom',
    'vaux': 'AUX',
    'rel': 'PronType=Rel',
    'vbhaver': 'AUX',
    'sup': 'Degree=Sup',
    'ij': 'INTJ',
    'ref': 'PronType=Rcp',
    'obj': 'Case=Acc',
    'an': 'Animacy=Anim,Inan',
    'al': 'LexCat=Al',
    'acc': 'Case=Acc',
    'pred': 'LexCat=Pred', # TODO
    'predet': 'DET', # ???
    'pers': 'PronType=Prs',
    'nn': 'Animacy=Inan',
    'def': 'Definite=Def',
    'sent': 'PUNCT',
    'cm': 'PUNCT',
    'lquot': 'PUNCT',
    'rquot': 'PUNCT',
    'guio': 'PUNCT',
    'lpar': 'PUNCT',
    'rpar': 'PUNCT',
    'gen': ['PART', 'Case=Gen'],
    'apos': 'PUNCT',
    'abbr': 'X',
}

def translate(reading):
    if '<' not in reading:
        return (reading, ())
    lem, tags = reading.split('<', 1)
    tagls = [lem]
    for t in ('<' + tags).split('>'):
        if not t:
            continue
        if t.startswith('<'):
            v = TAGS[t[1:]]
            if isinstance(v, list):
                tagls += v
            else:
                tagls.append(v)
        else:
            lem += t
    return tuple(tagls)

if __name__ == '__main__':
    import re
    import sys
    def repl(m):
        t = TAGS[m.group(1)]
        if isinstance(t, list):
            t = '><'.join(t)
        return '<'+t+'>'
    for line in sys.stdin:
        sys.stdout.write(re.sub(r'<(\w+)>', repl, line.strip()) + '\0\n')
