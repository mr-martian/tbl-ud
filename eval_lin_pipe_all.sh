#!/bin/bash

for folder in cv_data/jk*grc_g*
do
    echo "$folder"
    bash eval_lin_pipe.sh generated/hbo-grc/hbo.dev.bin ud-treebanks-v2.17/UD_Ancient_Greek-PTNK "$folder" > "${folder}/eval_lin_pipe.log" &
done

for folder in cv_data/jk*grc_m*
do
    echo "$folder"
    bash eval_lin_pipe.sh generated/hbo-grc/hbo.dev.bin ud-treebanks-v2.17/UD_Ancient_Greek-PTNK "$folder" > "${folder}/eval_lin_pipe.log" &
done

for folder in cv_data/jk*eng*
do
    echo "$folder"
    bash eval_lin_pipe.sh generated/hbo-eng/hbo.NET.dev.bin generated/hbo-eng "$folder" > "${folder}/eval_lin_pipe.log" &
done

for folder in cv_data/jk*blx*
do
    echo "$folder"
    bash eval_lin_pipe.sh generated/blx/hbo.blx.dev.bin generated/blx "$folder" > "${folder}/eval_lin_pipe.log" &
done

wait `jobs -p`
