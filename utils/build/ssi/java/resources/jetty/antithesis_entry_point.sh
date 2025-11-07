#!/usr/bin/env bash
set -euo pipefail

LIB_DIR="/opt/datadog-packages/datadog-apm-library-java/1.55.0"
# Construye el boot classpath: el directorio + todos los .jar excepto el agente
BOOT_EXTRA="$LIB_DIR"
while IFS= read -r -d '' J; do
  BOOT_EXTRA="${BOOT_EXTRA}:$J"
done < <(find "$LIB_DIR" -maxdepth 1 -type f -name '*.jar' ! -name 'dd-java-agent.jar' -print0)

echo "Listing $LIB_DIR"
ls -la $LIB_DIR
echo "The boot extra is $BOOT_EXTRA"
echo "Listing /workdir"
ls -la /workdir
echo "Listing /workdir/jetty-classpath"
ls -la /workdir/jetty-classpath
echo "Listing .jar files in /workdir"
ls -la /workdir/*.jar
exec java -Xbootclasspath/a:"$BOOT_EXTRA" -cp "/workdir/*:/workdir/jetty-classpath/*:." -Ddd.trace.classes.exclude=com.antithesis.*,com.antithesis.ffi.* JettyServletMain