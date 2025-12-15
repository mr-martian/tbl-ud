#!/bin/bash

hin=~/hbo-UD/UD_Ancient_Hebrew-PTNK/hbo_ptnk-ud-train.conllu
gin=~/UD_Ancient_Greek-PTNK/grc_ptnk-ud-train.conllu

make_grc() {
  python3 conllu2apertium.py --surface NOUN:Gender DET:PronType PROPN:Gender | cg-conv -a -Z --dep-delimit
}

make_hbo() {
  python3 conllu2apertium.py --surface NOUN:Gender VERB:HebBinyan AUX:HebBinyan DET:PronType PROPN:Gender ExtPos | lt-proc -O generated/hbo-grc/gloss.bin | sed -E 's|(\^[^/]+/[^<]+)<|\1<SOURCE><|g' | cg-conv -a | vislcg3 --dep-delimit -g rempunct.cg3 --out-binary
}

python3 dix_by_gloss.py "$hin" "$gin" -t NOUN:Gender -s NOUN:Gender -s VERB:HebBinyan -s AUX:HebBinyan -s DET:PronType -t DET:PronType -s PROPN:Gender -t PROPN:Gender generated/hbo-grc/gloss.dix

lt-comp lr generated/hbo-grc/gloss.dix generated/hbo-grc/gloss.bin

cat <<EOF > rempunct.cg3
DELIMITERS = "<\$\$\$>" ;
REMCOHORT (SOURCE PUNCT) ;
MERGECOHORTS ("<\$1\$5>"v "\$2\$6"v SOURCE VSTR:\$3 VSTR:\$4 "@null" X VSTR:\$4) ("<\\(.+\\)>"r "\\([^<>]+\\)"r SOURCE /^ExtPos=\\(.+\\)\$/r /^\\(@.+\\)\$/r) WITH (c ("<\\(.+\\)>"r "\\([^<>]+\\)"r SOURCE @fixed)) ;
EOF

cat sources/hbo-short-train.conllu | make_hbo > generated/hbo-grc/hbo.input.bin
cat "$gin" | make_grc > generated/hbo-grc/grc.gold.bin
cat sources/hbo-short-test.conllu | make_hbo > generated/hbo-grc/hbo.test.bin
cat sources/hbo-short-dev.conllu | make_hbo > generated/hbo-grc/hbo.dev.bin
cat ~/UD_Ancient_Greek-PTNK/grc_ptnk-ud-test.conllu | make_grc > generated/hbo-grc/grc.test.bin
cat ~/UD_Ancient_Greek-PTNK/grc_ptnk-ud-dev.conllu | make_grc > generated/hbo-grc/grc.dev.bin
