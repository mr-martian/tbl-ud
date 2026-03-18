#!/bin/bash

rm -rf round5_data
mkdir round5_data

cp generated/hbo-grc/grc.gold.bin round5_data/gold.bin
cp generated/hbo-grc/hbo.input.bin round5_data/input.1.bin

function iter() {
    n=$1
    next=`echo $n + 1 | bc`
    inp=round5_data/input.$n.bin
    db=round5_data/stats.$n.db
    gold=generated/hbo-grc/grc.gold.bin
    out=round5_data/grammar.$n.cg3
    echo "gen $n"
    date
    time ./round5.gen.py $inp $gold $db
    echo "context $n"
    date
    time ./round5.context.py $inp $gold $db
    echo "eval $n"
    date
    time ./round5.eval.py $inp $gold $db $out --count 100
    bash binformat_workaround.sh $out $inp round5_data/input.$next.bin
    echo "####################" >> round5_data/grammar.cg3
    echo "# ROUND $n" >> round5_data/grammar.cg3
    echo "####################" >> round5_data/grammar.cg3
    cat $out >> round5_data/grammar.cg3
    echo "" >> round5_data/grammar.cg3
}

for i in $(seq 10)
do
    iter $i
done
