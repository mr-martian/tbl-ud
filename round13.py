from cg3 import parse_binary_stream as parse_cg3
from metrics import PER

import argparse
from collections import Counter, defaultdict
import io
from itertools import combinations
import json
import os
import resource
import sqlite3
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory, NamedTemporaryFile
import time

START = time.time()

RTYPES = [
    'remove',
    'replace',
    'addcohort',
    'remcohort',
    'func2feat',
    'feat2func',
    'feat-from-func',
    'agreement',
    'add-feat',
]
RULE_HEADER = '''
OPTIONS += addcohort-attach ;
DELIMITERS = "<$$$>" ;
PROTECT (SOURCE) ;
LIST UPOS = ADJ ADP ADV AUX CCONJ DET INTJ NOUN NUM PART PRON PROPN PUNCT SCONJ SYM VERB X UNK ;


'''.lstrip()
LEAF_POS = ['CCONJ', 'ADP', 'DET', 'PUNCT', 'INTJ', 'PART', 'AUX']

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('iterations', type=int)
parser.add_argument('out')
parser.add_argument('--weights', action='store', default='{}')
parser.add_argument('--count', type=int, default=25,
                    help='number of rules to test per iteration')
parser.add_argument('--append', action='store_true',
                    help='retain any rules already present in output file')
parser.add_argument('--max_sents', type=int, default=0,
                    help='use only first N sentences')
parser.add_argument('--target_feats', action='store',
                    help='skip removing features not in this JSON list')
parser.add_argument('--skip_windows', action='store',
                    help='skip windows with indecies in this JSON list')
parser.add_argument('--score_report', action='store_true',
                    help='print the contribution of each factor to the final error score')
parser.add_argument('--rtypes', action='store',
                    help='only generate certain rule types')
args = parser.parse_args()

WEIGHTS = defaultdict(lambda: 1, json.loads(args.weights))
EXCLUDE = set()
TARGET_FEATS = None
if args.target_feats:
    with open(args.target_feats) as fin:
        TARGET_FEATS = set(json.loads(fin.read()))
SKIP_WINDOWS = set()
if args.skip_windows:
    with open(args.skip_windows) as fin:
        SKIP_WINDOWS = set(json.loads(fin.read()))
if args.rtypes:
    RTYPES = json.loads(args.rtypes)

def desc_r(reading):
    ret = reading.lemma
    for t in reading.tags:
        if t != 'SOURCE':
            ret += ' ' + t
            break
    return ret
def desc_c(cohort):
    for r in cohort.readings:
        if 'SOURCE' in r.tags:
            return desc_r(r)
    return desc_r(cohort.readings[0])

def get_rel(cohort):
    for r in cohort.readings:
        for t in r.tags:
            if t[0] == '@':
                return t

def tags_to_feature_dict(tags, dct=None):
    if dct is None:
        dct = defaultdict(Counter)
    for t in tags:
        if '=' in t:
            k, v = t.split('=', 1)
            if TARGET_FEATS is not None and k not in TARGET_FEATS:
                continue
            dct[k][v] += 1
    return dct

def collect_words_and_feats(window):
    words = Counter()
    feats = defaultdict(lambda: defaultdict(Counter))
    for c in window.cohorts:
        for r in c.readings:
            if 'SOURCE' in r.tags:
                continue
            d = desc_r(r)
            words[d] += 1
            tags_to_feature_dict(r.tags, feats[d])
    return words, feats

with open(args.target, 'rb') as fin:
    target = list(parse_cg3(fin, windows_only=True))
    if args.max_sents > 0:
        target = target[:args.max_sents]
target_words_and_feats = [collect_words_and_feats(w) for w in target]

