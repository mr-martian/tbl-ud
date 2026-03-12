#!/bin/bash

lang="$1"
conllu_dir="$2"

cat "lex-output/${lang}.dev.bin" | python3 bin2conllu.py > "cv_data/jk_pipe_${lang}/lin0.conllu"

python3 linearize.py "cv_data/jk_pipe_${lang}/r200.lin" "lex-output/${lang}.dev.bin" --format conllu > "cv_data/jk_pipe_${lang}/lin200.conllu"

dev_ref=$(ls "$conllu_dir"/*dev*.conllu)

echo "no linearization"
./env/bin/python3 calc_bleu.py "cv_data/jk_pipe_${lang}/lin0.conllu" "$dev_ref" "$conllu_dir"/*.conllu | tail -n1
echo "r200"
./env/bin/python3 calc_bleu.py "cv_data/jk_pipe_${lang}/lin200.conllu" "$dev_ref" "$conllu_dir"/*.conllu | tail -n1
