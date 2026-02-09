import argparse
import subprocess
import tempfile
import utils

parser = argparse.ArgumentParser()
parser.add_argument('src')
parser.add_argument('tgt')
parser.add_argument('out')
args = parser.parse_args()

with (open(args.src) as fin1,
      open(args.tgt) as fin2,
      open(args.out+'.words', 'w') as fout):
    for src, tgt in zip(utils.conllu_sentences(fin1),
                        utils.conllu_sentences(fin2)):
        swords = [w[2] for w in utils.conllu_words(src)]
        twords = [w[2] for w in utils.conllu_words(tgt)]
        print(' '.join(swords), '|||', ' '.join(twords), file=fout)
subprocess.run(['eflomal-align', '-i', args.out+'.words',
                '--overwrite', '-f', args.out])
