import argparse
import json
import matplotlib.pyplot as plt
import os

parser = argparse.ArgumentParser()
parser.add_argument('per_lem', type=float)
parser.add_argument('per_form', type=float)
parser.add_argument('out')
parser.add_argument('grammars', nargs='+')
args = parser.parse_args()

fig, (a_lem, a_form) = plt.subplots(2)
a_lem.set(ylabel='PER_lemma')
a_form.set(xlabel='Sentence', ylabel='PER_form')
lv = []
fv = []
grams = []
for grammar in args.grammars:
    with open(grammar) as fin:
        blob = json.loads(fin.read())
        x = blob['x']
        yl = blob['y_lem']
        yf = blob['y_form']
        a_lem.plot(x, yl, 'tab:blue')
        a_form.plot(x, yf, 'tab:blue')
        lv.append(yl[-1])
        fv.append(yf[-1])
        grams.append((os.path.basename(grammar), yl[-1], yf[-1]))
a_lem.axhline(args.per_lem, color='tab:orange')
a_form.axhline(args.per_form, color='tab:orange')
plt.savefig(args.out, bbox_inches='tight', pad_inches=0.1)
print(f'{args.per_lem:.2f} & {args.per_form:.2f} & {min(lv):.2f} & {min(fv):.2f}')
grams.sort(key=lambda x: x[1])
print('%s\t%0.2f\t%0.2f' % grams[0])
grams.sort(key=lambda x: x[2])
print('%s\t%0.2f\t%0.2f' % grams[0])
