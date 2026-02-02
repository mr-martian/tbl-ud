from cg3 import parse_binary_stream as parse_cg3

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

RTYPES = ['grandparent', 'sibling', 'child', 'relation']
RULE_HEADER = '''
DELIMITERS = "<$$$>" ;
LIST Relation = /^@.*$/r ;

'''.lstrip()
LEAF_POS = ['CCONJ', 'ADP', 'DET', 'PUNCT', 'INTJ', 'PART', 'AUX']

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('iterations', type=int)
parser.add_argument('out')
parser.add_argument('--count', type=int, default=25,
                    help='number of templates to expand')
parser.add_argument('--ctx', type=int, default=2,
                    help='max context tests')
parser.add_argument('--beam', type=int, default=25,
                    help='max instantiations of a single pattern')
parser.add_argument('--rule_count', type=int, default=25,
                    help='number of rules to try')
parser.add_argument('--context_similarity', type=float, default=0.9,
                    help='threshold for discarding more complex context as equivalent')
parser.add_argument('--append', action='store_true',
                    help='retain any rules already present in output file')
parser.add_argument('--max_sents', type=int, default=0,
                    help='use only first N sentences')
parser.add_argument('--skip_windows', action='store',
                    help='skip windows with indecies in this JSON list')
parser.add_argument('--rtypes', action='store',
                    help='only generate certain rule types')
args = parser.parse_args()

EXCLUDE = set()
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

def get_heads(window):
    heads = {}
    index = {0: -1}
    rels = []
    for i, c in enumerate(window.cohorts):
        heads[c.dep_self] = c.dep_parent
        index[c.dep_self] = i
        rels.append(get_rel(c))
    return (heads, index, rels)

def get_path(wid, heads, index):
    if wid == 0:
        return [-1]
    else:
        return [index[wid]] + get_path(heads[wid], heads, index)

with open(args.target, 'rb') as fin:
    target = list(parse_cg3(fin, windows_only=True))
    if args.max_sents > 0:
        target = target[:args.max_sents]
target_heads = [get_heads(w) for w in target]

def gen_rules(window, slw, tlw):
    if window in SKIP_WINDOWS:
        return []
    rules = []
    src_heads, src_index, src_rels = get_heads(slw)
    tgt_heads, tgt_index, tgt_rels = target_heads[window]
    descs = [None] * len(slw.cohorts)
    for i, (sc, tc) in enumerate(zip(slw.cohorts, tlw.cohorts)):
        sid = sc.dep_self
        tid = tc.dep_self
        sh = sc.dep_parent
        th = tc.dep_parent
        srel = src_rels[i]
        trel = tgt_rels[i]
        if descs[i] is None:
            descs[i] = desc_c(sc)
        suf = (window, i, descs[i])
        if srel != trel:
            rules.append(('relation', srel, trel, None, '')+suf)
        if src_index[sh] != tgt_index[th]:
            if th == 0:
                ch = 0
            else:
                ch = slw.cohorts[tgt_index[th]].dep_self
            sp = get_path(sid, src_heads, src_index)
            cp = get_path(ch, src_heads, src_index)
            if sp[0] in cp:
                n = cp[cp.index(sp[0]) - 1]
                if descs[n] is None:
                    descs[n] = desc_c(slw.cohorts[n])
                rules.append(('child', '', '', n, descs[n])+suf)
            elif sp[1] in cp:
                n = cp[cp.index(sp[1]) - 1]
                if descs[n] is None:
                    descs[n] = desc_c(slw.cohorts[n])
                rules.append(('sibing', '', '', n, descs[n])+suf)
            else:
                rules.append(('grandparent', '', '', None, '')+suf)
    def error_key(row):
        return '-'.join(str(row[k]) for k in [0, 1, 2, 4, 7])
    return [r for r in rules if error_key(r) not in EXCLUDE]

def format_rule(rtype, target, tags=None, desttags=None, ctarget=None,
                context=None):
    ctx = ' '.join(f'({test})' for test in sorted(context))
    if rtype == 'relation':
        return f'SUBSTITUTE ({tags}) ({desttags}) (*) IF (0 {target}) {ctx} ;'
    elif rtype == 'child':
        return f'WITH {target} (c {ctarget}) {ctx} {{\n\tSWITCHPARENT WITHCHILD (*) _C2_ ;\n\tSUBSTITUTE Relation $$Relation _C2_ IF (jC1 $$Relation) ;\n}} ;'
    elif rtype == 'sibling':
        return f'SETPARENT (*) (0 {target}) {ctx} TO (s {ctarget}) ;'
    elif rtype == 'grandparent':
        return f'SETPARENT (*) (0 {target}) {ctx} TO (p (*) LINK p (*)) ;'

