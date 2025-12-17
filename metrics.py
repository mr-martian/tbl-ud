from collections import Counter, defaultdict

def PER_readings(window, with_features):
    for cohort in window.cohorts:
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            if with_features:
                yield frozenset([reading.lemma] + reading.tags)
            else:
                yield frozenset([reading.lemma, reading.tags[0]])
            break
def PER(source, target):
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
        sf = Counter(PER_readings(sw, True))
        tf = Counter(PER_readings(tw, True))
        fcorrect += (sf & tf).total()
    deletions = max(0, swords - twords)
    return (100 * (1 - float(lcorrect - deletions)/twords),
            100 * (1 - float(fcorrect - deletions)/twords))

if __name__ == '__main__':
    from cg3 import parse_binary_stream
    import sys
    with (open(sys.argv[1], 'rb') as f1,
          open(sys.argv[2], 'rb') as f2):
        print('%s\t%s' % PER(
            list(parse_binary_stream(f1, windows_only=True)),
            list(parse_binary_stream(f2, windows_only=True))))
