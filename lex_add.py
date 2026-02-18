import argparse
import cg3
import cg3_score
from collections import Counter, defaultdict
import io
import itertools
import json
import os
import sqlite3
import subprocess
import time
from tempfile import TemporaryDirectory

RULE_HEADER = 'DELIMITERS = "<$$$>" ;\nOPTIONS += addcohort-attach ;\n\n'

CG_BIN_HEADER = b'CGBF\x01\x00\x00\x00'
CG_BIN_FOOTER = b'\x02\x01\x02\x02' # FLUSH, EXIT

LEAF_POS = {'CCONJ', 'ADP', 'DET', 'PUNCT', 'INTJ', 'PART', 'AUX'}
UPOS_EXCLUDE = {'DET': 'VERB'}

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('lang')
parser.add_argument('iterations', type=int)
parser.add_argument('out')
parser.add_argument('--rule_count', type=int, default=100)
parser.add_argument('--lemma_count', type=int, default=100)
parser.add_argument('--append', action='store_true')
parser.add_argument('--max_sents', type=int, default=-1)
parser.add_argument('--skip_windows', action='store')
parser.add_argument('--max_tests', type=int, default=2)
parser.add_argument('--batch_size', type=int, default=100)
parser.add_argument('--out_dir', action='store')
parser.add_argument('--score_proc', action='store')
parser.add_argument('--threads', type=int, default=10)
args = parser.parse_args()

SKIP_WINDOWS = set()
if args.skip_windows:
    with open(args.skip_windows) as fin:
        SKIP_WINDOWS.update(json.loads(fin.read()))

def desc_r(reading):
    return reading.lemma + ' ' + reading.tags[0]

def count_lemmas(window):
    ret = Counter()
    for cohort in window.cohorts:
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            ret[desc_r(reading)] += 1
    return ret

target = []
target_blocks = []
target_counts = []
with open(args.target, 'rb') as fin:
    for i, block in enumerate(cg3_score.iter_blocks(fin.read())):
        if i == args.max_sents:
            break
        if i in SKIP_WINDOWS:
            continue
        target_blocks.append(block)
        window = cg3.parse_binary_window(block[5:])
        target.append(window)
        target_counts.append(count_lemmas(window))

def score_window(window_num, window):
    dct = count_lemmas(window)
    a, b = cg3_score.symmetric_difference(dct, target_counts[window_num])
    #ins = len([c for c in window.cohorts if c.static.lemma == '"<ins>"'])
    #return a + b + ins//2, dct
    return a + b, dct

source = []
source_blocks = []
lemma_index = defaultdict(list)
source_descs = []
priority = Counter()
source_counts = []
source_maps = []
base_scores = []

def reload_source(data, initial=False):
    global source, source_blocks, lemma_index, source_descs, priority, source_counts, source_maps, base_scores
    source = []
    source_blocks = []
    lemma_index = defaultdict(list)
    source_descs = []
    priority = Counter()
    source_counts = []
    base_scores = []
    for i, block in enumerate(cg3_score.iter_blocks(data)):
        if initial:
            if i == args.max_sents:
                break
            if i in SKIP_WINDOWS:
                continue
        if len(source) == len(target):
            break
        source_blocks.append(block)
        window = cg3.parse_binary_window(block[5:])
        cur = []
        for j, cohort in enumerate(window.cohorts):
            key = None
            rel = None
            pos = None
            count = 0
            for reading in cohort.readings:
                if reading.tags[0] == 'SOURCE':
                    key = reading.lemma + ' ' + reading.tags[1]
                    for tag in reading.tags:
                        if tag.startswith('LId[SDBH]='):
                            key += ' ' + tag
                        if tag.startswith('@'):
                            rel = tag
                else:
                    count += 1
                    pos = reading.tags[0]
            both = None
            if pos and rel:
                both = f'{pos} {rel}'
            #cur.append((pos, rel, both))
            cur.append((both,))
        source.append(window)
        source_descs.append(cur)
        s, c = score_window(len(source_counts), window)
        missing = target_counts[len(source_counts)] - c
        for key in missing:
            lemma_index[key].append(len(source_counts))
            priority[key] += missing[key]
        source_counts.append(c)
        base_scores.append(s)
    source_maps = [None] * len(source)

if args.append:
    proc = subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                           '-g', args.out, '-I', args.source],
                          capture_output=True, check=True)
    reload_source(proc.stdout, initial=True)
else:
    with open(args.source, 'rb') as fin:
        reload_source(fin.read(), initial=True)

