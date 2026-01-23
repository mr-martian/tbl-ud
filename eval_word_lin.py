import argparse
import matplotlib.pyplot as plt
from nltk.metrics import edit_distance
import train_word_lin as twl

parser = argparse.ArgumentParser()
parser.add_argument('rule_file')
parser.add_argument('train_src', help='bin')
parser.add_argument('train_tgt', help='conllu')
parser.add_argument('dev_src', help='bin')
parser.add_argument('dev_tgt', help='conllu')
parser.add_argument('graph')
args = parser.parse_args()

orig_rules = twl.parse_rule_file(args.rule_file, to_global=False)

train = twl.Trainer()
train.load_corpus(args.train_src, args.train_tgt)
dev = twl.Trainer()
dev.load_corpus(args.dev_src, args.dev_tgt)

def eval_corpus(corpus):
    max_loss = 0
    actual_loss = 0
    total_wer = 0
    norm_wer = 0
    num_words = 0
    for sent in corpus.corpus:
        cohorts = len(sent.source.cohorts)
        max_loss += (cohorts * (cohorts - 1)) / 2
        actual_loss += len(list(sent.wrong_pairs()))
        sw = [sent.source_words[n].lemma for n in sent.wl.sequence]
        tw = [w.lemma for w in sent.target]
        wer = edit_distance(sw, tw)
        total_wer += wer
        num_words += cohorts
        norm_wer += float(wer) / cohorts
    return (100.0 * actual_loss / max_loss,
            100.0 * total_wer / num_words,
            100.0 * norm_wer / len(corpus.corpus))

train_log = []
dev_log = []
def eval_both(idx):
    global train_log, dev_log
    t = eval_corpus(train)
    d = eval_corpus(dev)
    train_log.append(t)
    dev_log.append(d)
    print('%5d: Train Loss %3.2f Micro-WER %3.2f Macro-WER %3.2f Test Loss %3.2f Micro-WER %3.2f Macro-WER %3.2f' % (idx, *t, *d))
    if idx == len(orig_rules):
        print('& %d & %.2f\\%% & %.2f\\%% & %.2f\\%% \\\\' % (idx, *d))

for rule_idx in range(len(orig_rules)):
    eval_both(rule_idx)
    for sent in train.corpus + dev.corpus:
        sent.wl.add_rule(orig_rules[rule_idx], rule_idx)
    twl.ALL_RULES.append(orig_rules[rule_idx])

eval_both(len(orig_rules))

axs = plt.subplot(ylabel='WER and Normalized Loss', xlabel='Iterations')
axs.set_ylim(ymin=0, ymax=100)
axs.plot([t[0] for t in train_log], label='Train loss')
axs.plot([t[1] for t in train_log], label='Train Micro-WER')
axs.plot([t[2] for t in train_log], label='Train Macro-WER')
axs.plot([t[0] for t in dev_log], label='Dev loss')
axs.plot([t[1] for t in dev_log], label='Dev Micro-WER')
axs.plot([t[2] for t in dev_log], label='Dev Macro-WER')
axs.legend()
plt.savefig(args.graph)
