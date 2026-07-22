#!/bin/bash

shared_args='--threads 10 --score_proc ch4_pipe_score/ch4_pipe_score --skip_windows spa/skip.json'
sel_args='--rule_count 100 --lemma_count 100'
replace_args='--rule_count 100 --lemma_count 100'
add_args='--rule_count 20 --lemma_count 20'
feat_args='--rule_count 100 --pos_count 20'
del_args='--rule_count 100 --lemma_count 20'

run_cg() {
    lang="$1"
    src_mode="$2"
    tgt_mode="$3"
    vislcg3 --in-binary --out-binary -g "spa/${lang}.${tgt_mode}.cg3" \
	    -I "spa/${lang}.${src_mode}.bin" \
	    -O "spa/${lang}.${tgt_mode}.bin"
}

run_lang() {
    lang="$1"
    tmp_prefix="spa/tmp/${lang}"
    mkdir -p "$tmp_prefix"
    rm -rf "${tmp_prefix}/sel"
    mkdir -p "${tmp_prefix}/sel"
    python3 lex_sel.py "spa/${lang}.src.bin" "spa/${lang}.tgt.bin" "pud${lang}" 500 "spa/${lang}.sel.cg3" $shared_args $sel_args --out_dir "${tmp_prefix}/sel"
    run_cg "$lang" src sel
    rm -rf "${tmp_prefix}/replace"
    mkdir -p "${tmp_prefix}/replace"
    python3 lex_replace.py "spa/${lang}.sel.bin" "spa/${lang}.tgt.bin" "pud${lang}" 500 "spa/${lang}.replace.cg3" $shared_args $replace_args --out_dir "${tmp_prefix}/replace"
    run_cg "$lang" sel replace
    rm -rf "${tmp_prefix}/add"
    mkdir -p "${tmp_prefix}/add"
    python3 lex_add.py "spa/${lang}.replace.bin" "spa/${lang}.tgt.bin" "pud${lang}" 500 "spa/${lang}.add.cg3" $shared_args $add_args --out_dir "${tmp_prefix}/add"
    run_cg "$lang" replace add
    rm -rf "${tmp_prefix}/feat"
    mkdir -p "${tmp_prefix}/feat"
    python3 lex_feat.py "spa/${lang}.add.bin" "spa/${lang}.tgt.bin" "pud${lang}" 500 "spa/${lang}.feat.cg3" $shared_args $feat_args --out_dir "${tmp_prefix}/feat"
    run_cg "$lang" add feat
    rm -rf "${tmp_prefix}/del"
    mkdir -p "${tmp_prefix}/del"
    python3 lex_del.py "spa/${lang}.feat.bin" "spa/${lang}.tgt.bin" "pud${lang}" 500 "spa/${lang}.del.cg3" $shared_args $del_args --out_dir "${tmp_prefix}/del"
    run_cg "$lang" feat del
}

run_lang $1
