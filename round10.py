from cg3 import parse_binary_stream as parse_cg3

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
import os
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

RTYPES = ['remove', 'append', 'addcohort', 'rem-self',
          #'rem-parent'
          ]
RULE_HEADER = '''
OPTIONS += addcohort-attach ;
DELIMITERS = "<$$$>" ;
PROTECT (SOURCE) ;


'''

parser = argparse.ArgumentParser()
parser.add_argument('source')
parser.add_argument('target')
parser.add_argument('iterations', type=int)
parser.add_argument('out')
parser.add_argument('--weights', action='store', default='{}')
parser.add_argument('--count', type=int, default=25,
                    help='number of templates to expand')
parser.add_argument('--ctx', type=int, default=2,
                    help='max context tests')
parser.add_argument('--beam', type=int, default=25,
                    help='max instantiations of a single pattern')
parser.add_argument('--rule_count', type=int, default=25,
                    help='number of rules to try')
args = parser.parse_args()

WEIGHTS = defaultdict(lambda: 1, json.loads(args.weights))
EXCLUDE = set()

with open(args.target, 'rb') as fin:
    target = list(parse_cg3(fin, windows_only=True))

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

def gen_rules(window, slw, tlw):
    LEAF_POS = ['CCONJ', 'ADP', 'DET', 'PUNCT', 'INTJ', 'PART', 'AUX']
    rules = []
    src_words = Counter(desc_r(r) for c in slw.cohorts for r in c.readings if 'SOURCE' not in r.tags)
    tgt_words = Counter(desc_r(r) for c in tlw.cohorts for r in c.readings if 'SOURCE' not in r.tags)
    extra = +(src_words - tgt_words)
    missing = +(tgt_words - src_words)
    for idx, cohort in enumerate(slw.cohorts):
        suf = (window, idx, desc_c(cohort))
        inserting = not any(l in suf[2] for l in LEAF_POS)
        words = [desc_r(r) for r in cohort.readings if 'SOURCE' not in r.tags]
        if all(w in extra for w in words):
            children = [(i, desc_c(c)) for i, c in enumerate(slw.cohorts)
                        if c.dep_parent == cohort.dep_self]
            if children:
                for ch in children:
                    rules.append(('rem-parent', '', '', window)+ch)
            else:
                rules.append(('rem-self', '', '')+suf)
            if inserting:
                for m in missing:
                    if 'PUNCT' in m:
                        if not (cohort.static.lemma == '<ins>' in suf[2] or 'PUNCT' in suf[2]):
                            continue
                    rules.append(('append', m, '')+suf)
            else:
                for m in missing:
                    if any(l in m and l in suf[2] for l in LEAF_POS):
                        rules.append(('append', m, '')+suf)
        if len(words) > 1:
            for w in words:
                if w in extra:
                    rules.append(('remove', w, '')+suf)
        if inserting:
            for m in missing:
                rules.append(('addcohort', m, '')+suf)
        # TODO: SUBSTITUTE
    def error_key(row):
        return '-'.join(row[k] for k in [0, 1, 2, 5])
    return [r for r in rules if error_key(r) not in EXCLUDE]

def format_rule(rtype, target, tags=None, desttags=None, context=None):
    ls = []
    if rtype == 'rem-parent':
        ls = [c for c in context if c[0] == 'p'] + sorted(
            [c for c in context if c[0] != 'p'])
    else:
        ls = sorted(context or [])
    ctx = ' '.join(f'({test})' for test in ls)
    if rtype == 'remove':
        return f'REMOVE ({tags}) IF (0 ({target})) {ctx} ;'
    elif rtype == 'append':
        return f'APPEND ({tags}) (*) IF (0 ({target})) {ctx} ;'
    elif rtype == 'addcohort':
        return f'ADDCOHORT ("<ins>" {tags} @dep) BEFORE (*) IF (0 ({target})) (NEGATE c ({tags})) {ctx} ;'
    elif rtype == 'rem-self':
        return f'REMCOHORT (*) IF (0 ({target})) (NEGATE c (*)) {ctx} ;'
    elif rtype == 'rem-parent':
        return f'WITH (*) IF (0 ({target})) {ctx} {{\n\tSWITCHPARENT WITHCHILD (*) (*) ;\n\tREMCOHORT _C2_ ;\n}} ;'

    elif rtype == 'SUBSTITUTE':
        return f'SUBSTITUTE ({tags}) ({desttags}) (*) IF (0 ({target})) {ctx} ;'

