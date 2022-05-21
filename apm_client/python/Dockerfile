FROM debian:buster-slim

# Parametrize Python version

# http://bugs.python.org/issue19846
# > At the moment, setting "LANG=C" on a Linux system *fundamentally breaks Python 3*, and that's not OK.
ENV LANG C.UTF-8

WORKDIR /client
COPY requirements.txt /client
