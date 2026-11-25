#!/bin/bash
# Payara Micro 5 sometimes fails its own boot, before the app is deployed: a NullPointerException in
# TransactionServiceConfigListener.postConstruct (a race in Payara's parallel startup threads; the code
# is unchanged up to Payara 6), then "BootstrapException: ... Server failed to start". It happens in
# about 1 boot out of 10,000, and fails the whole scenario. Restart Payara once on that failure.
# Any other exit is passed through unchanged, and a failure that happens again on the restart still
# fails the scenario.
set -u -o pipefail

PAYARA_STDERR=/tmp/payara-stderr.log
PAYARA_PID=/tmp/payara.pid
STOPPING=false

# Like `exec java`: docker's stop signal goes to Payara, so it shuts down gracefully (tracer flush).
# shellcheck disable=SC2329 # invoked by the traps below
forward_signal() {
    STOPPING=true
    if [ -f "$PAYARA_PID" ]; then
        kill -s "$1" "$(cat "$PAYARA_PID")" 2>/dev/null || true
    fi
}
trap 'forward_signal TERM' TERM
trap 'forward_signal INT' INT

exec 3>&1

run_payara() {
    rm -f "$PAYARA_PID"
    # stdout goes to the container's stdout as is; stderr goes to the container's stderr and to $PAYARA_STDERR
    # shellcheck disable=SC2016,SC2086
    sh -c 'echo $$ > "$0" && exec "$@"' "$PAYARA_PID" \
        java -Xmx362m -javaagent:/app/dd-java-agent.jar -jar /app/payara-micro.jar \
        --addlibs /app/stax2-api-4.2.1.jar --deploy /app/app.war ${APP_EXTRA_ARGS:-} \
        2>&1 >&3 3>&- | tee "$PAYARA_STDERR" >&2 &

    local status
    wait %%
    status=$?
    # a forwarded signal interrupts `wait`: wait again until Payara has exited
    while [ -n "$(jobs -r)" ]; do
        wait %%
        status=$?
    done
    return "$status"
}

run_payara
status=$?

if [ "$STOPPING" = false ] && grep -q "BootstrapException" "$PAYARA_STDERR" && grep -q "Server failed to start" "$PAYARA_STDERR"; then
    echo "app-payara.sh: Payara Micro failed to boot (exit code $status), restarting it once" >&2
    run_payara
    status=$?
fi

exit "$status"