def format_rule(rtype, target, ctx, tag1, tag2):
    if rtype == 'remove':
        return f'REMOVE ({tag1}) IF (0 ({target})) ({ctx}) ;'
    elif rtype == 'replace':
        return f'''
WITH ({target}) IF ({ctx}) {{
    SELECT ({tag1}) ;
    SUBSTITUTE ({tag1}) ({tag2}) (*) ;
}} ;
        '''.strip()
    elif rtype == 'addcohort':
        return f'ADDCOHORT ("<ins>" {tag1} @dep) BEFORE (*) IF (0 ({target})) (NEGATE c ({tag1})) ({ctx}) ;'
    elif rtype == 'remcohort':
        return f'REMCOHORT (*) IF (0 ({target})) ({ctx}) ;'
    # tag1 is category, tag2 is value
    elif rtype == 'func2feat':
        return f'''
WITH ({target}) IF (w{ctx} LINK NEGATE c (*)) {{
    SUBSTITUTE (/^{tag1}=.*$/r) (*) (*) ;
    SUBSTITUTE (*) ({tag2}) (*) ;
    REMCOHORT _C1_ ;
}} ;
        '''.strip()
    elif rtype == 'feat2func':
        return f'''
WITH ({target} {tag2}) IF ({ctx}) (NEGATE c ({tag1})) {{
    SUBSTITUTE ({tag2}) (*) (*) ;
    ADDCOHORT ("<ins>" {tag1} @dep) BEFORE (*) ;
}} ;
        '''.strip()
    elif rtype == 'feat-from-func':
        return f'''
WITH ({target}) - ({tag2}) IF ({ctx}) {{
    SUBSTITUTE (/^{tag1}=.*$/r) (*) (*) ;
    SUBSTITUTE (*) ({tag2}) (*) ;
}} ;
        '''.strip()
    elif rtype == 'agreement':
        return f'''
LIST {tag1} = /^({tag1}=.*)$/r ;
WITH ({target}) IF ({ctx} + {tag1}) {{
    SUBSTITUTE {tag1} (*) (*) ;
    SUBSTITUTE (*) (VSTR:$1) (*) IF (jC1 {tag1}) ;
}} ;
        '''.strip()
    elif rtype == 'add-feat':
        return f'SUBSTITUTE (*) ({tag2}) ({target}) - (/^{tag1}=.*$/r) ;'

def format_relation(target, ctx):
    if ctx:
        return f'''
ADDRELATION (tr{{NUM}}) (*) (0 ({target})) TO (0 (*)) ;
ADDRELATION (r{{NUM}}) (*) (0 ({target})) TO ({ctx}) ;
        '''.strip()
    else:
        return f'ADDRELATION (tr{{NUM}}) (*) (0 ({target})) TO (0 (*)) ;'

def source_lex(cohort):
    for r in cohort.readings:
        if 'SOURCE' in r.tags:
            ls = [r.lemma]
            ls.append(([t for t in r.tags if t != 'SOURCE' and '=' not in t]
                       or ['UNK'])[0])
            for t in r.tags:
                if t.startswith('LId[SDBH]='):
                    ls.append(t)
                    break
            return ' '.join(ls)

