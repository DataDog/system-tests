#!/bin/bash

export ATTEMPT=1
for (( ; ATTEMPT<=${SYSTEM_TEST_BUILD_ATTEMPTS:=1}; ATTEMPT++ ))
do
    echo "== Run build script (attempt $i on $ATTEMPT) =="
    ./utils/build/build.sh "$@"
    if [ $? -eq 0 ]
    then
        exit 0
    fi
done

echo "Build step failed after $ATTEMPT attempts"
exit 1