def format_relation(target, context):
    ret = []
    ret.append(f'ADDRELATION (tr{{NUM}}) (*) (0 ({target})) TO (0 (*)) ;')
    for test in context:
        ret.append(f'ADDRELATION (r{{NUM}}) (*) (0 ({target})) TO ({test}) ;')
    # TODO: NEGATE
    return '\n'.join(ret)

def get_rel(cohort):
    for r in cohort.readings:
        for t in r.tags:
            if t[0] == '@':
                return t

def describe_cohort(cohort):
    rel = get_rel(cohort) or ''
    for rd in cohort.readings:
        tag = rd.tags[0]
        if tag == 'SOURCE':
            tag += ' ' + rd.tags[1]
        yield f'{tag} {rel}'
        yield f'{rd.lemma} {tag} {rel}'
        # TODO: features

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

def select_contexts(cur, dct):
    RANGE = 5
    SIMILARITY = 0.9
    ret = defaultdict(Counter)
    for rel in dct:
        cs = list(dct[rel])
        qs = ', '.join(['?']*len(cs))
        cur.execute(
            f'SELECT cohort, pattern FROM tests WHERE cohort IN ({qs})',
            cs)
        d2 = defaultdict(set)
        c2 = Counter()
        for c, p in cur.fetchall():
            d2[p].add(c)
            c2[p] += 1
        ls = c2.most_common()
        for i in range(len(ls)):
            pattern, count = ls[i]
            for j in range(max(i-RANGE, 0), i):
                pj = ls[j][0]
                if len(d2[pattern].intersection(d2[pj])) / count >= SIMILARITY:
                    break
            else:
                ret[rel][pattern] = count
    return ret

def rel_ranges(include_parent):
    mn = 1 if include_parent else 0
    for n in range(1, args.ctx+1):
        for i_p in range(mn, 2):
            for i_s in range(n-i_p+1):
                yield i_p, i_s, (n-i_p-i_s)

def contextualize_rules(contexts, dct, ekey, include_parent=False):
    ct = args.count >> 2
    cp = [(f'p ({k})',v) for k,v in contexts['p'].most_common(ct)]
    cs = [(f's ({k})',v) for k,v in contexts['s'].most_common(ct)]
    cs += [(f'NEGATE s ({k})',v) for k,v in contexts['negs'].most_common(ct)]
    cc = [(f'c ({k})',v) for k,v in contexts['c'].most_common(ct)]
    cc += [(f'NEGATE c ({k})',v) for k,v in contexts['negc'].most_common(ct)]
    for i_p, i_s, i_c in rel_ranges(include_parent):
        for t_p in combinations(cp, i_p):
            for t_s in combinations(cs, i_s):
                for t_c in combinations(cc, i_c):
                    seq = t_p + t_s + t_c
                    ctx = tuple([s[0] for s in seq])
                    count = min(s[1] for s in seq)
                    for tgc, tgi in contexts['t'].most_common(ct):
                        yield (dct['rtype'],
                               format_rule(target=tgc, context=ctx, **dct),
                               format_relation(tgc, ctx),
                               min(count, tgi),
                               ekey)

def run_grammar(gpath, opath):
    subprocess.run(['vislcg3', '--in-binary', '--out-binary', '-g',
                    gpath, '-I', args.source, '-O', opath],
                   capture_output=True, check=True)
    with open(opath, 'rb') as fout:
        yield from parse_cg3(fout, windows_only=True)

def calc_intersection(rules: list, gpath: str, opath: str):
    if not rules:
        return []
    with open(gpath, 'w') as fout:
        for i, (s, r) in enumerate(rules):
            fout.write(r[2].replace('{NUM}', str(i)) + '\n')
    targets = defaultdict(set)
    contexts = defaultdict(set)
    for window in run_grammar(gpath, opath):
        for cohort in window.cohorts:
            for tag, heads in cohort.relations.items():
                if tag[0] == 'r' and tag[1:].isdigit():
                    contexts[int(tag[1:])].update(heads)
                elif tag.startswith('tr') and tag[2:].isdigit():
                    targets[int(tag[2:])].add(cohort.dep_self)
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
    return intersections

def score_window(slw, tlw):
    score = 0
    score += WEIGHTS['cohorts'] * abs(len(slw.cohorts) - len(tlw.cohorts))
    src_words = Counter((r.lemma, r.tags[0]) for c in slw.cohorts
                        for r in c.readings if 'SOURCE' not in r.tags)
    tgt_words = Counter((r.lemma, r.tags[0]) for c in tlw.cohorts
                        for r in c.readings if 'SOURCE' not in r.tags)
    extra = src_words - tgt_words
    missing = tgt_words - src_words
    score += WEIGHTS['missing'] * missing.total()
    score += WEIGHTS['extra'] * extra.total()
    score += WEIGHTS['ambig'] * (src_words.total() - len(slw.cohorts))
    score += WEIGHTS['ins'] * len([s for s in slw.cohorts if any(r.lemma == '"<ins>"' for r in s.readings)])
    score += WEIGHTS['unk'] * sum([ct for (lm, tg), ct in src_words.items()
                                   if lm.startswith('"@')])
    return score

