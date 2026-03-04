#!/bin/bash

outdir="cv_data/jk_pipe_$1"
refdir=$2

src="${outdir}/train.src.bin"
tgt="${outdir}/train.tgt.bin"

cat "${outdir}/del.0.bin" > "$src"
tail -c +9 "${outdir}/del.1.bin" >> "$src"
tail -c +9 "${outdir}/del.2.bin" >> "$src"
tail -c +9 "${outdir}/del.3.bin" >> "$src"
tail -c +9 "${outdir}/del.4.bin" >> "$src"

cat "${refdir}/target.train.0.bin" > "$tgt"
tail -c +9 "${refdir}/target.train.1.bin" >> "$tgt"
tail -c +9 "${refdir}/target.train.2.bin" >> "$tgt"
tail -c +9 "${refdir}/target.train.3.bin" >> "$tgt"
tail -c +9 "${refdir}/target.train.4.bin" >> "$tgt"

cat "$tgt" | python3 bin2conllu.py > "${outdir}/train.tgt.conllu"
