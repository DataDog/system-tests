#!/bin/bash
# Throwaway experiment (do not merge): time the first container creations on a fresh runner,
# the way system-tests creates the proxy and the mocked backend.
# usage: throwaway_docker_first_create.sh <output folder>
set -uo pipefail

out=$(realpath -m "${1:?output folder}")
mkdir -p "$out/stacks"
durations="$out/durations.tsv"
: >"$durations"

now() { date +%s.%N; }
log() { echo "$(date -u +%H:%M:%S.%3N) $*" | tee -a "$out/timeline.log"; }

# run a command, and record its duration under a name
timed() {
    local name=$1 start end duration
    shift
    start=$(now)
    "$@" >>"$out/commands.log" 2>&1
    end=$(now)
    duration=$(awk -v s="$start" -v e="$end" 'BEGIN { printf "%.2f", e - s }')
    printf '%s\t%s\n' "$name" "$duration" >>"$durations"
    log "$name: ${duration}s"
}

# while the first create runs: host pressure, blocked processes, and the daemons' goroutine stacks
sample_daemon() {
    local label=$1 marker
    marker=$(mktemp)
    {
        echo "### $label $(date -u +%H:%M:%S.%3N)"
        grep -H . /proc/pressure/cpu /proc/pressure/io /proc/pressure/memory
        ps -eo stat,pid,etime,wchan:32,args | awk 'NR == 1 || $1 ~ /D/'
    } >>"$out/samples.log" 2>&1
    sudo kill -USR1 "$(pidof dockerd)" "$(pidof containerd)"
    sleep 1
    sudo find /var/run/docker -maxdepth 1 -name 'goroutine-stacks-*.log' -newer "$marker" \
        -exec sh -c 'cat "$1" > "$2"' _ {} "$out/stacks/dockerd-$label.log" \;
    rm -f "$marker"
}

create_proxy() {
    docker create --name system-tests-proxy --hostname proxy --network system-tests-ipv4 -w /app \
        -v "$PWD/utils/proxy:/app/proxy:ro" -v "$PWD/logs_exp/interfaces:/app/logs_exp/interfaces" \
        -p 127.0.0.1:11111:11111 datadog/system-tests:proxy-v1 sleep 600
}

create_mocked_backend() {
    docker create --name system-tests-mocked-backend --hostname mocked-backend --network system-tests-ipv4 \
        -w /app -v "$PWD/logs_exp:/app/logs_exp" -p 127.0.0.1::4900 datadog/system-tests:proxy-v1 sleep 600
}

create_other_image() {
    docker create --name system-tests-agent --hostname agent --network system-tests-ipv4 \
        --entrypoint sleep datadog/agent:latest 600
}

mkdir -p logs_exp/interfaces

{
    uptime
    uname -a
    docker version
    docker info
} >"$out/host.txt" 2>&1
log "host uptime: $(uptime)"

timed pull_agent docker pull -q datadog/agent:latest
timed pull_proxy docker pull -q datadog/system-tests:proxy-v1
docker network create system-tests-ipv4 >/dev/null

# the first create of the runner, with two samples while it runs
(sleep 2 && sample_daemon first-create-2s) &
sampler2=$!
(sleep 5 && sample_daemon first-create-5s) &
sampler5=$!
timed 1_create_proxy create_proxy
kill "$sampler2" "$sampler5" 2>/dev/null
timed 1_start_proxy docker start system-tests-proxy

timed 2_create_mocked_backend create_mocked_backend
timed 2_start_mocked_backend docker start system-tests-mocked-backend

timed 3_create_other_image create_other_image
timed 3_start_other_image docker start system-tests-agent

# same thing again on a fresh daemon: is the cost paid once per boot, or once per daemon start?
docker rm -f system-tests-proxy system-tests-mocked-backend system-tests-agent >/dev/null
timed restart_docker sudo systemctl restart docker
timed 4_create_proxy_after_restart create_proxy
timed 4_start_proxy_after_restart docker start system-tests-proxy

wait
sudo journalctl -u docker.service -u containerd.service --since -15min --no-pager 2>&1 | tee "$out/journal.log" >/dev/null
sudo dmesg -T 2>&1 | tee "$out/dmesg.log" >/dev/null
log "done"