def score_rule(rule, gpath, opath):
    with open(gpath, 'w') as fout:
        fout.write(RULE_HEADER + rule[1])
    score = 0
    for slw, tlw in zip(run_grammar(gpath, opath), target):
        score += score_window(slw, tlw)
    return score

with (TemporaryDirectory() as tmpdir,
      open(args.out, 'w') as rule_output):
    db_path = os.path.join(tmpdir, 'db.sqlite')
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('CREATE TABLE errors(rule, tags1, tags2, window, cohort, cohort_key)')
    cur.execute('CREATE TABLE context(rtype, rule TEXT, relation TEXT, count INT, error_label TEXT)')
    cur.execute('CREATE TABLE tests(cohort INTEGER, pattern TEXT)')
    con.commit()

    for iteration in range(args.iterations):
        src_path = os.path.join(tmpdir, f'output.{iteration}.bin')
        if iteration == 0:
            src_path = args.source
        with open(src_path, 'rb') as fin:
            source = list(parse_cg3(fin, windows_only=True))
        base_score = sum(score_window(s, t) for s, t in zip(source, target))
        tgt_path = os.path.join(tmpdir, f'output.{iteration+1}.bin')

        for table in ['errors', 'context', 'tests']:
            cur.execute(f'DELETE FROM {table}')
        con.commit()

        for window, (slw, tlw) in enumerate(zip(source, target)):
            cur.executemany('INSERT INTO errors VALUES(?, ?, ?, ?, ?, ?)',
                            gen_rules(window, slw, tlw))
            for ch in slw.cohorts:
                cur.executemany(
                    'INSERT INTO tests(cohort, pattern) VALUES(?, ?)',
                    [(ch.dep_self, dc) for dc in describe_cohort(ch)])
            con.commit()

        patterns = []
        for rt in RTYPES:
            cur.execute('SELECT COUNT(*) AS ct, rule, tags1, tags2, cohort_key FROM errors WHERE rule = ? GROUP BY rule, tags1, tags2, cohort_key ORDER BY ct DESC LIMIT ?', (rt, args.count))
            patterns += cur.fetchall()

        for count, rule, tags1, tags2, ckey in patterns:
            label = f'{rule}-{tags1}-{tags2}-{ckey}'
            cur.execute('SELECT window, cohort FROM errors WHERE rule = ? AND tags1 = ? AND tags2 = ? AND cohort_key = ?',
                        (rule, tags1, tags2, ckey))
            neighbors = defaultdict(set)
            for wnum, cnum in cur.fetchall():
                slw = source[wnum]
                collect_neighbors(slw, cnum, neighbors)
            dct = select_contexts(cur, neighbors)
            rules = list(contextualize_rules(
                dct,
                {'rtype': rule, 'tags': tags1, 'desttags': tags2},
                label,
                include_parent=(rule == 'rem-parent')))
            rules.sort(key=lambda x: x[3], reverse=True)
            cur.executemany('INSERT INTO context VALUES(?, ?, ?, ?, ?)',
                            rules[:args.beam])
            con.commit()

        rule_output.write('####################\n')
        rule_output.write(f'## {iteration}: {base_score}\n')
        rule_output.write('####################\n')
        print(f'{iteration=}, {base_score=}, {len(EXCLUDE)=}')

        failed_errors = set()
        non_failed = set()
        rules = []
        for rt in RTYPES:
            cur.execute('SELECT count, rule, relation, error_label FROM context WHERE rtype = ? ORDER BY count LIMIT ?', (rt, args.rule_count))
            for rule in cur.fetchall():
                i = len(rules)
                gpath = os.path.join(tmpdir, f'g{i:05}.cg3')
                opath = os.path.join(tmpdir, f'o{i:05}.bin')
                s = score_rule(rule, gpath, opath)
                print(s, rule[1])
                if s < base_score:
                    rules.append((s, rule))
                    non_failed.add(rule[-1])
                else:
                    failed_errors.add(rule[-1])
        rules.sort()
        gpath = os.path.join(tmpdir, f'intersection.{iteration}.cg3')
        opath = os.path.join(tmpdir, f'intersection.{iteration}.bin')
        intersections = calc_intersection(rules, gpath, opath)
        added = set()
        new_words = set()
        selected_rules = []
        for i, (score, rule) in enumerate(rules):
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
