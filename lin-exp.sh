#!/bin/bash

#shuf_gram=lin-exp-data/ja_pud-ud-test.conllu.lin
#shuf_lang=jap
shuf_gram=lin-exp-data/tr_pud-ud-test.conllu.lin
shuf_lang=tur
#shuf_gram=lin-exp-data/sjo_xtb-ud-test.conllu.lin
#shuf_lang=sjo

tb="$1"
count="$2"
conllu=$(ls ud-treebanks-v2.17/${tb}/*train*.conllu)
dev_conllu=$(ls ud-treebanks-v2.17/${tb}/*dev*.conllu)
base=$(basename "$conllu")
base="${base}.${shuf_lang}.${count}"
dev_base="${base}.dev"
mkdir -p lin-exp-data
bin1="lin-exp-data/${base}.input.bin"
rules="lin-exp-data/${base}.lin"
bin2="lin-exp-data/${base}.shuf.bin"
conllu_shuf="lin-exp-data/${base}.shuf.conllu"
conllu_lin="lin-exp-data/${base}.lin.conllu"
dev_bin1="lin-exp-data/${dev_base}.input.bin"
dev_bin2="lin-exp-data/${dev_base}.shuf.bin"
png="lin-exp-data/${base}.loss.png"

#shuf_gram=head-final.lin
#shuf_gram=lin-exp-data/ja_pud-ud-test.conllu.lin
shuf_gram=lin-exp-data/tr_pud-ud-test.conllu.lin

rm -f "$rules"

cat "$conllu" | python3 conllu2apertium.py BLAH --surf | cg-conv -a | cg-conv --dep-delimit -Z > "$bin1"

python3 linearize.py "$shuf_gram" "$bin1" --format cg | cg-conv --dep-delimit -Z > "$bin2"

#cat "$conllu" | python3 train_tree_lin_get_data.py | cg-conv --dep-delimit -Z > "$bin2"

python3 train_word_lin.py "$bin2" "$conllu" "$rules" --iterations 500 --count "$count"

echo "shuffled BLEU"
python3 linearize.py "$shuf_gram" "$bin1" --format conllu > "$conllu_shuf"
./env/bin/python3 score_lin.py "$conllu_shuf" "$conllu"
echo "linearized BLEU (train)"
python3 linearize.py "$rules" "$bin2" --format conllu > "$conllu_lin"
./env/bin/python3 score_lin.py "$conllu_lin" "$conllu"

cat "$dev_conllu" | python3 conllu2apertium.py BLAH --surf | cg-conv -a | cg-conv --dep-delimit -Z > "$dev_bin1"

python3 linearize.py "$shuf_gram" "$dev_bin1" --format cg | cg-conv --dep-delimit -Z > "$dev_bin2"

./env/bin/python3 eval_word_lin.py "$rules" "$bin2" "$conllu" "$dev_bin2" "$dev_conllu" "$png"
