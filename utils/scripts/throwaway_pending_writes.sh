#!/bin/bash
# Throwaway (do not merge): leave writes pending on the root filesystem, flushed slowly for a while.
#
# The data is written by a service limited to <bandwidth> of disk writes. For <seconds>, its pending writes
# are flushed at this bandwidth, and anything that syncs the root filesystem waits for them. Then the service
# exits, and what is left is flushed at full speed.
#
# usage: throwaway_pending_writes.sh <size in MB> <bandwidth, e.g. 10M> <seconds>
set -euo pipefail

size_mb=${1:?size in MB}
bandwidth=${2:?bandwidth}
duration=${3:?seconds}

# not /tmp: it's a tmpfs on ubuntu-26.04
file=/var/tmp/pending-writes
done_marker=/var/tmp/pending-writes.done
sudo rm -f "$file" "$done_marker"

sudo systemd-run --unit=pending-writes --collect --property="IOWriteBandwidthMax=/var/tmp $bandwidth" \
    /bin/bash -c "dd if=/dev/zero of=$file bs=1M count=$size_mb status=none && touch $done_marker && sleep $duration"

# dd only fills the page cache: it's quick
for _ in $(seq 120); do
    [ -f "$done_marker" ] && break
    sleep 0.5
done
if [ ! -f "$done_marker" ]; then
    echo "dd did not complete"
    sudo systemctl status pending-writes --no-pager || true
    exit 1
fi

echo "$(date -u +%H:%M:%S) ${size_mb}MB written, flushed at $bandwidth for ${duration}s"
echo "io.max: $(cat /sys/fs/cgroup/system.slice/pending-writes.service/io.max)"
grep -E "^(Dirty|Writeback):" /proc/meminfo