def format_relation(rtype, target, ctarget, context):
    ret = []
    ret.append(f'ADDRELATION (tr{{NUM}}) (*) (0 {target}) TO (0 (*)) ;')
    if ctarget:
        sel = 's' if rtype == 'sibling' else 'c'
        ret.append(f'ADDRELATION (ct{{NUM}}) (*) (0 {target}) TO ({sel} {ctarget})')
    for test in context:
        ret.append(f'ADDRELATION (r{{NUM}}) (*) (0 {target}) TO (A{test}) ;')
    # TODO: NEGATE
    return '\n'.join(ret)

def describe_cohort(cohort, window):
    rel = get_rel(cohort) or ''
    prel = ''
    cpos = set()
    for c in window.cohorts:
        if c.dep_self == cohort.dep_parent:
            prel = get_rel(c)
        elif c.dep_parent == cohort.dep_self:
            for r in c.readings:
                t = r.tags[0]
                if t == 'SOURCE':
                    t = r.tags[1]
                if t in LEAF_POS:
                    cpos.add(t)
    for rd in cohort.readings:
        tag = rd.tags[0]
        if tag == 'SOURCE':
            tag += ' ' + rd.tags[1]
        yield f'({tag} {rel})'
        yield f'({rd.lemma} {tag} {rel})'
        for feat in rd.tags:
            if '=' in feat:
                yield f'({tag} {rel} {feat})'
                yield f'({rd.lemma} {tag} {rel} {feat})'
        for cp in cpos:
            yield f'({tag} {rel}) LINK c ({cp})'
            yield f'({rd.lemma} {tag} {rel}) LINK c ({cp})'
        if prel:
            yield f'({tag} {rel}) LINK p ({prel})'
            yield f'({rd.lemma} {tag} {rel}) LINK p ({prel})'

def collect_neighbors(slw, idx, dct):
    ds = slw.cohorts[idx].dep_self
    dh = slw.cohorts[idx].dep_parent
    for cohort in slw.cohorts:
        if cohort.dep_self == dh:
            dct['p'].add(cohort.dep_self)
        elif cohort.dep_self == ds:
            dct['t'].add(cohort.dep_self)
        elif cohort.dep_parent == dh:
            dct['s'].add(cohort.dep_self)
        elif cohort.dep_parent == ds:
            dct['c'].add(cohort.dep_self)

def select_contexts(cur, dct, rtype):
    RANGE = 10
    ret = defaultdict(Counter)
    for rel in dct:
        cs = list(dct[rel])
        qs = ', '.join(['?']*len(cs))
        cur.execute(
            f'SELECT cohort, pattern FROM tests WHERE cohort IN ({qs})',
            cs)
        d2 = defaultdict(set)
        c2 = Counter()
        # shorter tests first
        for c, p in sorted(cur.fetchall(), key=lambda r: len(r[1])):
            if rel == 't' and 'LINK' in p:
                continue
            d2[p].add(c)
            c2[p] += 1
        ls = c2.most_common()
        for i in range(len(ls)):
            pattern, count = ls[i]
            # stop when we get to comparatively low frequency tests
            if count < ls[0][1] / 10:
                break
            # only consider the last RANGE options, rather than all
            # => most similarly sized
            for j in range(max(i-RANGE, 0), i):
                pj = ls[j][0]
                comp = len(d2[pattern].intersection(d2[pj])) / count
                #print(pattern, count, pj, ls[j][1], comp)
                if comp >= args.context_similarity:
                    break
            else:
                ret[rel][pattern] = count
    return ret

def rel_ranges():
    for n in range(1, args.ctx+1):
        for i_p in range(2):
            for i_s in range(n-i_p+1):
                yield i_p, i_s, (n-i_p-i_s)

