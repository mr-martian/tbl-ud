#!/bin/bash

tb=$1
relabel=$2
detach=$3

mkdir -p generated/ch6_independent/

for inp in ud-treebanks-v2.17/$tb/*.conllu
do
    base=$(basename "$inp")
    prefix="generated/ch6_independent/${base/.conllu/}_${relabel}_${detach}"
    python3 ch6_mangle_trees.py "$inp" "${prefix}.mangle.conllu" "$relabel" "$detach"
    cat "${prefix}.mangle.conllu" | python3 ch6_connect_tree.py > "${prefix}.connect.conllu"
    cat "${prefix}.connect.conllu" | python3 conllu2apertium.py --surface BLAH | cg-conv -a | cg-conv -Z --dep-delimit > "$prefix.input.bin"
    cat "$inp" | python3 conllu2apertium.py --surface BLAH | cg-conv -a | cg-conv -Z --dep-delimit > "$prefix.reference.bin"
done
