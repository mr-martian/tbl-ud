#!/bin/bash

source env/bin/activate
pushd ud-treebanks-v2.17
mkdir -p ../tb-logs
rm -f ../tb-logs/all.jsonl
for tb in *
do
    echo $tb
    printf "${tb}\t" >> ../tb-logs/all.jsonl
    cat $tb/*.conllu | PYTHONPATH="/home/daniel/tbl-ud/blocks:$PYTHONPATH" udapy .SurveyNonprojective 2> ../tb-logs/$tb.log >> ../tb-logs/all.jsonl
done
popd
grep -r 'Traceback' tb-logs || python3 summarize_nonproj.py
