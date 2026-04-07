#!/bin/bash

python3 md_prepare_conllu.py
. env/bin/activate
python3 ch6_align_eflomal.py manual-dix/hbo.conllu manual-dix/grc.conllu manual-dix/initial-align.txt
echo '[]' > manual-dix/maybe-skip.json
touch manual-dix/align.txt