def gen_rules(window, slw, tlw):
    if window in SKIP_WINDOWS:
        return
    src_words, src_feats = collect_words_and_feats(slw)
    tgt_words, tgt_feats = target_words_and_feats[window]
    extra = +(src_words - tgt_words)
    missing = +(tgt_words - src_words)
    dep2idx = {}
    all_extra = set()
    deletable = set()
    word_lists = []
    source_desc = []
    lexical_desc = []
    rels = []
    for idx, cohort in enumerate(slw.cohorts):
        dep2idx[cohort.dep_self] = idx
        word_lists.append([desc_r(r) for r in cohort.readings
                           if 'SOURCE' not in r.tags])
        if all(w in extra for w in word_lists[-1]):
            all_extra.add(idx)
            if all(c.dep_parent != cohort.dep_self for c in slw.cohorts):
                deletable.add(idx)
        source_desc.append(source_lex(cohort))
        lexical_desc.append(source_desc[-1] or desc_c(cohort))
        rels.append(get_rel(cohort))
    def lexical_context(cohort):
        for i, c in enumerate(slw.cohorts):
            if c.dep_self == cohort.dep_parent:
                yield f'p ({lexical_desc[i]})'
            elif c.dep_parent == cohort.dep_self:
                yield f'c ({lexical_desc[i]})'
            elif c.dep_parent == cohort.dep_parent and c.dep_self != cohort.dep_self:
                yield f's ({lexical_desc[i]})'
    def context_with_feat(cohort, feat):
        for i, c in enumerate(slw.cohorts):
            rel = None
            if c.dep_self == cohort.dep_parent:
                rel = 'p'
            elif c.dep_parent == cohort.dep_self:
                rel = 'c'
            else:
                continue
            if any(feat in r.tags and 'SOURCE' not in r.tags
                   for r in c.readings):
                yield i, f'{rel} ({rels[i]})'
    # don't insert words if we're already very imbalanced
    not_overload = (len(slw.cohorts) < len(tlw.cohorts) + 5)
    for idx, cohort in enumerate(slw.cohorts):
        lctx = list(lexical_context(cohort))
        if len(word_lists[idx]) > 1:
            for w in word_lists[idx]:
                for lc in lctx:
                    yield ('remove', lexical_desc[idx], lc, w, None)
        if idx in all_extra:
            for w in missing:
                for lc in lctx:
                    yield ('replace', lexical_desc[idx], lc,
                           word_lists[idx][0], w)
            if idx in deletable:
                for lc in lctx:
                    yield ('remcohort', lexical_desc[idx], lc,
                           None, None)
        can_insert = (not_overload and not any(l in lexical_desc[idx] for l in LEAF_POS))
        if can_insert:
            for m in missing:
                for lc in lctx:
                    yield ('addcohort', lexical_desc[idx], lc, m, None)
        for reading in cohort.readings:
            if 'SOURCE' in reading.tags:
                continue
            d = desc_r(reading)
            role_desc = reading.tags[0] + ' ' + rels[idx]
            scount = src_words[d]
            tcount = tgt_words[d]
            if tcount == 0:
                continue
            rf = dict([t.split('=', 1) for t in reading.tags if '=' in t])
            sf = src_feats[d]
            tf = tgt_feats[d]
            for k, v in rf.items():
                if sf[k][v] <= tf[k][v]:
                    continue
                st = sf[k].total()
                tt = tf[k].total()
                if can_insert:
                    for m in missing:
                        for lc in lctx: # TODO: ???
                            yield ('feat2func', lexical_desc[idx], lc,
                                   m, f'{k}={v}')
                for v2 in tf[k]:
                    if v != v2 and sf[k][v2] < tf[k][v2]:
                        feat = f'{k}={v2}'
                        for i, c in context_with_feat(cohort, feat):
                            if i in deletable:
                                yield ('func2feat', lexical_desc[idx],
                                       c, k, feat)
                            yield ('feat-from-func', lexical_desc[idx],
                                   c, k, feat)
                            yield ('feat-from-func', role_desc, c, k, feat)
                            yield ('agreement', lexical_desc[idx],
                                   c, k, feat)
                            yield ('agreement', role_desc, c, k, feat)
            for k in tf:
                if k in rf:
                    continue
                diff = +(tf[k] - sf[k])
                for v in diff:
                    feat = f'{k}={v}'
                    for i, c in context_with_feat(cohort, feat):
                        yield ('agreement', lexical_desc[idx], c, k, feat)
                    yield ('add-feat', reading.tags[0], None, k, feat)
                    for alt in reading.tags:
                        if '=' in alt:
                            yield ('add-feat', reading.tags[0] + ' ' + alt,
                                   None, k, feat)

def run_grammar(ipath, gpath, opath):
    try:
        subprocess.run(['vislcg3', '--in-binary', '--out-binary', '-g',
                        gpath, '-I', ipath, '-O', opath],
                       capture_output=True, check=True)
    except subprocess.CalledProcessError:
        with open(gpath) as fin:
            print(fin.read())
        raise
    with open(opath, 'rb') as fout:
        yield from parse_cg3(fout, windows_only=True)

CG_BIN_HEADER = b'CGBF\x01\x00\x00\x00'
CG_BIN_FOOTER = b'\x02\x01\x02\x02' # FLUSH, EXIT
def run_windows(gpath, windows):
    inp = CG_BIN_HEADER + b''.join(source_blocks[i] for i in windows) + CG_BIN_FOOTER
    proc = subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                           '-g', gpath],
                          capture_output=True, check=True, input=inp)
    yield from parse_cg3(io.BytesIO(proc.stdout), windows_only=True)

