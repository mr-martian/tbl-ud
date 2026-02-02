import argparse
import random
import utils

parser = argparse.ArgumentParser()
parser.add_argument('in_file')
parser.add_argument('out_file')
parser.add_argument('relabel_prob', type=float)
parser.add_argument('detach_prob', type=float)
args = parser.parse_args()

RELS = ['acl', 'acl:relcl', 'advcl', 'advcl:relcl', 'advmod', 'advmod:emph', 'advmod:lmod', 'amod', 'appos', 'aux', 'aux:pass', 'case', 'cc', 'cc:preconj', 'ccomp', 'clf', 'compound', 'compound:lvc', 'compound:prt', 'compound:redup', 'compound:svc', 'conj', 'cop', 'csubj', 'csubj:outer', 'csubj:pass', 'dep', 'det', 'det:numgov', 'det:nummod', 'det:poss', 'discourse', 'dislocated', 'expl', 'expl:impers', 'expl:pass', 'expl:pv', 'fixed', 'flat', 'flat:foreign', 'flat:name', 'goeswith', 'iobj', 'list', 'mark', 'nmod', 'nmod:poss', 'nmod:tmod', 'nsubj', 'nsubj:outer', 'nsubj:pass', 'nummod', 'nummod:gov', 'obj', 'obl', 'obl:agent', 'obl:arg', 'obl:lmod', 'obl:tmod', 'orphan', 'parataxis', 'punct', 'reparandum', 'vocative', 'xcomp']

with open(args.in_file) as fin, open(args.out_file, 'w') as fout:
    for index, sent in enumerate(utils.conllu_sentences(fin), 1):
        print(f'# sent_id = s{index}', file=fout)
        for word in utils.conllu_words(sent):
            roll = random.random()
            if roll < args.relabel_prob and word[7] != 'root':
                if roll < args.detach_prob:
                    word[6] = '_'
                    word[7] = '_'
                else:
                    word[7] = random.choice(RELS)
            print('\t'.join(word), file=fout)
        print('', file=fout)
