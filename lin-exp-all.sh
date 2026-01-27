#!/bin/bash

tb="$1"

function run_settings() {
    log="lin-exp-data/$tb.$1.$2.$3.log"
    bash lin-exp.sh "$tb" "$2" "$1" "$3" > "$log"
    out=$(tail -n1 "$log")
    echo "$tb & $1 & $2 $out"
}

echo "Tree"
run_settings jap 50 tree
run_settings jap 100 tree
run_settings jap 200 tree
run_settings tur 50 tree
run_settings tur 100 tree
run_settings tur 200 tree
run_settings sjo 50 tree
run_settings sjo 100 tree
run_settings sjo 200 tree
echo "Word"
run_settings jap 50 word
run_settings jap 100 word
run_settings jap 200 word
run_settings tur 50 word
run_settings tur 100 word
run_settings tur 200 word
run_settings sjo 50 word
run_settings sjo 100 word
run_settings sjo 200 word
