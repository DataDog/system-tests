#!/bin/bash

bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1
