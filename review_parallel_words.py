from flask import Flask, request, render_template
import json
import collections
import itertools

app = Flask('review')

with open('possible.json') as fin:
    possible = json.load(fin)

with open('actual.json') as fin:
    actual = json.load(fin)

word_map = collections.defaultdict(set)
rev_map = collections.defaultdict(set)
for row in actual:
    word_map[(row['sl'], row['su'])].add((row['tl'], row['tu']))
    rev_map[(row['tl'], row['tu'])].add((row['sl'], row['su']))

todo = set()

def reset_todo():
    global todo
    todo = set()
    for i, sent in enumerate(possible):
        all_src = set((row['lemma'], row['upos']) for row in sent['src'])
        all_tgt = set((row['lemma'], row['upos']) for row in sent['tgt'])
        null = {(None, None)}
        if any((all_src|null).isdisjoint(rev_map[t]) for t in all_tgt):
            todo.add(i)
        elif any((all_tgt|null).isdisjoint(word_map[s]) for s in all_src):
            todo.add(i)
reset_todo()

@app.route('/', methods=['GET', 'POST'])
def main():
    if request.method == 'POST':
        if request.values.get('sl'):
            word_map[(request.values['sl'], request.values['su'])].add(
                (request.values.get('tl'), request.values.get('tu')))
        if request.values.get('tl'):
            rev_map[(request.values['tl'], request.values['tu'])].add(
                (request.values.get('sl'), request.values.get('su')))
    idx = request.values.get('index')
    if idx is None:
        idx = 1
    else:
        idx = int(idx)
    sentence = possible[sorted(todo)[idx-1]]
    words = []
    all_src = set((row['lemma'], row['upos']) for row in sentence['src'])
    all_tgt = set((row['lemma'], row['upos']) for row in sentence['tgt'])
    for src in sentence['src']:
        exist = False
        blob = {'src': src, 'tgt': []}
        prev = word_map[(src['lemma'], src['upos'])]
        for tgt in sentence['tgt']:
            key = (tgt['lemma'], tgt['upos'])
            have = (key in prev)
            revhave = not rev_map[key].isdisjoint(all_src)
            exist = exist or have
            blob['tgt'].append({'linked': have, **tgt,
                                'revlinked': revhave})
        blob['linked'] = exist
        blob['nulllink'] = ((None, None) in prev)
        words.append(blob)
    return render_template(
        'review.html',
        sid=sentence['sid'], words=words,
        idx=idx, prev=(idx-1 if idx > 1 else None),
        next=(idx+1 if idx < len(possible) else None),
        total=len(possible), len_todo=len(todo),
        unaligned=[t for t in all_tgt if rev_map[t].isdisjoint(all_src|{(None,None)})],
    )

@app.route('/save')
def save():
    with open('actual.json', 'w') as fout:
        fout.write(json.dumps([{'sl': k[0], 'su': k[1],
                                'tl': t[0], 'tu': t[1]}
                               for k, v in word_map.items()
                               for t in sorted(v, key=str)]))
    reset_todo()
    return ''
