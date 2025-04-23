#!/bin/bash

mkdir -p generated/hbo-grc

get_hbo() {
    pushd ~/hbo-UD/UD_Ancient_Hebrew-PTNK
    cat *dev.conllu
    cat *test.conllu
    cat *train.conllu
    popd
}

get_hbo | grep -v newdoc | python3 skip_sent.py 'Exodus|Leviticus|Genesis-(31:51|32:33|35:21)' > generated/hbo-grc/hbo.conllu

cat generated/hbo-grc/hbo.conllu | python3 conllu2dix.py generated/hbo-grc/hbo.lex.json 2 3 5:HebBinyan > generated/hbo-grc/hbo.align.txt

get_grc() {
    pushd ~/UD_Ancient_Greek-PTNK
    cat *dev.conllu
    cat *test.conllu
    cat *train.conllu
    popd
}

get_grc | grep -v newdoc > generated/hbo-grc/grc.conllu

cat generated/hbo-grc/grc.conllu | python3 conllu2dix.py generated/hbo-grc/grc.lex.json 2 3 5:Gender > generated/hbo-grc/grc.align.txt

#eflomal-align --overwrite -s hbo.align.txt -t grc.align.txt -f hbo-grc.align.txt
python3 get_hbo_grc.py generated/hbo-grc/hbo.conllu generated/hbo-grc/grc.conllu > generated/hbo-grc/hbo-grc.align.txt

python3 json2dix.py generated/hbo-grc/hbo.lex.json generated/hbo-grc/grc.lex.json generated/hbo-grc/hbo-grc.align.txt generated/hbo-grc/hbo-grc.dix

lt-comp lr generated/hbo-grc/hbo-grc.dix generated/hbo-grc/hbo-grc.bin
