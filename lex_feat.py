import argparse
import cg3
import cg3_score
from collections import Counter, defaultdict
import io
import itertools
import json
import os
import subprocess
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
parser.add_argument('--pos_count', type=int, default=20)
parser.add_argument('--append', action='store_true')
parser.add_argument('--max_sents', type=int, default=-1)
parser.add_argument('--skip_windows', action='store')
parser.add_argument('--max_tests', type=int, default=2)
parser.add_argument('--batch_size', type=int, default=20)
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

FEATS = {
    'blx': {"Adjz", "Aspect", "Caus", "Degree", "Emph", "Loc", "Mood", "Nmlz", "NumType", "Number", "Pluraction", "Polarity", "Poss", "Redup", "Voice"},
    'eng': {"Animacy", "Case", "Definite", "Degree", "Gender", "LexCat", "Mood", "Number", "NumType", "Person", "PronType", "Tense", "VerbForm"},
    'grc': {"Aspect", "Case", "Definite", "Degree", "Gender", "Mood", "NumType", "Number", "Person", "Polarity", "Poss", "PronType", "Reflex", "Tense", "VerbForm", "Voice"},
}

for f in sorted(FEATS.get(args.lang, set())):
    RULE_HEADER += f'LIST {f} = /^{f}=.*$/r ;\n'
RULE_HEADER += '\n'

def get_feats(reading):
    for t in reading.tags:
        if '=' in t:
            f = t.split('=')[0]
            if f in FEATS.get(args.lang, set()):
                yield t

def count_lemmas(window):
    ret = Counter()
    for cohort in window.cohorts:
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            d = desc_r(reading)
            for t in get_feats(reading):
                ret[(d, t)] += 1
    return ret

def count_lemmas_gen(window):
    ret = defaultdict(lambda: defaultdict(Counter))
    for cohort in window.cohorts:
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            d = desc_r(reading)
            for t in get_feats(reading):
                ret[d][t.split('=')[0]][t] += 1
    return ret

target = []
target_blocks = []
target_counts = []
target_counts_gen = []
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
        target_counts_gen.append(count_lemmas_gen(window))

def score_window(window_num, window):
    dct = count_lemmas(window)
    a, b = cg3_score.symmetric_difference(dct, target_counts[window_num])
    return a + b, dct

source = []
source_blocks = []
source_lemmas = []
source_counts = []
source_counts_gen = []
source_maps = []
base_scores = []

def reload_source(data, initial=False):
    global source, source_blocks, source_lemmas, source_counts, source_counts_gen, source_maps, base_scores
    source = []
    source_blocks = []
    source_lemmas = []
    source_counts = []
    source_counts_gen = []
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
        source_counts_gen.append(count_lemmas_gen(window))
        s, c = score_window(len(source_counts), window)
        source_counts.append(c)
        base_scores.append(s)
        diff = c - target_counts[len(source_counts)-1]
        source.append(window)
        cur = []
        for cohort in window.cohorts:
            upos = set()
            rel = None
            feats = set()
            for reading in cohort.readings:
                if reading.tags[0] == 'SOURCE':
                    continue
                upos.add(reading.tags[0])
                feats.update(get_feats(reading))
                if rel is None:
                    for t in reading.tags:
                        if t[0] == '@':
                            rel = t
                            break
            cur.append((upos, rel, feats))
        source_lemmas.append(cur)
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

def get_context(window_num, cohort_num, feat):
    window = source[window_num]
    locs, parents, siblings, children = map_window(window_num)
    target = window.cohorts[cohort_num].dep_self
    def desc_single(rel, wid, with_feat):
        if wid in locs:
            upos, deprel, feats = source_lemmas[window_num][locs[wid]]
            for u in upos:
                yield f'({rel} ({u} {deprel}))'
            if with_feat:
                for f in feats:
                    if f.startswith(feat):
                        for u in upos:
                            yield f'({rel} ({u} {deprel} {f}))'
    def desc_link(tup):
        if len(tup) == 2:
            yield from desc_single(*tup, True)
        elif len(tup) == 4:
            for a in desc_single(tup[0], tup[1], True):
                for b in desc_single(tup[2], tup[3], False):
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
    ps = set()
    for p in paths:
        ps.update(desc_link(p))
    paths = sorted(ps)
    for n in range(1, args.max_tests + 1):
        for seq in itertools.combinations(paths, n):
            yield ' '.join(seq)

