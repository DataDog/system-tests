#!/bin/sh
# RHEL 8 gives Java 8 a higher alternatives priority than Java 11, so javac can be 11
# while java stays on 8. Corretto also registers the arch-specific directory, and
# alternatives --set rejects the short java-11-amazon-corretto symlink.
set -eu

# Below 11.0.23 the profiler falls back to JFR OldObjectSample, which crashes the JVM
# (JDK-8236743, never backported to 11). EOL distros (Fedora 36: 11.0.19) ship older builds.
readonly MIN_JAVA11_UPDATE=23

java11_home=""
# Fedora installs java-11-openjdk without a version suffix, RHEL/Ubuntu add one,
# Corretto uses the arch-specific java-11-amazon-corretto.<arch> (or our tarball fallback).
for candidate in \
    /usr/lib/jvm/java-11-amazon-corretto.tarball \
    /usr/lib/jvm/java-11-amazon-corretto.* \
    /usr/lib/jvm/java-11-openjdk* \
    /usr/lib/jvm/java-11-amazon-corretto* \
    /usr/lib/jvm/java-11; do
    if [ -x "$candidate/bin/java" ] && [ -x "$candidate/bin/javac" ]; then
        java11_home=$candidate
        break
    fi
done

if [ -z "$java11_home" ]; then
    echo "Java 11 JDK not found under /usr/lib/jvm" >&2
    ls -ld /usr/lib/jvm/* >&2 || true
    exit 1
fi

if command -v readlink >/dev/null 2>&1; then
    resolved=$(readlink -f "$java11_home" || true)
    if [ -n "$resolved" ] && [ -x "$resolved/bin/java" ] && [ -x "$resolved/bin/javac" ]; then
        java11_home=$resolved
    fi
fi

if command -v alternatives >/dev/null 2>&1; then
    alt_cmd=alternatives
else
    alt_cmd=update-alternatives
fi

sudo "$alt_cmd" --set java "$java11_home/bin/java" \
    || sudo "$alt_cmd" --install /usr/bin/java java "$java11_home/bin/java" 2000000000 \
    || true
sudo "$alt_cmd" --set java "$java11_home/bin/java" || true
sudo "$alt_cmd" --set javac "$java11_home/bin/javac" \
    || sudo "$alt_cmd" --install /usr/bin/javac javac "$java11_home/bin/javac" 2000000000 \
    || true
sudo "$alt_cmd" --set javac "$java11_home/bin/javac" || true

# Later SSH steps and the weblog service call "java" from a PATH that includes
# /usr/bin and may not include /usr/local/bin. Point both names at this JDK.
sudo ln -sfn "$java11_home/bin/java" /usr/local/bin/java
sudo ln -sfn "$java11_home/bin/javac" /usr/local/bin/javac
sudo ln -sfn "$java11_home/bin/java" /usr/bin/java
sudo ln -sfn "$java11_home/bin/javac" /usr/bin/javac

export PATH="$java11_home/bin:/usr/local/bin:/usr/bin:${PATH:-/bin}"

echo "Selected Java 11 home: $java11_home"
echo "java=$(command -v java)"
echo "javac=$(command -v javac)"
java -version
javac -version

java_version=$(java -version 2>&1)
javac_version=$(javac -version 2>&1)
printf '%s\n' "$java_version" | grep -q 'version "11\.'
printf '%s\n' "$javac_version" | grep -q '11\.'

java_update=$(printf '%s\n' "$java_version" | sed -n 's/.*version "11\.0\.\([0-9]*\).*/\1/p' | head -n 1)
if [ "${java_update:-0}" -lt "$MIN_JAVA11_UPDATE" ]; then
    if [ "$java11_home" = /usr/lib/jvm/java-11-amazon-corretto.tarball ]; then
        echo "Corretto 11 tarball is 11.0.${java_update:-0}, expected 11.0.${MIN_JAVA11_UPDATE}+" >&2
        exit 1
    fi
    echo "Java 11.0.${java_update:-0} is older than 11.0.${MIN_JAVA11_UPDATE}: installing the Corretto 11 tarball"
    sh "$(dirname "$0")/install_corretto11.sh"
    exec sh "$0"
fi
