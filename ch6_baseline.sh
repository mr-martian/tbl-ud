#!/bin/bash

mkdir -p cv_data/baseline

python3 <<EOF
with (open('/home/daniel/hbo-UD/UD_Ancient_Hebrew-PTNK/hbo_ptnk-ud-train.conllu') as fin,
      open('cv_data/baseline/hbo.train.conllu', 'w') as fout):
    for block in fin.read().split('\n\n'):
        if 'Genesis' not in block and 'Ruth' not in block: continue
        if '31:51' in block or '32:33' in block or '35:21' in block: continue
        fout.write(block + '\n\n')
EOF

. env/bin/activate

prefix=cv_data/baseline
src=cv_data/baseline/hbo.train.conllu
tgt=ud-treebanks-v2.17/UD_Ancient_Greek-PTNK/grc_ptnk-ud-train.conllu
python3 ch6_align_eflomal.py "$src" "$tgt" "${prefix}/train.align.eflomal.txt"
python3 ch6_project.py "$src" "$tgt" "${prefix}/train.align.eflomal.txt" "${prefix}/train.project.eflomal.conllu"
cat "${prefix}/train.project.eflomal.conllu" | python3 conllu2apertium.py BLAH --surface | cg-conv | vislcg3 --dep-delimit -g ch6_connect_tree.cg3 --out-binary -O "${prefix}/train.ch6.src.eflomal.bin"

cat "$tgt" | python3 conllu2apertium.py BLAH --surface | cg-conv -a | cg-conv -Z --dep-delimit > "${prefix}/train.ch6.tgt.bin"
