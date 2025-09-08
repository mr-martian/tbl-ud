#!/bin/bash

python3 dix_by_gloss.py generated/hbo-grc/hbo.conllu generated/hbo-grc/grc.conllu -t NOUN:Gender -s NOUN:Gender -s VERB:HebBinyan -s AUX:HebBinyan -s DET:PronType -t DET:PronType -s PROPN:Gender -t PROPN:Gender generated/hbo-grc/gloss.dix

lt-comp lr generated/hbo-grc/gloss.dix generated/hbo-grc/gloss.bin

cat generated/hbo-grc/hbo.conllu | python3 conllu2apertium.py --count 100 NOUN:Gender VERB:HebBinyan AUX:HebBinyan DET:PronType PROPN:Gender | lt-proc -b generated/hbo-grc/gloss.bin | python3 apertium2cg.py | cg-conv -aC > generated/hbo-grc/hbo.gloss.cg3.txt

#cat generated/hbo-grc/grc.conllu | python3 conllu2apertium.py NOUN:Gender DET:PronType PROPN:Gender | lt-proc -b generated/hbo-grc/gloss.bin | python3 apertium2cg.py | cg-conv -aC > generated/hbo-grc/grc.gloss.cg3.txt
cat generated/hbo-grc/grc.conllu | python3 conllu2apertium.py --count 100 NOUN:Gender DET:PronType PROPN:Gender | sed -E 's|\^([^$]*)\$|\^\1/\1\$|g' | python3 apertium2cg.py | cg-conv -aC > generated/hbo-grc/grc.gloss.cg3.txt

cat <<EOF > rempunct.cg3
DELIMITERS = "<$$$>" ;
REMCOHORT (tgt:PUNCT) ;
EOF

cat generated/hbo-grc/hbo.gloss.cg3.txt | vislcg3 --dep-delimit -g rempunct.cg3 | cg-conv -cZ --dep-delimit > generated/hbo-grc/hbo.input.bin

cat generated/hbo-grc/grc.gloss.cg3.txt | cg-conv -cZ --dep-delimit > generated/hbo-grc/grc.gold.bin
