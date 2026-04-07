from flask import Flask, request, render_template
import json
import utils

app = Flask('md_review')

with open('manual-dix/initial-align.txt') as fin:
    alignments = fin.read().splitlines()

with open('manual-dix/maybe-skip.json') as fin:
    maybe_skip = json.loads(fin.read())

def get_sid(block):
    for line in block:
        if 'sent_id' in line:
            return line.split()[-1]

with open('manual-dix/hbo.conllu') as fin:
    hbo = [(list(utils.conllu_words(sent)), get_sid(sent))
           for sent in utils.conllu_sentences(fin)]

with open('manual-dix/grc.conllu') as fin:
    grc = [list(utils.conllu_words(sent))
           for sent in utils.conllu_sentences(fin)]

@app.route('/', methods=['GET', 'POST'])
def main():
    global maybe_skip
    if request.method == 'POST':
        row = []
        for key, val in request.values.items():
            if key[0] == 'w' and key[1:].isdigit() and val and val.isdigit():
                row.append((int(key[1:]), int(val)))
        row.sort()
        with open('manual-dix/align.txt', 'a') as fout:
            print(' '.join(f'{x}-{y}' for x, y in row), file=fout)
        if request.values.get('skip'):
            maybe_skip.append(int(request.values['sid']))
            with open('manual-dix/maybe-skip.json', 'w') as fout:
                fout.write(json.dumps(maybe_skip))
    N = 0
    with open('manual-dix/align.txt') as fin:
        N = len(fin.read().strip().splitlines())
    align = [''] * len(hbo[N][0])
    for pr in alignments[N].split():
        a, b = pr.split('-')
        align[int(a)] = b
    return render_template(
        'md_review.html',
        sid=N, hbo=hbo[N][0], sent_id=hbo[N][1], grc=grc[N], align=align)
