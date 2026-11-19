#!/bin/bash
# Throwaway (do not merge): leave writes pending on the root filesystem, flushed slowly for a while.
#
# The data is written by a service limited to <bandwidth> of disk writes: its pending writes are flushed at this
# bandwidth, and anything that syncs the root filesystem waits for them. After <seconds>, the service is stopped,
# and what is left is flushed at full speed.
#
# usage: throwaway_pending_writes.sh <size in MB> <bandwidth, e.g. 10M> <seconds>
set -euo pipefail

size_mb=${1:?size in MB}
bandwidth=${2:?bandwidth}
duration=${3:?seconds}

# not /tmp: it's a tmpfs on ubuntu-26.04
file=/var/tmp/pending-writes
sudo rm -f "$file"

sudo systemd-run --unit=pending-writes --collect --property="IOWriteBandwidthMax=/var/tmp $bandwidth" \
    /bin/bash -c "dd if=/dev/zero of=$file bs=1M count=$size_mb status=none; sleep infinity"
sudo systemd-run --unit=pending-writes-stop --collect --on-active="$duration" systemctl stop pending-writes.service
echo "$(date -u +%H:%M:%S) writing ${size_mb}MB, flushed at $bandwidth until $(date -u -d "+$duration sec" +%H:%M:%S)"
echo "io.max: $(cat /sys/fs/cgroup/system.slice/pending-writes.service/io.max)"

dirty_mb() {
    awk '/^Dirty:/ { printf "%d", $2 / 1024 }' /proc/meminfo
}

# wait until most of the data is pending, for at most 30s
for _ in $(seq 6); do
    echo "$(date -u +%H:%M:%S) $(grep -E '^(Dirty|Writeback):' /proc/meminfo | tr -s ' ' | tr '\n' ' ')"
    [ "$(dirty_mb)" -ge $((size_mb * 7 / 10)) ] && break
    sleep 5
done
