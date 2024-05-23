#!/bin/sh
python manifests/parser/live-checker.py manifests
yamllint manifests/