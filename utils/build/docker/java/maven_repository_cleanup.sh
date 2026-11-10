#!/bin/bash
# Removes from a maven local repository the files that offline builds never read, to make base images lighter.
# It keeps maven-metadata-*.xml files: offline builds need them to resolve version ranges (e.g. dd-trace-api).
# Must run in the same RUN instruction as the build that filled the repository, otherwise the layer does not shrink.

set -eu

repository="$1"

size() {
    du -s --apparent-size --block-size=1K "$repository" | cut -f1
}

before=$(size)

find "$repository" -type f \( \
    -name '*.lastUpdated' \
    -o -name '_remote.repositories' \
    -o -name 'resolver-status.properties' \
    -o -name '*.sha1' -o -name '*.md5' -o -name '*.sha256' -o -name '*.sha512' \
    \) -delete
find "$repository" -type d -empty -delete
rm -rf /tmp/* /root/.cache

after=$(size)

echo "Maven repository cleanup: ${before}KB -> ${after}KB (saved $((before - after))KB)"