def calc_intersection(rules: list, ipath, gpath: str, opath: str):
    if not rules:
        return [], {}
    with open(gpath, 'w') as fout:
        for i, r in enumerate(rules):
            fout.write(r[2].replace('{NUM}', str(i)) + '\n')
    target_windows = defaultdict(set)
    targets = defaultdict(set)
    contexts = defaultdict(set)
    for idx, window in enumerate(run_grammar(ipath, gpath, opath)):
        if idx in SKIP_WINDOWS or idx >= len(target):
            continue
        for cohort in window.cohorts:
            for tag, heads in cohort.relations.items():
                if tag[0] == 'r' and tag[1:].isdigit():
                    contexts[int(tag[1:])].update(heads)
                elif tag.startswith('tr') and tag[2:].isdigit():
                    targets[int(tag[2:])].add(cohort.dep_self)
                    target_windows[int(tag[2:])].add(idx)
    intersections = [set() for i in range(len(rules))]
    for i in range(len(rules)):
        if not contexts[i]:
            continue
        for j in range(i):
            if (targets[i] & targets[j]
                or targets[i] & contexts[j]
                or targets[j] & contexts[i]):
                intersections[i].add(j)
                intersections[j].add(i)
    return intersections, {k: sorted(v) for k, v in target_windows.items()}

def score_window(slw, tlw, index):
    if index in SKIP_WINDOWS:
        return 0
    score = 0
    score += WEIGHTS['cohorts'] * abs(len(slw.cohorts) - len(tlw.cohorts))
    src_words, src_feats = collect_words_and_feats(slw)
    tgt_words, tgt_feats = target_words_and_feats[index]
    extra = src_words - tgt_words
    missing = tgt_words - src_words
    score += WEIGHTS['missing'] * missing.total()
    score += WEIGHTS['extra'] * extra.total()
    score += WEIGHTS['ambig'] * (src_words.total() - len(slw.cohorts))
    score += WEIGHTS['ins'] * len([s for s in slw.cohorts if s.static.lemma == '"<ins>"'])
    score += WEIGHTS['unk'] * sum([ct for lm, ct in src_words.items()
                                   if lm.startswith('"@')])
    mf = 0
    ef = 0
    for k1 in set(src_feats.keys()) | set(tgt_feats.keys()):
        for k2 in set(src_feats[k1].keys()) | set(tgt_feats[k1].keys()):
            ef += (src_feats[k1][k2] - tgt_feats[k1][k2]).total()
            mf += (tgt_feats[k1][k2] - src_feats[k1][k2]).total()
    score += WEIGHTS['missing_feats'] * mf
    score += WEIGHTS['extra_feats'] * ef
    return score

source = []
source_blocks = []
window_scores = []
base_score = 0
def update_source(fname):
    global source, source_blocks, window_scores, base_score
    with open(fname, 'rb') as fin:
        source = list(parse_cg3(fin, windows_only=True))
        source_blocks = []
        fin.seek(8)
        block = fin.read()
        pos = 0
        for i in range(len(source)):
            while block[pos] != 1:
                if block[pos] == 2:
                    pos += 2
                elif block[pos] == 3:
                    ln = struct.unpack('<I', block[pos+1:pos+5])[0]
                    pos += ln + 3
            ln = struct.unpack('<I', block[pos+1:pos+5])[0]
            source_blocks.append(block[pos:pos+ln+5])
            pos += ln + 5
    window_scores = [score_window(s, t, i) for i, (s, t) in enumerate(zip(source, target))]
    base_score = sum(window_scores)
update_source(args.source)
print(f'{len(source)=}, {len(target)=}')

def score_rule(rule, gpath, windows):
    with open(gpath, 'w') as fout:
        fout.write(RULE_HEADER + rule[1])
    score = 0
    last_window = 0
    for idx, slw in zip(windows, run_windows(gpath, windows)):
        score += sum(window_scores[last_window:idx])
        score += score_window(slw, target[idx], idx)
        last_window = idx+1
    score += sum(window_scores[last_window:])
    return score

