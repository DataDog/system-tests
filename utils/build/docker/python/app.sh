#!/bin/bash

set -eu

exec_gunicorn() {
    ddtrace-run gunicorn -w 2 -b 0.0.0.0:7777 app:app
}

exec_gunicorn_w_gevent() {
    ddtrace-run gunicorn -w 2 -b 0.0.0.0:7777 --access-logfile - app:app -k gevent
}

exec_uwsgi() { 
    # note, only thread mode is supported
    # https://ddtrace.readthedocs.io/en/stable/advanced_usage.html#uwsgi
    ddtrace-run uwsgi --http :7777 -w app:app --enable-threads
}

bash /system-tests/utils/scripts/configure-container-options.sh

SCENARIO=${1:-GUNICORN}

if [ $SCENARIO = "GUNICORN" ]; then
    exec_gunicorn()
elif [ $SCENARIO = "GUNICORN_W_GEVENT" ]; then
    exec_gunicorn_w_gevent()
elif [ $SCENARIO = "UWSGI" ]; then
    exec_uwsgi()
fi