def gen_rules_window(window_num):
    src = source_counts_gen[window_num]
    tgt = target_counts_gen[window_num]
    for cohort_num, cohort in enumerate(source[window_num].cohorts):
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            dr = desc_r(reading)
            have = set(reading.tags)
            if dr not in tgt:
                continue
            for f in set(src[dr].keys()) | set(tgt[dr].keys()):
                missing = set((tgt[dr][f] - src[dr][f]).keys())
                extra = set((src[dr][f] - tgt[dr][f]).keys())
                remove = extra & have
                add = missing - have
                pairs = []
                if not remove:
                    pairs += [('*', t) for t in add]
                if not add:
                    pairs += [(t, '*') for t in remove]
                for a in add:
                    for r in remove:
                        pairs.append((r, a))
                t = source_lemmas[window_num][cohort_num]
                for ctx in get_context(window_num, cohort_num, f):
                    if '=' not in ctx:
                        continue
                    for u in t[0]:
                        ts0 = f'({u} {t[1]})'
                        for t1, t2 in pairs:
                            if t2 != '*' and t2 not in ctx:
                                continue
                            ts = ts0
                            if t1 == '*':
                                ts += ' - ' + f
                            yield (f'SUBSTITUTE ({t1}) ({t2}) {ts} IF {ctx} ;', (ts0, f))

CUR_SOURCE = None
CUR_TARGET = None

def start_rule(gpath, rule):
    with open(gpath, 'w') as fout:
        fout.write(RULE_HEADER + rule)
    return subprocess.Popen(
        [(args.score_proc or 'ch4_pipe_score/ch4_pipe_score'),
         gpath, CUR_SOURCE, CUR_TARGET, args.lang, '--count-feats'],
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

    tmpdir = tmpdir_
    if args.out_dir:
        tmpdir = args.out_dir

    print('## 0:', sum(base_scores), file=rule_output)
    print('## 0:', sum(base_scores))

    CUR_TARGET = os.path.join(tmpdir, 'target.bin')
    with open(CUR_TARGET, 'wb') as fout:
        fout.write(CG_BIN_HEADER + b''.join(target_blocks) + CG_BIN_FOOTER)

    skip_next = set()
    skip_count = Counter()
    skip_entirely = set()

    for iteration in range(args.iterations):
        CUR_SOURCE = os.path.join(tmpdir, f'input.{iteration}.bin')
        with open(CUR_SOURCE, 'wb') as fout:
            fout.write(CG_BIN_HEADER + b''.join(source_blocks) + CG_BIN_FOOTER)
        rule_counter = defaultdict(Counter)
        pos_counter = Counter()
        for batch in itertools.batched(range(len(source)), args.batch_size):
            pct = Counter()
            rct = defaultdict(Counter)
            for window_num in batch:
                for r, p in gen_rules_window(window_num):
                    if p in skip_entirely or p in skip_next:
                        continue
                    pct[p] += 1
                    rct[p][r] += 1
            for p, _ in pct.most_common(args.pos_count * 2):
                mc = rct[p].most_common(args.rule_count * 2)
                mc = mc[(skip_count[p]*(args.rule_count>>1)):]
                ct = Counter(dict(mc))
                rule_counter[p].update(ct)
                pos_counter[p] += ct.total()
        rules = []
        tested_keys = set()
        for p, _ in pos_counter.most_common(args.pos_count):
            rules += [(r, p, c) for r, c in
                      rule_counter[p].most_common(args.rule_count)]
        scored_rules = []
        threshold = sum(base_scores)
        for batch in itertools.batched(enumerate(rules), args.threads):
            procs = []
            for i, (r, k, c) in batch:
                path = os.path.join(tmpdir, f'g_{iteration}_{i}.cg3')
                procs.append(start_rule(path, r))
            for (i, (r, k, c)), p in zip(batch, procs):
                s = finish_rule(p)
                print(i, s, r)
                if s < threshold:
                    scored_rules.append((s, i, r, k))
        scored_rules.sort()
        used = set()
        selected = []
        for s, i, r, k in scored_rules:
            if k in used:
                continue
            print(r, file=rule_output)
            selected.append(r)
            used.add(k)
        skip_next = tested_keys - used
        for k in skip_next:
            skip_count[k] += 1
            if skip_count[k] >= 3:
                skip_entirely.add(k)
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
