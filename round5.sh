#!/bin/bash

rm -f hbo-grc.db hbo-grc.round5.cg3

echo "gen"
date
time ./round5.gen.py generated/hbo-grc/hbo.input.bin generated/hbo-grc/grc.gold.bin hbo-grc.db
echo "context"
date
time ./round5.context.py generated/hbo-grc/hbo.input.bin generated/hbo-grc/grc.gold.bin hbo-grc.db
echo "eval"
date
time ./round5.eval.py generated/hbo-grc/hbo.input.bin generated/hbo-grc/grc.gold.bin hbo-grc.db hbo-grc.round5.cg3 --count 1000

cat hbo-grc.round5.cg3
