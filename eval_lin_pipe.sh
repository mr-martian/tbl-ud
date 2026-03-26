#!/bin/bash

dev_bin="$1"
conllu_dir="$2"
eval_dir="$3"

bin0="${eval_dir}/lin0.bin"
conllu0="${eval_dir}/lin0.conllu"
conllu200="${eval_dir}/lin200.conllu"

if [[ ! -f "$bin0" ]] || [[ ! -s "$bin0" ]]; then
  vislcg3 -I "$dev_bin" -O "$bin0" -g "${eval_dir}/main.cg3" \
	        --in-binary --out-binary
fi

if [[ ! -f "$conllu0" ]] || [[ ! -s "$conllu0" ]]; then
  cat "$bin0" | python3 bin2conllu.py > "$conllu0"
fi

if [[ ! -f "$conllu200" ]] || [[ ! -s "$conllu200" ]]; then
  python3 linearize.py "${eval_dir}/r200.lin" "$bin0" --format conllu > "$conllu200"
fi

dev_ref=$(ls "$conllu_dir"/*dev*.conllu)

echo "no linearization"
./env/bin/python3 calc_bleu.py "$conllu0" "$dev_ref" "$conllu_dir"/*.conllu | tail -n2
echo "r200"
./env/bin/python3 calc_bleu.py "$conllu200" "$dev_ref" "$conllu_dir"/*.conllu | tail -n2
