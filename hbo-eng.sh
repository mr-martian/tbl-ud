#!/bin/bash

version=$1

make_eng() {
    python3 usfm2txt.py $version $1 2>generated/hbo-eng/eng.$version.$1.skip.json | apertium -f line -d /home/daniel/apertium/apertium-data/apertium-eng eng-tagger-case | sed 's/ _ / /g' | python3 eng_tags.py | sed 's/\(*[A-Za-z]\+\)/\1<UNK>/g' | vislcg3 -g segment_eng.cg3 --in-apertium --out-binary -O generated/hbo-eng/eng.$version.$1.bin
}

make_hbo() {
  cat /home/daniel/hbo-UD/UD_Ancient_Hebrew-PTNK/hbo_ptnk-ud-$1.conllu | python3 conllu2apertium.py --surface NOUN:Gender VERB:HebBinyan AUX:HebBinyan DET:PronType PROPN:Gender ExtPos 'LexDomain[SDBH]' 'LId[SDBH]' | lt-proc -O generated/hbo-eng/$version.bin | sed -E 's|(\^[^/]+/[^<]+)<|\1<SOURCE><|g' | cg-conv -a | vislcg3 --dep-delimit -g rempunct.cg3 --out-binary > generated/hbo-eng/hbo.$version.$1.bin
}

python3 eng_dix_from_strongs.py $version
lt-comp lr generated/hbo-eng/$version.dix generated/hbo-eng/$version.bin

make_hbo train
make_hbo dev
make_hbo test
make_eng train
make_eng dev
make_eng test
