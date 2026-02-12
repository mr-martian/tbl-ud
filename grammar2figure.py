import argparse
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('train')
parser.add_argument('--dev', action='store')
parser.add_argument('--test', action='store')
args = parser.parse_args()

axs = plt.subplot(ylabel='PER and Normalized Loss', xlabel='Iterations')
axs.set_ylim(ymin=0, ymax=100)

with open(args.train) as fin:
    vals = []
    for line in fin:
        if line.startswith('## '):
            ls = line.split()
            vals.append((int(ls[2]), float(ls[4][:-1]), float(ls[6][:-1])))
    axs.plot([100.0*y[0]/vals[0][0] for y in vals], label='loss')
    axs.plot([y[1] for y in vals], label='PER of lemmas (train)')
    axs.plot([y[2] for y in vals], label='PER of forms (train)')

try:
    with open(args.train + '.dev.log') as fin:
        xs = []
        ylem = []
        yform = []
        for line in fin:
            ls = line.split()
            if len(ls) == 3:
                xs.append(int(ls[0]))
                ylem.append(float(ls[1]))
                yform.append(float(ls[2]))
        axs.plot(xs, ylem, label='PER of lemmas (dev)')
        axs.plot(xs, yform, label='PER of forms (dev)')
except FileNotFoundError:
    pass

axs.legend()

plt.savefig(args.train + '.png')
