#!/bin/bash

exec_puma() {
    bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1
}

exec_rails() {
    exec rails server -p 7777 -b 0.0.0.0
}

exec_thin() {
    bundle exec thin start -p 7777
}

bash /system-tests/utils/scripts/configure-container-options.sh

SERVER=${1:-PUMA}

if [ $SCENARIO = "PUMA" ]; then
    exec_puma()

if [ $SCENARIO = "RAILS" ]; then
    exec_rails()

if [ $SCENARIO = "THIN" ]; then
    exec_thin()
