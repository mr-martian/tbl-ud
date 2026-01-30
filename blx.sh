#!/bin/bash

mkdir -p generated/blx

make_blx() {
    python3 parse_blx.py $1 2>generated/blx/blx.$1.skip.json > generated/blx/blx.$1.conllu
    cat generated/blx/blx.$1.conllu | python3 conllu2apertium.py --surface BLAH | cg-conv -a | cg-conv -Z --dep-delimit > generated/blx/blx.$1.bin
}

make_hbo() {
  cat sources/hbo-short-$1.conllu | python3 conllu2apertium.py --surface NOUN:Gender VERB:HebBinyan AUX:HebBinyan DET:PronType PROPN:Gender ExtPos 'LexDomain[SDBH]' 'LId[SDBH]' | lt-proc -O generated/blx/blx.bin | sed -E 's|(\^[^/]+/[^<]+)<|\1<SOURCE><|g' | cg-conv -a | vislcg3 --dep-delimit -g rempunct.cg3 --out-binary > generated/blx/hbo.blx.$1.bin
}

make_blx train
make_blx dev
make_blx test

python3 blx_dix_by_gloss.py
lt-comp lr generated/blx/blx.dix generated/blx/blx.bin

make_hbo train
make_hbo dev
make_hbo test
