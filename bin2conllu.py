import cg3
import sys

for sid, window in enumerate(cg3.parse_binary_stream(sys.stdin.buffer, windows_only=True), 1):
    print(f'# sent_id = s{sid}')
    ids = {0: 0}
    for i, cohort in enumerate(window.cohorts, 1):
        ids[cohort.dep_self] = i
    for cohort in window.cohorts:
        cols = ['_'] * 10
        cols[0] = str(ids[cohort.dep_self])
        cols[1] = cohort.static.lemma[2:-2]
        rd = cohort.readings[0]
        cols[2] = rd.lemma[1:-1]
        cols[3] = rd.tags[0]
        cols[5] = '|'.join(t for t in rd.tags if '=' in t) or '_'
        cols[6] = str(ids[cohort.dep_parent])
        at = [t for t in rd.tags if t[0] == '@']
        if at:
            cols[7] = at[0].lstrip('@')
        print('\t'.join(cols))
    print()
