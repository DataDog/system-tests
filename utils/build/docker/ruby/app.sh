#!/bin/bash

exec_puma() {
    bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1
}

exec_rails() {
    exec rails server -p 7777 -b 0.0.0.0
}

SERVER=${1:-PUMA}

if [ $SCENARIO = "PUMA" ]; then
    exec_puma()

if [ $SCENARIO = "RAILS" ]; then
    exec_rails()
