#!/bin/bash

dir=$1
count=$2

python3 train_word_lin.py "${dir}/train.src.bin" "${dir}/train.tgt.conllu" "${dir}/r${count}.lin" --iterations 500 --count "$count"