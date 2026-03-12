#!/bin/bash

dev_bin="$1"
conllu_dir="$2"
eval_dir="$3"

vislcg3 -I "$dev_bin" -O "${eval_dir}/lin0.bin" -g "${eval_dir}/main.cg3" \
	--in-binary --out-binary

cat "${eval_dir}/lin0.bin" | python3 bin2conllu.py > "${eval_dir}/lin0.conllu"
#python3 linearize.py "${eval_dir}/r50.lin" "${eval_dir}/lin0.bin" --format conllu > "${eval_dir}/lin50.conllu"
#python3 linearize.py "${eval_dir}/r100.lin" "${eval_dir}/lin0.bin" --format conllu > "${eval_dir}/lin100.conllu"
python3 linearize.py "${eval_dir}/r200.lin" "${eval_dir}/lin0.bin" --format conllu > "${eval_dir}/lin200.conllu"

dev_ref=$(ls "$conllu_dir"/*dev*.conllu)

echo "no linearization"
./env/bin/python3 calc_bleu.py "${eval_dir}/lin0.conllu" "$dev_ref" "$conllu_dir"/*.conllu | tail -n1
#echo "r50"
#./env/bin/python3 calc_bleu.py "${eval_dir}/lin50.conllu" "$dev_ref" "$conllu_dir"/*.conllu | tail -n1
#echo "r100"
#./env/bin/python3 calc_bleu.py "${eval_dir}/lin100.conllu" "$dev_ref" "$conllu_dir"/*.conllu | tail -n1
echo "r200"
./env/bin/python3 calc_bleu.py "${eval_dir}/lin200.conllu" "$dev_ref" "$conllu_dir"/*.conllu | tail -n1
