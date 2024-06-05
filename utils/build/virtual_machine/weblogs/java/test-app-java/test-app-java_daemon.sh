#!/bin/bash -e

# This script is used to start, stop, and restart the test-app-nodejs service

NAME=system-tests_weblog
DIR=/home/datadog
PIDFILE=/home/datadog/$NAME.pid
STOP_SIGNAL=INT
USER=datadog
LOG=/shared_volume/std.out


common_opts="--quiet --chuid $USER --pidfile $PIDFILE"

do_start(){
    start-stop-daemon --start $common_opts --chdir $DIR --make-pidfile --background --startas /bin/bash -- -c "DD_APM_INSTRUMENTATION_DEBUG=true DD_APM_INSTRUMENTATION_OUTPUT_PATHS=/shared_volume/std.out java -Dserver.port=5985 -jar k8s-lib-injection-app-0.0.1-SNAPSHOT.jar >> $LOG 2>&1"
}

do_stop(){
    opt=${@:-}
    process=$(cat $PIDFILE)
    echo $((process+1)) > $PIDFILE
    cat $PIDFILE
    start-stop-daemon --stop $common_opts --signal $STOP_SIGNAL --oknodo $opt --remove-pidfile
}

do_status(){
    start-stop-daemon --status $common_opts && exit_status=$? || exit_status=$?
    echo asdf $exit_status
    case "$exit_status" in
        0)
            echo "Program '$NAME' is running."
            ;;
        1)
            echo "Program '$NAME' is not running and the pid file exists."
            ;;
        3)
            echo "Program '$NAME' is not running."
            ;;
        4)
            echo "Unable to determine program '$NAME' status."
            ;;
    esac
}

case "$1" in
  status)
        do_status
        ;;
  start)
        echo -n "Starting daemon: "$NAME
        do_start
        echo "."
        ;;
  stop)
        echo -n "Stopping daemon: "$NAME
        do_stop
        echo "."
        ;;
  restart)
        echo -n "Restarting daemon: "$NAME
        do_stop --retry 30
        do_start
        echo "."
        ;;
  *)
        echo "Usage: "$1" {status|start|stop|restart}"
        exit 1
esac

exit 0