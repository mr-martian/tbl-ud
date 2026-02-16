import argparse
import cg3
import cg3_score
from collections import Counter, defaultdict
import io
import itertools
import json
import os
import subprocess
import time
from tempfile import TemporaryDirectory

RULE_HEADER = 'DELIMITERS = "<$$$>" ;\nPROTECT (SOURCE) ;\n\n'

CG_BIN_HEADER = b'CGBF\x01\x00\x00\x00'
CG_BIN_FOOTER = b'\x02\x01\x02\x02' # FLUSH, EXIT

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
    return a + b, dct

source = []
source_blocks = []
lemma_index = defaultdict(list)
source_lemmas = []
ambiguity = Counter()
source_counts = []
source_maps = []
base_scores = []

def reload_source(data, initial=False):
    global source, source_blocks, lemma_index, source_lemmas, ambiguity, source_counts, source_maps, base_scores
    source = []
    source_blocks = []
    if initial:
        lemma_index = defaultdict(list)
        source_lemmas = []
        source_maps = []
    ambiguity = Counter()
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
            if initial:
                cur.append((key, rel))
                lemma_index[key].append((len(source), j))
            ambiguity[key] += (count - 1)
        source.append(window)
        if initial:
            source_lemmas.append(cur)
        s, c = score_window(len(source_counts), window)
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
            options = source_lemmas[window_num][locs[wid]]
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
        for s in siblings[p]:
            paths.append(('p', p, 's', s))
    for s in siblings[target]:
        paths.append(('s', s))
        for c in children[s]:
            paths.append(('s', s, 'c', c))
    for c in children[target]:
        paths.append(('c', c))
        for cc in children[c]:
            paths.append(('c', c, 'c', cc))
    for n in range(1, args.max_tests + 1):
        for seq in itertools.combinations(paths, n):
            yield from itertools.product(*[desc_link(p) for p in seq])

def gen_rules_window(window_num, cohort_num):
    src = source_counts[window_num]
    tgt = target_counts[window_num]
    cohort = source[window_num].cohorts[cohort_num]
    if len(cohort.readings) < 3:
        return []
    drop = []
    for reading in cohort.readings:
        if 'SOURCE' in reading.tags:
            continue
        key = desc_r(reading)
        if src[key] > tgt[key]:
            drop.append(key)
    for ctx_ls in get_context(window_num, cohort_num):
        ctx = ' '.join(ctx_ls)
        for t in source_lemmas[window_num][cohort_num]:
            if t is None:
                continue
            if '"' not in t:
                continue
            for key in drop:
                yield f'REMOVE ({key}) IF (0 ({t})) (0 (*) - (SOURCE) - ({key})) {ctx} ;'

def score_rule(rpath, key, rule):
    with open(rpath, 'w') as fout:
        fout.write(RULE_HEADER + rule)
    windows = sorted(set([x[0] for x in lemma_index[key]]))
    inp = CG_BIN_HEADER + b''.join(source_blocks[i] for i in windows) + CG_BIN_FOOTER
    proc = subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                           '-g', rpath],
                          capture_output=True, input=inp)
    diff = 0
    for i, window in zip(windows,
                         cg3.parse_binary_stream(io.BytesIO(proc.stdout),
                                                 windows_only=True)):
        s, d = score_window(i, window)
        diff += s - base_scores[i]
    return diff, set(windows)

def start_rule(prefix, rule):
    gpath = prefix + '.cg3'
    spath = prefix + '.input.bin'
    tpath = prefix + '.output.bin'
    with open(gpath, 'w') as fout:
        fout.write(RULE_HEADER + rule)
    with open(spath, 'wb') as fout:
        fout.write(CG_BIN_HEADER + b''.join(source_blocks) + CG_BIN_FOOTER)
    with open(tpath, 'wb') as fout:
        fout.write(CG_BIN_HEADER + b''.join(target_blocks) + CG_BIN_FOOTER)
    return subprocess.Popen(['ch4_pipe_score/ch4_pipe_score', gpath, spath, tpath,
                             args.lang],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

def finish_rule(proc):
    out, err = proc.communicate()
    return int(out.decode('utf-8').split()[1])

open_mode = 'a' if args.append else 'w'
with (TemporaryDirectory() as tmpdir,
      open(args.out, open_mode) as rule_output):
    if args.append:
        rule_output.write('\n')
    else:
        rule_output.write(RULE_HEADER)

    print('## 0:', sum(base_scores), file=rule_output)
    print('## 0:', sum(base_scores))

    for iteration in range(args.iterations):
        freq = Counter()
        for key, count in ambiguity.most_common(args.lemma_count):
            print(key, count)
            t0 = time.time()
            ct = Counter()
            for batch in itertools.batched(lemma_index[key], args.batch_size):
                bct = Counter()
                for w, c in batch:
                    bct.update(gen_rules_window(w, c))
                ct.update(dict(bct.most_common(args.rule_count * 2)))
            freq.update(dict(((key, r), c)
                             for r, c in ct.most_common(args.rule_count)))
            print('\tfinished', key, 'in %.3f seconds' % (time.time() - t0))
        scored_rules = []
        threshold = sum(base_scores)
        for batch in itertools.batched(enumerate(freq.most_common(args.rule_count)), args.threads):
            procs = []
            for i, ((k, r), c) in batch:
                prefix = os.path.join(tmpdir, f'g_{iteration}_{i}')
                procs.append(start_rule(prefix, r))
            for (i, ((k, r), c)), proc in zip(batch, procs):
                s = finish_rule(proc)
                print(i, s, r)
                if s < threshold:
                    scored_rules.append((s, i, r,
                                         set([x[0]
                                              for x in lemma_index[k]])))
        scored_rules.sort()
        used = set()
        selected = []
        for d, i, r, w in scored_rules:
            if w & used:
                continue
            print(r, file=rule_output)
            selected.append(r)
            used |= w
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
        if not selected:
            break
