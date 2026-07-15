#!/bin/bash

mkdir -p spa

python3 remap_bidix.py ~/apertium/apertium-data/apertium-eng-spa/apertium-eng-spa.eng-spa.dix spa/eng-spa.dix
lt-comp rl spa/eng-spa.dix spa/spa-eng.bin

python3 remap_bidix.py ~/apertium/apertium-data/apertium-es-pt/apertium-es-pt.es-pt.dix spa/spa-por.dix
lt-comp lr spa/spa-por.dix spa/spa-por.bin

python3 remap_bidix.py ~/apertium/apertium-data/apertium-es-gl/apertium-es-gl.es-gl.dix spa/spa-glg.dix
lt-comp lr spa/spa-glg.dix spa/spa-glg.bin

conv() {
    cg-conv | vislcg3 --out-binary --dep-delimit -g spa/ensure_pos_tag.cg3
}

cat ud-treebanks-v2.17/UD_Spanish-PUD/*.conllu | python3 conllu2apertium.py --surface Person Gender | lt-proc -O spa/spa-glg.bin | conv > spa/glg.src.bin
cat ud-treebanks-v2.17/UD_Spanish-PUD/*.conllu | python3 conllu2apertium.py --surface Person Gender | lt-proc -O spa/spa-por.bin | conv > spa/por.src.bin
cat ud-treebanks-v2.17/UD_Spanish-PUD/*.conllu | python3 conllu2apertium.py --surface Person Gender | lt-proc -O spa/spa-eng.bin | conv > spa/eng.src.bin

cat ud-treebanks-v2.17/UD_English-PUD/*.conllu | \
    python3 conllu2apertium.py --surface BLAH | \
    conv > spa/eng.tgt.bin
cat ud-treebanks-v2.17/UD_Portuguese-PUD/*.conllu | \
    python3 conllu2apertium.py --surface BLAH | \
    conv > spa/por.tgt.bin
cat ud-treebanks-v2.17/UD_Galician-PUD/*.conllu | \
    python3 conllu2apertium.py --surface BLAH | \
    conv > spa/glg.tgt.bin