initial_rule_output = RULE_HEADER
initial_source = args.source
if args.append:
    with open(args.out) as fin:
        initial_rule_output = fin.read().strip() + '\n\n'
        if not initial_rule_output.startswith(RULE_HEADER):
            initial_rule_output = RULE_HEADER + initial_rule_output
    new_source = NamedTemporaryFile(delete=False, delete_on_close=False)
    initial_source = new_source.name
    subprocess.run(['vislcg3', '--in-binary', '--out-binary', '-g',
                    args.out, '-I', args.source, '-O', new_source.name],
                   capture_output=True)
    update_source(new_source.name)

with (TemporaryDirectory() as tmpdir,
      open(args.out, 'w') as rule_output):
    rule_output.write(initial_rule_output)

    def log_scores(iteration, src_path):
        global target, rule_output, EXCLUDE
        update_source(src_path)
        base_per = PER(source, target, TARGET_FEATS)
        rule_output.write('####################\n')
        rule_output.write(f'## {iteration}: {base_score} PER_lem {base_per[0]:.2f}% PER_form {base_per[1]:.2f}%\n')
        rule_output.write('####################\n')
        print(f'{iteration=}, {base_score=}, {len(EXCLUDE)=} PER_lem {base_per[0]:.2f}% PER_form {base_per[1]:.2f}%')

    for iteration in range(args.iterations):
        src_path = os.path.join(tmpdir, f'output.{iteration}.bin')
        if iteration == 0:
            src_path = initial_source
        log_scores(iteration, src_path)
        tgt_path = os.path.join(tmpdir, f'output.{iteration+1}.bin')

        potential_rules = defaultdict(Counter)

        for window, (slw, tlw) in enumerate(zip(source, target)):
            if window in SKIP_WINDOWS:
                continue
            for rule in gen_rules(window, slw, tlw):
                if rule in EXCLUDE:
                    continue
                potential_rules[rule[0]][rule] += 1

        failed_errors = set()
        non_failed = set()
        rules = []
        for rt in RTYPES:
            for r, _ in potential_rules[rt].most_common(args.count):
                rules.append((r, format_rule(*r),
                              format_relation(r[1], r[2])))

        gpath = os.path.join(tmpdir, f'intersection.{iteration}.cg3')
        opath = os.path.join(tmpdir, f'intersection.{iteration}.bin')
        intersections, target_windows = calc_intersection(
            rules, src_path, gpath, opath)

        scored_rules = []
        for rule_idx, rule in enumerate(rules):
            gpath = os.path.join(tmpdir, f'g{rule_idx:05}.cg3')
            s = score_rule(rule, gpath, target_windows[rule_idx])
            print(s, rule[1])
            if s < base_score:
                scored_rules.append((s, rule, rule_idx))
                non_failed.add(rule[0])
            else:
                failed_errors.add(rule[0])
        scored_rules.sort()
        added = set()
        new_words = set()
        selected_rules = []
        for score, rule, i in scored_rules:
            if intersections[i] & added:
                continue
            if rule[1][0] == 'A':
                key = rule[1].split(')')[0]
                if key in new_words:
                    continue
                new_words.add(key)
            selected_rules.append(rule)
            added.add(i)

        gpath = os.path.join(tmpdir, f'grammar.{iteration}.cg3')
        rule_str = '\n'.join(r[1] for r in selected_rules)
        with open(gpath, 'w') as fout:
            fout.write(RULE_HEADER + rule_str)
        rule_output.write(rule_str + '\n\n')
        EXCLUDE.update(failed_errors - non_failed)
        subprocess.run(['vislcg3', '--in-binary', '--out-binary', '-g',
                        gpath, '-I', src_path, '-O', tgt_path],
                       capture_output=True)
    # log final values after all iterations
    log_scores(args.iterations, tgt_path)

if args.score_report:
    factors = ['cohorts', 'missing', 'extra', 'ambig', 'ins', 'unk',
               'missing_feats', 'extra_feats']
    scores = []
    for f in factors:
        WEIGHTS = {fn: 0 for fn in factors}
        WEIGHTS[f] = 1
        scores.append(sum(score_window(s, t, i)
                          for i, (s, t) in enumerate(zip(source, target))))
    total = sum(scores)
    for f, s in zip(factors, scores):
        p = (100.0 * s) / total
        print(f, s, f'{p:0.2f}%')

print(json.dumps({
    'max_mem_kb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'time_sec': time.time() - START,
}), file=sys.stderr)
