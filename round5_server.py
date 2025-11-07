#!/usr/bin/env python3

from collections import Counter
import pickle
from flask import Flask, request, render_template
import os

with open('hbo-grc.factors.pkl', 'rb') as fin:
    DATA = pickle.load(fin)

KEYS = set()
for row in DATA:
    KEYS.update(row[2].keys())
KEYS = sorted(KEYS)

base_dir = os.path.dirname(__file__)
app = Flask('round5-tbl',
            template_folder=os.path.join(base_dir, 'templates'))

@app.route('/')
def main():
    weights = {}
    for key in KEYS:
        try:
            weights[key] = int(request.args[key])
        except Exception as e:
            weights[key] = 0
    scored = [(sum(v*factors.get(k, 0) for k, v in weights.items()),
               -count, rule, count, factors)
              for rule, count, factors in DATA]
    scored.sort()
    return render_template('round5.html', scored=scored, weights=weights,
                           keys=KEYS)