def map_window(window_num):
    global source_maps
    if source_maps[window_num] is None:
        locs = {}
        parents = {}
        siblings = defaultdict(set)
        children = defaultdict(set)
        for i, ch in enumerate(source[window_num].cohorts):
            locs[ch.dep_self] = i
            parents[ch.dep_self] = ch.dep_parent
        for c, p in parents.items():
            children[p].add(c)
        for p, cs in children.items():
            for c in cs:
                siblings[c] = cs - {c}
        source_maps[window_num] = (locs, parents, siblings, children)
    return source_maps[window_num]

def get_context(window_num, cohort_num):
    window = source[window_num]
    locs, parents, siblings, children = map_window(window_num)
    target = window.cohorts[cohort_num].dep_self
    def desc_single(rel, wid):
        if wid in locs:
            options = source_descs[window_num][locs[wid]]
            for op in options:
                if op is not None:
                    yield f'({rel} ({op}))'
    def desc_link(tup):
        if len(tup) == 2:
            yield from desc_single(*tup)
        elif len(tup) == 4:
            for a in desc_single(tup[0], tup[1]):
                for b in desc_single(tup[2], tup[3]):
                    yield a[:-1] + ' LINK ' + b[1:]
    paths = []
    if parents[target] != 0:
        p = parents[target]
        paths.append(('p', p))
        if parents[p]:
            paths.append(('p', p, 'p', parents[p]))
        #for s in siblings[p]:
        #    paths.append(('p', p, 's', s))
    for s in siblings[target]:
        paths.append(('s', s))
        #for c in children[s]:
        #    paths.append(('s', s, 'c', c))
    for c in children[target]:
        paths.append(('c', c))
        for cc in children[c]:
            paths.append(('c', c, 'c', cc))
    for n in range(1, args.max_tests + 1):
        for seq in itertools.combinations(paths, n):
            yield from itertools.product(*[desc_link(p) for p in seq])

def gen_contexts(window_num):
    window = source[window_num]
    for cohort_num, cohort in enumerate(window.cohorts):
        upos = {r.tags[0] for r in cohort.readings} - {'SOURCE'}
        if upos & LEAF_POS:
            continue
        if not upos:
            continue
        upos = list(upos)[0]
        for ctx_ls in set(get_context(window_num, cohort_num)):
            ctx = ' '.join(ctx_ls)
            for t in source_descs[window_num][cohort_num]:
                if not t:
                    continue
                yield (window_num, upos, t, ctx)

def gen_rules_window(window_num, key):
    tpos = key.split()[-1]
    window = source[window_num]
    for cohort_num, cohort in enumerate(window.cohorts):
        upos = {r.tags[0] for r in cohort.readings} - {'SOURCE'}
        if upos & LEAF_POS:
            continue
        if tpos == 'DET' and 'VERB' in upos:
            continue
        for ctx_ls in set(get_context(window_num, cohort_num)):
            ctx = ' '.join(ctx_ls)
            for t in source_descs[window_num][cohort_num]:
                if not t:
                    continue
                yield f'ADDCOHORT ("<ins>" {key} @dep) BEFORE ({t}) IF (NEGATE c ({key})) {ctx} ;'

def score_rule(rpath, key, rule):
    with open(rpath, 'w') as fout:
        fout.write(RULE_HEADER + rule)
    #windows = lemma_index[key]
    windows = list(range(len(source_blocks)))
    inp = CG_BIN_HEADER + b''.join(source_blocks[i] for i in windows) + CG_BIN_FOOTER
    proc = subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                           '-g', rpath],
                          capture_output=True, input=inp)
    diff = 0
    actual_windows = set()
    for i, window in zip(windows,
                         cg3.parse_binary_stream(io.BytesIO(proc.stdout),
                                                 windows_only=True)):
        s, d = score_window(i, window)
        diff += s - base_scores[i]
        if s != base_scores[i]:
            actual_windows.add(i)
    return diff, actual_windows

CUR_SOURCE = None
CUR_TARGET = None

