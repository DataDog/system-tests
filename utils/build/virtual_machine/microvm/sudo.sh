#!/bin/bash
# shellcheck disable=SC2068
#Mock the sudo. Krunvm does not have sudo installed
#We use this script to avoid changing the provision scripts
command $@
