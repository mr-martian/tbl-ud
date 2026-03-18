#!/usr/bin/env python3

# avoid needing to remember to set PYTHONPATH
# while the library is still in a dev branch
# PYTHONPATH="/home/daniel/apertium/cg3/python:$PYTHONPATH"
import sys
sys.path.insert(0, '/home/daniel/apertium/cg3/python')

import cg3

import os
import pickle
import sqlite3
import subprocess
from tempfile import TemporaryDirectory

RTYPES = ['remove', 'append', 'addcohort', 'rem-self', 'rem-parent']

COUNT = 100
SOURCEFILE = 'generated/hbo-grc/hbo.input.bin'
TARGETFILE = 'generated/hbo-grc/grc.gold.bin'
DB = 'hbo-grc.db'
OUT = 'hbo-grc.pickle'

with open(SOURCEFILE, 'rb') as fin:
    source = list(cg3.parse_binary_stream(fin))

with open(TARGETFILE, 'rb') as fin:
    target = list(cg3.parse_binary_stream(fin))

def get_rules():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    for rt in RTYPES:
        cur.execute('SELECT count, rule FROM context WHERE rtype = ? ORDER BY count LIMIT ?', (rt, COUNT))
        yield from cur.fetchall()

def run_grammar(gpath, opath):
    subprocess.run(['/home/daniel/apertium/cg3/src/cg-proc',
                    '-f3', gpath, SOURCEFILE, opath],
                   capture_output=True)
    with open(opath, 'rb') as fout:
        return list(cg3.parse_binary_stream(fout))

with (TemporaryDirectory() as tmpdir,
      open(OUT, 'wb') as fpkl):
    for i, (count, rule) in enumerate(get_rules()):
        print(i, rule)
        gpath = os.path.join(tmpdir, f'g{i:05}.cg3')
        opath = os.path.join(tmpdir, f'o{i:05}.bin')
        with open(gpath, 'w') as fout:
            fout.write('OPTIONS += addcohort-attach ;\n')
            fout.write('DELIMITERS = "<$$$>" ;\n')
            fout.write(rule)
        pickle.dump((count, rule, run_grammar(gpath, opath)), fpkl)