def contextualize_rules(contexts, dct, ekey):
    ct = args.count >> 2
    cp = [(f'p {k}',v) for k,v in contexts['p'].most_common(ct)]
    cs = [(f's {k}',v) for k,v in contexts['s'].most_common(ct)]
    cs += [(f'NEGATE s {k}',v) for k,v in contexts['negs'].most_common(ct)]
    cc = [(f'c {k}',v) for k,v in contexts['c'].most_common(ct)]
    cc += [(f'NEGATE c {k}',v) for k,v in contexts['negc'].most_common(ct)]
    targets = contexts['t'].most_common(ct)
    ctargets = contexts['ct'].most_common(ct) or [(None, targets[0][1])]
    for i_p, i_s, i_c in rel_ranges():
        for t_p in combinations(cp, i_p):
            for t_s in combinations(cs, i_s):
                for t_c in combinations(cc, i_c):
                    seq = t_p + t_s + t_c
                    ctx = tuple([s[0] for s in seq])
                    count = min(s[1] for s in seq)
                    for tgc, tgi in targets:
                        for ctgc, ctgi in ctargets:
                            yield (dct['rtype'],
                                   format_rule(target=tgc, ctarget=ctgc,
                                               context=ctx, **dct),
                                   format_relation(dct['rtype'], tgc, ctgc,
                                                   ctx),
                                   min(count, tgi, ctgi),
                                   ekey)

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
    src_heads, src_index, src_rels = get_heads(slw)
    tgt_heads, tgt_index, tgt_rels = target_heads[index]
    for i, (sc, tc) in enumerate(zip(slw.cohorts, tlw.cohorts)):
        if src_rels[i] != tgt_rels[i]:
            score += 1
        if src_index[sc.dep_parent] != tgt_index[tc.dep_parent]:
            sp = get_path(sc.dep_self, src_heads, src_index)
            tp = get_path(tc.dep_self, tgt_heads, tgt_index)
            while sp and tp and sp[-1] == tp[-1]:
                sp.pop()
                tp.pop()
            score += len(sp) + len(tp) - 2
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
    db_path = os.path.join(tmpdir, 'db.sqlite')
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('CREATE TABLE errors(rule, tags1, tags2, ctarget, ctarget_key, window, cohort, cohort_key)')
    cur.execute('CREATE TABLE context(rtype, rule TEXT, relation TEXT, count INT, error_label TEXT)')
    cur.execute('CREATE TABLE tests(cohort INTEGER, pattern TEXT)')
    con.commit()
    rule_output.write(initial_rule_output)

    def log_scores(iteration, src_path):
        global target, rule_output, EXCLUDE
        update_source(src_path)
        rule_output.write('####################\n')
        rule_output.write(f'## {iteration}: {base_score}\n')
        rule_output.write('####################\n')
        print(f'{iteration=}, {base_score=}, {len(EXCLUDE)=}')

    for iteration in range(args.iterations):
        src_path = os.path.join(tmpdir, f'output.{iteration}.bin')
        if iteration == 0:
            src_path = initial_source
        log_scores(iteration, src_path)
        tgt_path = os.path.join(tmpdir, f'output.{iteration+1}.bin')

        for table in ['errors', 'context', 'tests']:
            cur.execute(f'DELETE FROM {table}')
        con.commit()

        for window, (slw, tlw) in enumerate(zip(source, target)):
            if window in SKIP_WINDOWS:
                continue
            cur.executemany(
                'INSERT INTO errors VALUES(?, ?, ?, ?, ?, ?, ?, ?)',
                gen_rules(window, slw, tlw))
            for ch in slw.cohorts:
                cur.executemany(
                    'INSERT INTO tests(cohort, pattern) VALUES(?, ?)',
                    [(ch.dep_self, dc) for dc in describe_cohort(ch, slw)])
            con.commit()

        patterns = []
        for rt in RTYPES:
            cur.execute('SELECT COUNT(*) AS ct, rule, tags1, tags2, cohort_key, ctarget_key FROM errors WHERE rule = ? GROUP BY rule, tags1, tags2, cohort_key, ctarget_key ORDER BY ct DESC LIMIT ?', (rt, args.count))
            patterns += cur.fetchall()

        for count, rule, tags1, tags2, ckey, ctkey in patterns:
            label = f'{rule}-{tags1}-{tags2}-{ckey}-{ctkey}'
            cur.execute('SELECT window, cohort, ctarget FROM errors WHERE rule = ? AND tags1 = ? AND tags2 = ? AND cohort_key = ? AND ctarget_key = ?',
                        (rule, tags1, tags2, ckey, ctkey))
            neighbors = defaultdict(set)
            for wnum, cnum, ctnum in cur.fetchall():
                slw = source[wnum]
                if ctnum is not None:
                    neighbors['ct'].add(slw.cohorts[ctnum].dep_self)
                collect_neighbors(slw, cnum, neighbors)
            dct = select_contexts(cur, neighbors, rule)
            rules = list(contextualize_rules(
                dct,
                {'rtype': rule, 'tags': tags1, 'desttags': tags2},
                label))
            rules.sort(key=lambda x: x[3], reverse=True)
            cur.executemany('INSERT INTO context VALUES(?, ?, ?, ?, ?)',
                            rules[:args.beam])
            con.commit()

        failed_errors = set()
        non_failed = set()
        rules = []
        for rt in RTYPES:
            cur.execute('SELECT count, rule, relation, error_label FROM context WHERE rtype = ? ORDER BY count LIMIT ?', (rt, args.rule_count))
            rules += cur.fetchall()

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
                non_failed.add(rule[-1])
            else:
                failed_errors.add(rule[-1])
        scored_rules.sort()
        added = set()
        selected_rules = []
        for score, rule, i in scored_rules:
            if intersections[i] & added:
                continue
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

print(json.dumps({
    'max_mem_kb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'time_sec': time.time() - START,
}), file=sys.stderr)
