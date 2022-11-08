#!/bin/bash

ATTEMPT=1
ARGS=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -a|--attempt) ATTEMPT="$2"; shift ;;
        *) ARGS+="$1 ";;
    esac
    shift
done

for (( i=1; i<=$ATTEMPT; i++ ))
do
    echo "== Run build script (attempt $i on $ATTEMPT) =="
    ./utils/build/build.sh $ARGS
    if [ $? -eq 0 ]
    then
        exit 0
    fi
done
