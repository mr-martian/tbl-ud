import cg3
import metrics

import argparse
import concurrent.futures
import json
import os
import sqlite3
import subprocess
import tempfile
import tomllib

parser = argparse.ArgumentParser()
parser.add_argument('config')
parser.add_argument('--resume', action='store_true')
parser.add_argument('--cores', type=int)
args = parser.parse_args()

with open(args.config, 'rb') as fin:
    CONFIG = tomllib.load(fin)

def load_cg(path):
    with open(path, 'rb') as fin:
        return list(cg3.parse_binary_stream(fin, windows_only=True))

TEST_DATA = []
for blob in CONFIG['files']:
    TEST_DATA.append((blob['test_source'], load_cg(blob['test_target'])))

def score_grammar(path, index):
    with tempfile.NamedTemporaryFile() as fout:
        subprocess.run(['vislcg3', '--in-binary', '--out-binary',
                        '-g', path, '-I', TEST_DATA[index][0],
                        '-O', fout.name], capture_output=True)
        return metrics.PER(load_cg(fout.name), TEST_DATA[index][1])

def run_config(tmpdir, row):
    grammar_file = os.path.join(tmpdir, f'g{row[0]}.cg3')
    file_idx = row[3]
    sents = row[5]
    cmd = ['python3', 'round11.py',
           CONFIG['files'][file_idx]['train_source'],
           CONFIG['files'][file_idx]['train_target'],
           str(row[6]),
           grammar_file,
           '--weights', str(row[10]),
           '--count', str(row[9]),
           '--beam', str(row[9]),
           '--rule_count', str(row[9]),
           '--context_similarity', str(row[8]),
           '--max_sents', str(sents)]
    mem = 0
    time = 0
    increment = row[7]
    while True:
        print(' '.join(cmd))
        proc = subprocess.run(cmd, capture_output=True)
        blob = json.loads(proc.stderr.decode('utf-8'))
        mem += blob['max_mem_kb']
        time += blob['time_sec']
        if increment == 0:
            break
        if sents >= CONFIG['files'][file_idx]['sentences']:
            break
        sents += increment
        cmd[-1] = str(sents)
        if '--append' not in cmd:
            cmd = cmd[:-2] + ['--append'] + cmd[-2:]
    return score_grammar(grammar_file, file_idx) + (time, mem, row[0])

if not args.resume:
    try:
        os.remove(CONFIG['db'])
    except FileNotFoundError:
        pass

con = sqlite3.connect(CONFIG['db'])
cur = con.cursor()

if not args.resume:
    cur.execute('CREATE TABLE jobs(completed, stage, file_idx, file_name, initial_size, iterations, increment, similarity, filters, errors, per_lem, per_form, time, mem, UNIQUE(file_idx, initial_size, iterations, increment, similarity, filters, errors) ON CONFLICT IGNORE)')
    init = CONFIG['initial_parameters']
    for i, blob in enumerate(CONFIG['files']):
        cur.execute('INSERT INTO jobs VALUES(0, 0, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0)', (i, blob['name'], init['initial_size'], init['iterations'], init['increment'], init['similarity'], init['filters'], json.dumps(init['errors'])))
    con.commit()

STAGES = [None, 'initial_size', 'iterations', 'increment', 'similarity', 'filters', 'errors']

def run_block(tmpdir, block):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for row in block:
            futures.append(executor.submit(run_config, tmpdir, row))
        results = []
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
        return results

for stage_num, stage in enumerate(STAGES):
    print('STAGE', stage_num, stage)
    if stage_num != 0:
        prev = []
        cur.execute('SELECT * FROM jobs WHERE completed = 1 AND stage < ? ORDER BY per_lem ASC LIMIT 5', (stage_num,))
        prev += cur.fetchall()
        cur.execute('SELECT * FROM jobs WHERE completed = 1 AND stage < ? ORDER BY per_form ASC LIMIT 5', (stage_num,))
        prev += cur.fetchall()
        new = []
        for p in prev:
            for option in CONFIG['parameters'][stage]:
                n = list(p[:-4])
                n[0] = 0
                n[1] = stage_num
                n[stage_num+3] = option
                if stage == 'errors':
                    n[stage_num+3] = json.dumps(option)
                new.append(n)
        cur.executemany('INSERT INTO jobs VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0)', new)
        con.commit()
    with tempfile.TemporaryDirectory() as tmpdir:
        cur.execute('SELECT rowid, * FROM jobs WHERE completed = 0 AND stage = ?', (stage_num,))
        rows = cur.fetchall()
        for i in range(0, len(rows), args.cores):
            results = run_block(tmpdir, rows[i:i+args.cores])
            cur.executemany('UPDATE jobs SET completed = 1, per_lem = ?, per_form = ?, time = ?, mem = ? WHERE rowid = ?', results)
            con.commit()
