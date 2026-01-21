import collections
import json

unk_count = collections.Counter()
np_count = collections.Counter()
total_words = 0
np_words = 0
unk_words = 0

by_percent = []
by_unk_percent = []

lang_np = collections.Counter()
lang_unk = collections.Counter()
lang_total = collections.Counter()

np_types = collections.Counter()

with open('tb-logs/all.jsonl') as fin:
    for line in fin:
        if line.count('\t') == 1:
            tb, blob = line.split('\t')
            dct = json.loads(blob)
            total_words += dct['total']
            np = sum(dct['nonproj'].values())
            np_words += np
            np_count[np] += 1
            unk = dct['nonproj'].get('unknown', 0)
            unk_count[unk] += 1
            unk_words += unk
            by_percent.append((np*100.0/dct['total'], tb, np, dct['total']))
            by_unk_percent.append((unk*100.0/dct['total'], tb, unk, dct['total']))
            lang = tb[3:].split('-')[0]
            lang_np[lang] += np
            lang_unk[lang] += unk
            lang_total[lang] += dct['total']
            np_types += collections.Counter(dct['nonproj'])

print(total_words, np_words, round(np_words*100.0/total_words, 2))
print(total_words, unk_words, round(unk_words*100.0/total_words, 2))
print('of', len(by_percent), 'treebanks,')
print('\t', np_count[0], 'have no nonproj words')
print('\t', unk_count[0], 'have no unknown nonproj words')
print('top nonproj')
by_percent.sort()
for p, t, np, tot in by_percent[-10:]:
    print('%30s %5.2f %10d %8d' % (t, p, np, tot))
print('top unknown nonproj')
by_unk_percent.sort()
for p, t, np, tot in by_unk_percent[-10:]:
    print('%30s %5.2f %10d %8d' % (t, p, np, tot))
print('top nonproj lang')
ls = sorted([(lang_np[l] * 100.0 / lang_total[l], l) for l in lang_total])
for p, l in ls[-10:]:
    print('%30s %5.2f' % (l, p))
print('top unknown lang')
ls = sorted([(lang_unk[l] * 100.0 / lang_total[l], l) for l in lang_total])
for p, l in ls[-10:]:
    print('%30s %5.2f' % (l, p))
print('all types')
for key, count in np_types.most_common():
    print('%20s %10d %10.2f' % (key, count, 100.0*count/np_words))
