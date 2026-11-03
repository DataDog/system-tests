#!/bin/sh
# RHEL 8 gives Java 8 a higher alternatives priority than Java 11, so javac can be 11
# while java stays on 8. Pin both commands to the JDK we just installed.
set -eu

java11_home=""
for candidate in /usr/lib/jvm/java-11-openjdk-* /usr/lib/jvm/java-11-amazon-corretto*; do
    if [ -x "$candidate/bin/java" ] && [ -x "$candidate/bin/javac" ]; then
        java11_home=$candidate
        break
    fi
done

if [ -z "$java11_home" ]; then
    echo "Java 11 JDK not found under /usr/lib/jvm" >&2
    ls -d /usr/lib/jvm/* >&2 || true
    exit 1
fi

if command -v alternatives >/dev/null 2>&1; then
    alt_cmd=alternatives
else
    alt_cmd=update-alternatives
fi

if ! sudo "$alt_cmd" --set java "$java11_home/bin/java"; then
    sudo "$alt_cmd" --install /usr/bin/java java "$java11_home/bin/java" 2000000000
    sudo "$alt_cmd" --set java "$java11_home/bin/java"
fi
if ! sudo "$alt_cmd" --set javac "$java11_home/bin/javac"; then
    sudo "$alt_cmd" --install /usr/bin/javac javac "$java11_home/bin/javac" 2000000000
    sudo "$alt_cmd" --set javac "$java11_home/bin/javac"
fi

sudo ln -sfn "$java11_home/bin/java" /usr/local/bin/java
sudo ln -sfn "$java11_home/bin/javac" /usr/local/bin/javac

echo "Selected Java 11 home: $java11_home"
java -version
javac -version

java_version=$(java -version 2>&1)
javac_version=$(javac -version 2>&1)
printf '%s\n' "$java_version" | grep -q 'version "11\.'
printf '%s\n' "$javac_version" | grep -q '11\.'
