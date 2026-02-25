#!/bin/bash

dir=$1
#conllu=$2
conllu=ud-treebanks-v2.17/UD_Ancient_Greek-PTNK/grc_ptnk-ud-train.conllu

prefix="cv_data/${dir}"
src_conllu="${prefix}/train.src.conllu"

#python3 ch6_rearrange_conllu.py "$conllu" "${prefix}/train.tgt.conllu"

add_segment() {
  i=$1
  train="${prefix}/not${i}.conllu"
  train_bin="${prefix}/not${i}.bin"
  python3 ch6_rearrange_conllu.py "$conllu" "$train" --skip_fold $i
  head -c8 "${prefix}/0.bin" > "$train_bin"
  for j in $(seq 0 4)
  do
    if [[ $i != $j ]]; then
      tail -c+9 "${prefix}/${j}.bin" >> "$train_bin"
    fi
  done
  python3 train_word_lin.py "$train_bin" "$train" "${prefix}/${i}.lin" --iterations 500 --count 200 > "${prefix}/${i}.train.log"
  python3 linearize.py "${prefix}/${i}.lin" "${prefix}/${i}.bin" --format conllu >> "$src_conllu"
}

#rm -f "$src_conllu"
#add_segment 0 &
#add_segment 1 &
#add_segment 2 &
#add_segment 3 &
#add_segment 4 &

#wait `jobs -p`

source ./env/bin/activate

project() {
  name=$1
  python3 "ch6_align_${name}.py" "$src_conllu" "${prefix}/train.tgt.conllu" "${prefix}/train.align.${name}.txt"
  python3 ch6_project.py "$src_conllu" "${prefix}/train.tgt.conllu" "${prefix}/train.align.${name}.txt" "${prefix}/train.project.${name}.conllu"
  cat "${prefix}/train.project.${name}.conllu" | python3 conllu2apertium.py BLAH --surface | cg-conv | vislcg3 --dep-delimit -g ch6_connect_tree.cg3 --out-binary -O "${prefix}/train.ch6.src.${name}.bin"
}

project feat
project eflomal
project eflomal_feat

cat "${prefix}/train.tgt.conllu" | python3 conllu2apertium.py BLAH --surface | cg-conv -a | cg-conv -Z --dep-delimit > "${prefix}/train.ch6.tgt.bin"
