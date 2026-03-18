#!/bin/bash

lang="$1"

if [[ "$lang" = "grc_g" ]]; then
    infile=generated/hbo-grc/hbo.dev.bin
    code=hbo
elif [[ "$lang" = "grc_m" ]]; then
    infile=generated/hbo-grc/hbo-macula.dev.bin
    code=hbo-macula
elif [[ "$lang" = "eng" ]]; then
    infile=generated/hbo-eng/hbo.NET.dev.bin
    code=hbo.NET
elif [[ "$lang" = "blx" ]]; then
    infile=generated/blx/hbo.blx.dev.bin
    code=hbo.blx
fi

function cg () {
    mode="$1"
    if [[ "$mode" = "sel" ]]; then
	fname="lex-output/lex_${mode}.${code}.cg3x"
    else
	fname="lex-output/lex_${mode}.${code}.cg3"
    fi
    vislcg3 -g "$fname" --in-binary --out-binary
}

cat "$infile" | cg sel | cg replace | cg add | cg feat | cg del > "lex-output/${lang}.dev.bin"
