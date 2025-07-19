#!/bin/bash

cat $2 | /home/daniel/apertium/cg3/src/cg-conv | /home/daniel/apertium/cg3/src/vislcg3 --dep-delimit -g $1 | /home/daniel/apertium/cg3/src/cg-conv --dep-delimit -Z > $3
