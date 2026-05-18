import argparse
import cg3
import utils

parser = argparse.ArgumentParser()
parser.add_argument('data')
parser.add_argument('skip')
args = parser.parse_args()

skip = utils.load_json_set(args.skip)

words = 0
sents = 0
with open(args.data, 'rb') as fin:
    for i, w in enumerate(cg3.parse_binary_stream(fin, windows_only=True)):
        if i in skip: continue
        sents += 1
        words += len(w.cohorts)
print(f'Sentences: {sents}, Words: {words}')