def start_rule(gpath, rule):
    with open(gpath, 'w') as fout:
        fout.write(RULE_HEADER + rule)
    return subprocess.Popen(
        [(args.score_proc or 'ch4_pipe_score/ch4_pipe_score'),
         gpath, CUR_SOURCE, CUR_TARGET, args.lang],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def finish_rule(proc):
    out, err = proc.communicate()
    return int(out.decode('utf-8').split()[1])

open_mode = 'a' if args.append else 'w'
with (TemporaryDirectory() as tmpdir_,
      open(args.out, open_mode) as rule_output):
    if args.append:
        rule_output.write('\n')
    else:
        rule_output.write(RULE_HEADER)

    tmpdir = args.out_dir or tmpdir_

    skip = set()

    con = sqlite3.connect(os.path.join(tmpdir, 'db.sqlite'))
    cur = con.cursor()
    cur.execute('CREATE TABLE context(window, upos, target, ctx)')
    #cur.execute('CREATE INDEX blah ON context(target, ctx)')
    con.commit()
    t0 = time.time()
    for w in range(len(source)):
        cur.executemany('INSERT INTO context VALUES(?, ?, ?, ?)',
                        gen_contexts(w))
    t1 = time.time()
    print('inserted in %.5f seconds' % (t1 - t0))
    cur.execute('CREATE INDEX blah ON context(upos, target, ctx)')
    t2 = time.time()
    print('indexed in %.5f seconds' % (t2 - t1))
    mx = 0
    if len(priority) > 1:
        mx = priority.most_common(1)[0][1]
    cur.execute('DELETE FROM context WHERE (upos, target, ctx) IN (SELECT upos, target, ctx FROM context GROUP BY upos, target, ctx HAVING COUNT(*) > ?)', (mx*2,))
    t3 = time.time()
    print('deleted in %.5f seconds' % (t3 - t2))
    cur.execute('CREATE TABLE freq AS SELECT upos, target, ctx, COUNT(*) as ct FROM context GROUP BY upos, target, ctx')
    cur.execute('CREATE INDEX blah2 ON freq(upos)')
    cur.execute('CREATE INDEX blah3 ON freq(ct)')
    t4 = time.time()
    print('flipped in %.5f seconds' % (t4 - t3))
    con.commit()
    print('\ncontexts entered')

    print('## 0:', sum(base_scores), file=rule_output)
    print('## 0:', sum(base_scores))
    print(priority.most_common(args.lemma_count))

    CUR_TARGET = os.path.join(tmpdir, 'target.bin')
    with open(CUR_TARGET, 'wb') as fout:
        fout.write(CG_BIN_HEADER + b''.join(target_blocks) + CG_BIN_FOOTER)

    shift = Counter()

    for iteration in range(args.iterations):
        CUR_SOURCE = os.path.join(tmpdir, f'input.{iteration}.bin')
        with open(CUR_SOURCE, 'wb') as fout:
            fout.write(CG_BIN_HEADER + b''.join(source_blocks) + CG_BIN_FOOTER)
        rules = []
        for key, count in priority.most_common(args.lemma_count):
            qs = ', '.join(['?']*len(lemma_index[key]))
            upos = key.split()[-1]
            t0 = time.time()
            mx = (count * 2) >> shift[key]
            cur.execute(f'SELECT target, ctx, ct FROM freq f WHERE upos IS NOT ? AND EXISTS (SELECT * FROM context c WHERE c.target = f.target AND c.ctx = f.ctx AND c.window IN ({qs})) AND ct <= ? ORDER BY ct DESC LIMIT ?', (UPOS_EXCLUDE.get(upos, 'UNK'), *lemma_index[key], mx, args.rule_count))
            shift[key] += 1
            for t, c, ct in cur.fetchall():
                rules.append((ct, key, f'ADDCOHORT ("<ins>" {key} @dep) BEFORE ({t}) IF (NEGATE c ({key})) {c} ;'))
            print('queried %s in %.5f seconds' % (key, time.time() - t0))
        scored_rules = []
        threshold = sum(base_scores)
        for batch in itertools.batched(enumerate(rules), args.threads):
            procs = []
            for i, (c, k, r) in batch:
                path = os.path.join(tmpdir, f'g_{iteration}_{i}.cg3')
                procs.append(start_rule(path, r))
            for (i, (c, k, r)), p in zip(batch, procs):
                s = finish_rule(p)
                print(i, s, r)
                if s < threshold:
                    scored_rules.append((s, i, r, k))
        scored_rules.sort()
        used_keys = set()
        selected = []
        for d, i, r, k in scored_rules:
            if k in used_keys:
                continue
            print(r, file=rule_output)
            selected.append(r)
            used_keys.add(k)
            shift[k] = 0
        if selected:
            update = os.path.join(tmpdir, f'g_{iteration}.cg3')
            with open(update, 'w') as fout:
                fout.write(RULE_HEADER + '\n'.join(selected))
            proc = subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                                   '-g', update],
                                  capture_output=True, check=True,
                                  input=(CG_BIN_HEADER +
                                         b''.join(source_blocks) +
                                         CG_BIN_FOOTER))
            reload_source(proc.stdout)
        print(f'## {iteration+1}:', sum(base_scores), file=rule_output)
        print(f'## {iteration+1}:', sum(base_scores))
        print(priority.most_common(args.lemma_count))
        if not selected:
            break
