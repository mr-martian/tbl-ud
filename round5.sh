#!/bin/bash

rm -f hbo-grc.db hbo-grc.round5.cg3

./round5.gen.py generated/hbo-grc/hbo.input.bin generated/hbo-grc/grc.gold.bin hbo-grc.db
./round5.context.py generated/hbo-grc/hbo.input.bin generated/hbo-grc/grc.gold.bin hbo-grc.db
./round5.eval.py generated/hbo-grc/hbo.input.bin generated/hbo-grc/grc.gold.bin hbo-grc.db hbo-grc.round5.cg3
