#!/bin/bash

conllu="$1"
base=$(basename "$conllu")
mkdir -p lin-exp-data
bin1="lin-exp-data/${base}.input.bin"
rules="lin-exp-data/${base}.lin"
bin2="lin-exp-data/${base}.shuf.bin"
conllu_shuf="lin-exp-data/${base}.shuf.conllu"
conllu_lin="lin-exp-data/${base}.lin.conllu"

#shuf_gram=head-final.lin
shuf_gram=lin-exp-data/ja_gsdluw-ud-train.conllu.lin

cat "$conllu" | python3 conllu2apertium.py BLAH --surf | cg-conv -a | cg-conv --dep-delimit -Z > "$bin1"

python3 linearize.py "$shuf_gram" "$bin1" --format cg | cg-conv --dep-delimit -Z > "$bin2"

#cat "$conllu" | python3 train_tree_lin_get_data.py | cg-conv --dep-delimit -Z > "$bin2"

python3 train_word_lin.py "$bin2" "$conllu" "$rules" --iterations 25

echo "shuffled BLEU"
python3 linearize.py "$shuf_gram" "$bin1" --format conllu > "$conllu_shuf"
./env/bin/python3 score_lin.py "$conllu_shuf" "$conllu"
echo "linearized BLEU (train)"
python3 linearize.py "$rules" "$bin1" --format conllu > "$conllu_lin"
./env/bin/python3 score_lin.py "$conllu_lin" "$conllu"
