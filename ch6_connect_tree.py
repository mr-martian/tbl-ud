import sys
import utils

def calc_depth(words):
    depth = [None] * len(words)
    def get_depth(n):
        nonlocal depth
        if depth[n] is None:
            if words[n][6] == '_':
                depth[n] = len(words) + 1
            elif words[n][6] == '0':
                depth[n] = 0
            else:
                depth[n] = get_depth(int(words[n][6])-1) + 1
        return depth[n]
    for n in range(len(words)):
        depth[n] = get_depth(n)
    return depth

for sent in utils.conllu_sentences(sys.stdin):
    for line in sent:
        if line.startswith('#'):
            print(line.strip())
    words = list(utils.conllu_words(sent))
    depth = calc_depth(words)
    for wid, wd in enumerate(words, 1):
        if wd[6] == '_':
            l = 1
            r = len(words)
            for wid2, wd2 in enumerate(words, 1):
                if wd2[6] in ['_', '0']:
                    continue
                if wid2 < wid and int(wd2[6]) > wid:
                    l = wid2
                elif wid2 > wid and int(wd2[6]) < wid:
                    r = wid2
            mni = 0
            mn = depth[wid-1]
            for i in range(l-1, r):
                if i + 1 == wid:
                    continue
                if depth[i] < mn:
                    mni = i + 1
                    mn = depth[i]
            wd[6] = str(mni)
            wd[7] = 'dep'
        print('\t'.join(wd))
    print()
