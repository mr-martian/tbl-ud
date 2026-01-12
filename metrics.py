from collections import Counter, defaultdict

def PER_readings(window, with_features, target_features=None):
    for cohort in window.cohorts:
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            if with_features:
                if target_features is None:
                    yield frozenset([reading.lemma] + reading.tags)
                else:
                    ls = [reading.lemma, reading.tags[0]]
                    for t in reading.tags:
                        if '=' in t and t.split('=')[0] in target_features:
                            ls.append(t)
                    yield frozenset(ls)
            else:
                yield frozenset([reading.lemma, reading.tags[0]])
            break
def PER(source, target, target_features=None):
    swords = 0
    twords = 0
    lcorrect = 0
    fcorrect = 0
    for sw, tw in zip(source, target):
        swords += len(sw.cohorts)
        twords += len(tw.cohorts)
        sl = Counter(PER_readings(sw, False))
        tl = Counter(PER_readings(tw, False))
        lcorrect += (sl & tl).total()
        sf = Counter(PER_readings(sw, True, target_features))
        tf = Counter(PER_readings(tw, True, target_features))
        fcorrect += (sf & tf).total()
    deletions = max(0, swords - twords)
    return (100 * (1 - float(lcorrect - deletions)/twords),
            100 * (1 - float(fcorrect - deletions)/twords))

if __name__ == '__main__':
    import argparse
    from cg3 import parse_binary_stream
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('src')
    parser.add_argument('tgt')
    parser.add_argument('--target_feats', action='store')
    args = parser.parse_args()
    target_feats = None
    if args.target_feats:
        with open(args.target_feats) as fin:
            target_feats = set(json.loads(fin.read()))
    with (open(args.src, 'rb') as f1,
          open(args.tgt, 'rb') as f2):
        print('%s\t%s' % PER(
            list(parse_binary_stream(f1, windows_only=True)),
            list(parse_binary_stream(f2, windows_only=True)),
            target_feats))
