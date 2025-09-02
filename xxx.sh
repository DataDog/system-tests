#!/bin/bash


set -eux

for i in {1..100}
do
  echo "Run #$i"
  ./run.sh DEBUGGER_EXPRESSION_LANGUAGE 
done