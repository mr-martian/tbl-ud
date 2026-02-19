#!/bin/bash

hin=~/hbo-UD/UD_Ancient_Hebrew-PTNK/hbo_ptnk-ud-train.conllu
gin=~/UD_Ancient_Greek-PTNK/grc_ptnk-ud-train.conllu

make_grc() {
  python3 conllu2apertium.py --surface NOUN:Gender DET:PronType PROPN:Gender --feats_file generated/hbo-grc/grc.$1.feats.json | cg-conv -a | cg-conv -Z --dep-delimit > generated/hbo-grc/grc.$1.bin
}

make_hbo() {
  python3 conllu2apertium.py --surface NOUN:Gender VERB:HebBinyan AUX:HebBinyan DET:PronType PROPN:Gender ExtPos 'LexDomain[SDBH]' 'LId[SDBH]' --skip_ids '31:51|32:33|35:21' | lt-proc -O generated/hbo-grc/macula.bin | sed -E 's|(\^[^/]+/[^<]+)<|\1<SOURCE><|g' | cg-conv -a | vislcg3 --dep-delimit -g rempunct.cg3 --out-binary
}

python3 dix_from_macula.py

lt-comp lr generated/hbo-grc/macula.dix generated/hbo-grc/macula.bin

cat sources/hbo-short-train.conllu | make_hbo > generated/hbo-grc/hbo-macula.train.bin
cat "$gin" | make_grc train
cat sources/hbo-short-test.conllu | make_hbo > generated/hbo-grc/hbo-macula.test.bin
cat sources/hbo-short-dev.conllu | make_hbo > generated/hbo-grc/hbo-macula.dev.bin
cat ~/UD_Ancient_Greek-PTNK/grc_ptnk-ud-test.conllu | make_grc test
cat ~/UD_Ancient_Greek-PTNK/grc_ptnk-ud-dev.conllu | make_grc dev
