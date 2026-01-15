#!/bin/bash

prefix=$1
src=$2
tgt=$3
feats=$4

for g in grammars/${prefix}*.cg3
do
  rm -f "$g.dev.log"
  echo "$g"
  for i in $(seq 0 20 300)
  do
	  gram=/tmp/${prefix}_grammar.cg3
	  out=/tmp/${prefix}_out.bin
	  echo "$i"
	  ln=$(grep -n "$i:" "$g" | head -n1 | cut -f1 -d:)
	  printf "%s\t" "$i" >> "$g.dev.log"
	  head -n "$ln" "$g" > "$gram"
	  vislcg3 --in-binary --out-binary -I "$src" -O "$out" -g "$gram"
	  python3 metrics.py "$out" "$tgt" --target_feats "$feats" >> "$g.dev.log"
  done
done
