#!/bin/bash

tb="$1"
count="$2"
shuf_lang="$3"
mode="$4"

if [[ "$shuf_lang" == "jap" ]]; then
    shuf_gram=lin-exp-data/ja_pud-ud-test.conllu.lin
elif [[ "$shuf_lang" == "tur" ]]; then
    shuf_gram=lin-exp-data/tr_pud-ud-test.conllu.lin
elif [[ "$shuf_lang" == "sjo" ]]; then
    shuf_gram=lin-exp-data/sjo_xdt-ud-test.conllu.lin
else
    echo "unknown language '$shuf_lang'"
    exit 1
fi

if [[ "$mode" == "tree" ]]; then
    train_script=train_tree_lin.py
    eval_arg=--tree
elif [[ "$mode" == "word" ]]; then
    train_script=train_word_lin.py
    eval_arg=
else
    echo "unknown mode '$mode'"
    exit 1
fi

conllu=$(ls ud-treebanks-v2.17/${tb}/*train*.conllu)
dev_conllu=$(ls ud-treebanks-v2.17/${tb}/*dev*.conllu 2>/dev/null || ls ud-treebanks-v2.17/${tb}/*test*.conllu)
base=$(basename "$conllu")
base="${base}.${mode}.${shuf_lang}.${count}"
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

rm -f "$rules"

cat "$conllu" | python3 conllu2apertium.py BLAH --surf | cg-conv -a | cg-conv --dep-delimit -Z > "$bin1"

python3 linearize.py "$shuf_gram" "$bin1" --format cg | cg-conv --dep-delimit -Z > "$bin2"

python3 "$train_script" "$bin2" "$conllu" "$rules" --iterations 500 --count "$count"

echo "shuffled BLEU"
python3 linearize.py "$shuf_gram" "$bin1" --format conllu > "$conllu_shuf"
./env/bin/python3 score_lin.py "$conllu_shuf" "$conllu"
echo "linearized BLEU (train)"
python3 linearize.py "$rules" "$bin2" --format conllu > "$conllu_lin"
./env/bin/python3 score_lin.py "$conllu_lin" "$conllu"

cat "$dev_conllu" | python3 conllu2apertium.py BLAH --surf | cg-conv -a | cg-conv --dep-delimit -Z > "$dev_bin1"

python3 linearize.py "$shuf_gram" "$dev_bin1" --format cg | cg-conv --dep-delimit -Z > "$dev_bin2"

./env/bin/python3 eval_word_lin.py "$rules" "$bin2" "$conllu" "$dev_bin2" "$dev_conllu" "$png" $eval_arg
