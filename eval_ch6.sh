#!/bin/bash

function prepare_data() {
    dir_name="$1"
    infile="$2"
    raw_bin="cv_data/${dir_name}/dev.plain.bin"
    if [[ ! -f "$raw_bin" ]]; then
      vislcg3 -g "cv_data/${dir_name}/plain.cg3" -I "$infile" -O "$raw_bin" --in-binary --out-binary
    fi
    python3 linearize.py "cv_data/${dir_name}/r200.lin" "$raw_bin" --format cg | cg-conv -Z --dep-delimit > "cv_data/${dir_name}/dev.plain-lin.bin"
}

ref_conllu=ud-treebanks-v2.17/UD_Ancient_Greek-PTNK/grc_ptnk-ud-dev.conllu

source ./env/bin/activate

function project_and_eval() {
    dir_name="$1"
    mode="$2"
    prefix="cv_data/${dir_name}/dev.${mode}"
    vislcg3 -g "cv_data/${dir_name}/ch6.${mode}.cg3" -I "cv_data/${dir_name}/dev.plain-lin.bin" -O "${prefix}.bin" --in-binary --out-binary
    cat "${prefix}.bin" | python3 bin2conllu.py > "${prefix}.base.conllu"
    python3 "ch6_align_${mode}.py" "${prefix}.base.conllu" "$ref_conllu" "${prefix}.align.txt"
    python3 ch6_project.py "${prefix}.base.conllu" "$ref_conllu" "${prefix}.align.txt" "${prefix}.project.conllu"
    cat "${prefix}.project.conllu" | python3 conllu2apertium.py BLAH --surface | cg-conv | vislcg3 --dep-delimit -g ch6_connect_tree.cg3 --out-binary | python3 bin2conllu.py > "${prefix}.connect.conllu"
    udapy read.Conllu zone=gold files="$ref_conllu" \
          read.Conllu zone=pred files="${prefix}.connect.conllu" ignore_sent_id=1 \
          util.ResegmentGold \
          eval.Conll18 > "${prefix}.eval.log"
}

function project_and_eval_raw() {
    dir_name="$1"
    mode="$2"
    prefix="cv_data/${dir_name}/dev.${mode}.raw"
    cat "cv_data/${dir_name}/dev.plain-lin.bin" | python3 bin2conllu.py > "${prefix}.base.conllu"
    python3 "ch6_align_${mode}.py" "${prefix}.base.conllu" "$ref_conllu" "${prefix}.align.txt"
    python3 ch6_project.py "${prefix}.base.conllu" "$ref_conllu" "${prefix}.align.txt" "${prefix}.project.conllu"
    cat "${prefix}.project.conllu" | python3 conllu2apertium.py BLAH --surface | cg-conv | vislcg3 --dep-delimit -g ch6_connect_tree.cg3 --out-binary | python3 bin2conllu.py > "${prefix}.connect.conllu"
    udapy read.Conllu zone=gold files="$ref_conllu" \
          read.Conllu zone=pred files="${prefix}.connect.conllu" ignore_sent_id=1 \
          util.ResegmentGold \
          eval.Conll18 > "${prefix}.eval.log"
}

function run_folder() {
    name=`basename "$1"`
    infile="$2"
    echo "$name"
    prepare_data "$name" "$infile"
    project_and_eval "$name" feat
    project_and_eval "$name" eflomal
    project_and_eval "$name" eflomal_feat
    project_and_eval_raw "$name" feat
    project_and_eval_raw "$name" eflomal
    project_and_eval_raw "$name" eflomal_feat
    echo "${name} done"
}

#for folder in cv_data/*_m_*
#do
#    run_folder "$folder" generated/hbo-grc/hbo-macula.dev.bin &
#done

#for folder in cv_data/jk_*_g_*
#do
#    run_folder "$folder" generated/hbo-grc/hbo.dev.bin &
#done

#run_folder baseline blah

run_folder jk_pipe_grc_g &
run_folder jk_pipe_grc_m &

wait `jobs -p`
