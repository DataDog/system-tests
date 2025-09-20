#!/usr/bin/env bash

perl -pi -e 's/^(\s*)(.*\*r.*)(#.*)$/$1$3\n$1$2/' manifests/*.yml
perl -pi -e 's/^(\s*)(- &ref.*)(#.*)$/$1$3\n$1$2/' manifests/*.yml
python ./utils/scripts/activate-easy-wins.py "$@"
./format.sh


