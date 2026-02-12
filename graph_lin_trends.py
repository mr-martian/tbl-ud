import matplotlib.pyplot as plt
import glob
from collections import defaultdict

axs = plt.subplot(ylabel='WER', xlabel='Rules per Iteration')
#axs.set_ylim(ymin=0, ymax=100)

rows = defaultdict(list)

def to_list(s):
    return [x.strip() for x in s.replace('\\', '').replace('%', '').split('&')]

for lang in ['Welsh', 'North_Sami', 'KhoekhoeLLL', 'Ancient_Greek', 'Ancient_Hebrew']:
    for fname in glob.glob(f'lin-exp-data/UD_{lang}*.log'):
        if 'short' in fname:
            continue
        if 'long' in fname:
            continue
        if 'mid' in fname:
            continue
        print(fname)
        ls = fname.split('.')
        key = (lang.replace('_', ' '), ls[1], ls[3])
        count = int(ls[2])
        with open(fname) as fin:
            for line in fin:
                if '&' in line:
                    ls = to_list(line)
                    rows[key].append((count, float(ls[-2]), float(ls[-1])))

for (lang, _, mode), vals in rows.items():
    vals.sort()
    #colors = ('r', 'g') if mode == 'tree' else ('b', 'tab:purple')
    colors = ('C0', 'C0') if mode == 'tree' else ('C1', 'C1')
    axs.plot([x[0] for x in vals], [x[1] for x in vals], colors[0])
    #axs.plot([x[0] for x in vals], [x[2] for x in vals], colors[1])
plt.savefig('lin_trends.png')
