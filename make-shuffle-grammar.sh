#!/bin/bash

conllu="$1"
base=$(basename "$conllu")
mkdir -p lin-exp-data
rules="lin-exp-data/${base}.lin"
bin="lin-exp-data/${base}.shuf.bin"

cat "$conllu" | python3 train_tree_lin_get_data.py | cg-conv --dep-delimit -Z > "$bin"

python3 train_word_lin.py "$bin" "$conllu" "$rules" --iterations 100
