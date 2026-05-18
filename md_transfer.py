from flask import Flask, request, render_template, redirect
import cg3
from collections import Counter, defaultdict
import csv
import datetime
import io
import json
import os
import subprocess

app = Flask('manual_transfer')

os.makedirs('manual-dix/checkpoints', exist_ok=True)

target_features = ["Aspect", "Case", "Definite", "Degree", "ExtPos", "Gender", "Mood", "NumType", "Number", "Person", "Polarity", "Poss", "PronType", "Reflex", "Tense", "VerbForm", "Voice"]

with open('manual-dix/grc.bin', 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin, windows_only=True))

def PER_readings(window, with_features):
    for cohort in window.cohorts:
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            if with_features:
                ls = [reading.lemma, reading.tags[0]]
                for t in reading.tags:
                    if '=' in t and t.split('=')[0] in target_features:
                        ls.append(t)
                yield frozenset(ls)
            else:
                yield frozenset([reading.lemma, reading.tags[0]])
            break

target_readings = [(Counter(PER_readings(tw, False)),
                    Counter(PER_readings(tw, True)))
                   for tw in target]

current_source = None
current_per_sent = []
current_per_lemma = 100
current_per_form = 100

def frac(correct, deleted, words):
    return str(round(100 * (1 - float(correct - deleted)/words), 3))+'%'

def PER(source):
    swords = 0
    twords = 0
    lcorrect = 0
    fcorrect = 0
    ct = 0
    per_sentence = []
    for idx, (sw, tw) in enumerate(zip(source, target)):
        ct += 1
        swords += len(sw.cohorts)
        twords += len(tw.cohorts)
        sl = Counter(PER_readings(sw, False))
        lc = (sl & target_readings[idx][0]).total()
        lcorrect += lc
        sf = Counter(PER_readings(sw, True))
        fc = (sf & target_readings[idx][1]).total()
        fcorrect += fc
        dl = max(0, len(sw.cohorts) - len(tw.cohorts))
        per_sentence.append((frac(lc, dl, len(tw.cohorts)),
                             frac(fc, dl, len(tw.cohorts))))
    deletions = max(0, swords - twords)
    return (frac(lcorrect, deletions, twords),
            frac(fcorrect, deletions, twords),
            per_sentence)

def eval_current(save_checkpoint=False):
    global current_source, current_per_sent, current_per_lemma, current_per_form
    proc = subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                           '-g', 'manual-dix/current.cg3',
                           '-I', 'manual-dix/hbo.bin'],
                          capture_output=True)
    if proc.stderr:
        print("ERROR!!!!!!!!!!!")
        print(proc.stderr.decode('utf-8'))
    print('updating current_source')
    current_source = list(cg3.parse_binary_stream(io.BytesIO(proc.stdout),
                                                  windows_only=True))
    ret = PER(current_source)
    current_per_lemma, current_per_form, current_per_sent = ret
    if save_checkpoint:
        now = datetime.datetime.now()
        key = now.isoformat()
        with (open(f'manual-dix/checkpoints/{key}.cg3', 'w') as fout,
              open('manual-dix/current.cg3') as fin):
            fout.write(fin.read())
        with open('manual-dix/progress.csv', 'a') as fout:
            ls = [key, str(ret[0]), str(ret[1])]
            ls += ['%s,%s' % x for x in ret[2]]
            print(','.join(ls), file=fout)
    return ret

eval_current(not os.path.exists('manual-dix/progress.csv'))

def comp(old, new):
    if old == new:
        return new
    diff = float(new[:-1]) - float(old[:-1])
    if diff < 0:
        return '<ins>'+new+'</ins>'
    else:
        return '<del>'+new+'</ins>'

@app.route('/', methods=['GET'])
def main():
    eval_current()
    with open('manual-dix/progress.csv') as fin:
        lns = fin.read().strip().splitlines()
        first = lns[0].split(',')
        last = lns[-1].split(',')
        rows = [['total', first[1], first[2], last[1], last[2],
                 comp(last[1], current_per_lemma),
                 comp(last[2], current_per_form)]]
        all_cl = sorted(s[0] for s in current_per_sent)
        all_cf = sorted(s[1] for s in current_per_sent)
        for idx, (fl, ff, ll, lf, (cl, cf)) in enumerate(
                zip(first[3::2], first[4::2], last[3::2], last[4::2],
                    current_per_sent)):
            rows.append([f'<a href="/sentence/{idx}">{idx}</a>',
                         fl, ff, ll, lf,
                         comp(ll, cl), comp(lf, cf),
                         all_cl.index(cl), all_cf.index(cf)])
        return render_template('md_transfer.html', rows=rows,
                               first_cp=first[0], last_cp=last[0])

@app.route('/checkpoint', methods=['POST'])
def checkpoint():
    eval_current(save_checkpoint=True)
    return redirect('/')

def get_indexes(sw, tw, with_feats):
    sc = Counter()
    tc = Counter()
    sl = defaultdict(list)
    tl = defaultdict(list)
    for i, c in enumerate(PER_readings(sw, with_feats)):
        sl[c].append(i)
        sc[c] += 1
    for i, c in enumerate(PER_readings(tw, with_feats)):
        tl[c].append(i)
        tc[c] += 1
    sm = sc - tc
    tm = tc - sc
    sr = set()
    tr = set()
    for c in sm:
        sr.update(sl[c])
    for c in tm:
        tr.update(tl[c])
    return sr, tr

@app.route('/sentence/<int:idx>')
def view_sentence(idx):
    sw = current_source[idx]
    tw = target[idx]
    srl, trl = get_indexes(sw, tw, False)
    srf, trf = get_indexes(sw, tw, True)
    src = []
    for i, c in enumerate(sw.cohorts):
        k = ''
        if i in srl:
            k += ' <span class="error">lemma</span>'
        if i in srf:
            k += ' <span class="error">form</span>'
        src.append((c, k))
    tgt = []
    for i, c in enumerate(tw.cohorts):
        k = ''
        if i in trl:
            k += ' <span class="error">lemma</span>'
        if i in trf:
            k += ' <span class="error">form</span>'
        tgt.append((c, k))
    return render_template('md_transfer_sentence.html',
                           sent_id=idx, windows=[src, tgt])
