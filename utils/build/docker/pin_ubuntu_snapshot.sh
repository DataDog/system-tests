#!/bin/sh
# Pins apt to a snapshot, corresponding to last apt command.
# In a Docker image, this should ensure that the snapshot is not older than
# the base image, and it would also be close to the state of the repository
# when the image was built, minimizing any unneeded upgrade.
# See: https://snapshot.ubuntu.com/
set -eu

if [ ! -f /var/log/apt/history.log ]; then
  echo "Cannot pin Ubuntu Snapshot: /var/log/apt/history.log not found"
  exit 1
fi

SNAPSHOT_ID="$(date -d"$(grep 'End-Date' /var/log/apt/history.log | tail -n 1 | awk '{ print $2" "$3 }')" +%Y%m%dT%H%M%SZ)"
echo 'APT::Snapshot "'"${SNAPSHOT_ID}"'";' > /etc/apt/apt.conf.d/50snapshot
echo "Pinned Ubuntu Snapshot ${SNAPSHOT_ID}"
