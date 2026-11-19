#!/bin/bash
# Throwaway (do not merge): leave writes pending on the root filesystem, that only a sync of the filesystem flushes,
# slowly.
#
# start: the kernel is told to keep dirty pages in memory (no background writeback). A service limited to
#   <bandwidth> of disk writes writes <size> MB: they stay pending, until something syncs the root filesystem, which
#   then waits for them to be written at <bandwidth>.
# stop: drop the pending writes (deleting a file discards its dirty pages), and restore the writeback settings.
#
# usage: throwaway_pending_writes.sh start <size in MB> <bandwidth, e.g. 10M>
#        throwaway_pending_writes.sh stop
set -euo pipefail

# not /tmp: it's a tmpfs on ubuntu-26.04
file=/var/tmp/pending-writes
saved_settings=/var/tmp/pending-writes.sysctl
settings=(vm.dirty_ratio vm.dirty_background_ratio vm.dirty_expire_centisecs vm.dirty_writeback_centisecs)

meminfo() {
    echo "$(date -u +%H:%M:%S.%3N) $(grep -E '^(Dirty|Writeback):' /proc/meminfo | tr -s ' ' | tr '\n' ' ')"
}

case "${1:?start or stop}" in
start)
    size_mb=${2:?size in MB}
    bandwidth=${3:?bandwidth}

    sudo sysctl "${settings[@]}" | sudo tee "$saved_settings" >/dev/null
    sudo sysctl -q -w vm.dirty_ratio=80 vm.dirty_background_ratio=70 vm.dirty_expire_centisecs=360000 \
        vm.dirty_writeback_centisecs=0

    sudo rm -f "$file"
    sudo systemd-run --unit=pending-writes --collect --property="IOWriteBandwidthMax=/var/tmp $bandwidth" \
        /bin/bash -c "dd if=/dev/zero of=$file bs=1M count=$size_mb status=none; sleep infinity"
    echo "io.max: $(cat /sys/fs/cgroup/system.slice/pending-writes.service/io.max)"

    # dd only fills the page cache: wait until most of it is there
    for _ in $(seq 60); do
        [ "$(awk '/^Dirty:/ { printf "%d", $2 / 1024 }' /proc/meminfo)" -ge $((size_mb * 9 / 10)) ] && break
        sleep 0.5
    done
    meminfo
    ;;
stop)
    meminfo
    sudo rm -f "$file"
    sudo systemctl stop pending-writes.service || true
    [ -f "$saved_settings" ] && sudo sysctl -q -p "$saved_settings"
    echo "pending writes dropped"
    meminfo
    ;;
*)
    echo "usage: $0 start <size in MB> <bandwidth> | stop"
    exit 1
    ;;
esac
