import matplotlib.pyplot as plt
import glob
from collections import defaultdict

rows = defaultdict(list)

def to_list(s):
    return [x.strip() for x in s.replace('\\', '').replace('%', '').split('&')]

langs = ['Ancient_Greek', 'Ancient_Hebrew', 'Khoekhoe', 'North_Sami', 'Welsh']

for lang in langs:
    for fname in glob.glob(f'lin-exp-data/UD_{lang}*.log'):
        if 'short' in fname:
            continue
        if 'long' in fname:
            continue
        if 'mid' in fname:
            continue
        print(fname)
        ls = fname.split('.')
        key = (lang, ls[1], ls[3])
        count = int(ls[2])
        with open(fname) as fin:
            for line in fin:
                if '&' in line:
                    ls = to_list(line)
                    rows[key].append((count, float(ls[-2]), float(ls[-1])))

fig, (a_lang, a_alg) = plt.subplots(2)
a_lang.set(ylabel='WER')
a_alg.set(ylabel='WER', xlabel='Rules per Iteration')

alg_used = set()
lang_used = set()
for (lang, _, mode), vals in rows.items():
    vals.sort()
    alg_color = 'C0' if mode == 'tree' else 'C1'
    lang_label = lang.replace('_', ' ') if lang not in lang_used else '_'+lang
    alg_label = mode if mode not in alg_used else '_'+mode
    lang_used.add(lang)
    alg_used.add(mode)
    lang_color = 'C' + str(langs.index(lang))
    xs = [x[0] for x in vals]
    ys = [x[1] for x in vals]
    a_lang.plot(xs, ys, lang_color, label=lang_label)
    a_alg.plot(xs, ys, alg_color, label=alg_label)
a_lang.legend()
a_alg.legend()
plt.savefig('lin_trends.png')
