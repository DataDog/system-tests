#!/bin/bash
set -eu

# shellcheck source=/dev/null
source "$(dirname "$0")/github.sh"

cd /binaries

# ---------------------------------------------------------------------------
# 1. Build or install libdd_trace_c.so
# ---------------------------------------------------------------------------
DEST=/usr/local/lib/libdd_trace_c.so

if [ -f libdd_trace_c.so ]; then
  echo "Install libdd_trace_c.so from binaries/"
  cp libdd_trace_c.so "$DEST"

elif [ -d dd-trace-cpp ]; then
  echo "Build libdd_trace_c.so from local binaries/dd-trace-cpp"
  cd dd-trace-cpp
  cmake -S . -B build \
      -DBUILD_C_BINDING=ON \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_CXX_FLAGS="-Wno-error=unused-variable"
  cmake --build build --target dd_trace_c -j"$(nproc)"
  cp build/binding/c/libdd_trace_c.so "$DEST"
  cd /binaries

elif [ -f cpp-load-from-git ]; then
  echo "Build libdd_trace_c.so from cpp-load-from-git"
  TARGET=$(cat cpp-load-from-git)
  URL=$(echo "$TARGET" | cut -d "@" -f 1)
  BRANCH=$(echo "$TARGET" | cut -d "@" -f 2)
  git clone --depth 1 --branch "$BRANCH" "$URL" dd-trace-cpp
  cd dd-trace-cpp
  cmake -S . -B build \
      -DBUILD_C_BINDING=ON \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_CXX_FLAGS="-Wno-error=unused-variable"
  cmake --build build --target dd_trace_c -j"$(nproc)"
  cp build/binding/c/libdd_trace_c.so "$DEST"
  cd /binaries

else
  # The C binding is currently on the dmehala/c-binding branch, not in any
  # release yet.  Once it merges and ships in a release, switch back to
  # get_latest_release.
  DD_TRACE_CPP_BRANCH="${DD_TRACE_CPP_BRANCH:-dmehala/c-binding}"
  echo "Build libdd_trace_c.so from dd-trace-cpp branch ${DD_TRACE_CPP_BRANCH}"
  git clone --depth 1 --branch "$DD_TRACE_CPP_BRANCH" \
      https://github.com/DataDog/dd-trace-cpp.git dd-trace-cpp
  cd dd-trace-cpp
  cmake -S . -B build \
      -DBUILD_C_BINDING=ON \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_CXX_FLAGS="-Wno-error=unused-variable"
  cmake --build build --target dd_trace_c -j"$(nproc)"
  cp build/binding/c/libdd_trace_c.so "$DEST"
  cd /binaries
fi

# ---------------------------------------------------------------------------
# 2. Get Kong plugin files
# ---------------------------------------------------------------------------
rock_file=""
for f in kong-plugin-ddtrace*.rock; do
  if [ -e "$f" ]; then
    rock_file="$f"
    break
  fi
done

if [ -n "$rock_file" ]; then
  echo "Extracting Kong plugin from .rock artifact: ${rock_file}"
  mkdir -p kong-rock-extract
  unzip -o "${rock_file}" -d kong-rock-extract
  # The .src.rock contains a nested source archive (e.g. tip.zip).
  for inner_zip in kong-rock-extract/*.zip; do
    if [ -e "$inner_zip" ]; then
      unzip -o "$inner_zip" -d kong-rock-extract
      break
    fi
  done
  for extracted_dir in kong-rock-extract/kong-plugin-ddtrace-*/; do
    if [ -d "$extracted_dir" ]; then
      mv "$extracted_dir" kong-plugin-ddtrace
      break
    fi
  done
  rm -rf kong-rock-extract

elif [ -d kong-plugin-ddtrace ]; then
  echo "Using Kong plugin from binaries/kong-plugin-ddtrace"

else
  KONG_PLUGIN_BRANCH="${KONG_PLUGIN_BRANCH:-main}"
  echo "Cloning kong-plugin-ddtrace branch ${KONG_PLUGIN_BRANCH}"
  git clone --depth 1 --branch "$KONG_PLUGIN_BRANCH" \
      https://github.com/DataDog/kong-plugin-ddtrace.git kong-plugin-ddtrace
fi

# ---------------------------------------------------------------------------
# 3. Determine plugin version and write metadata
# ---------------------------------------------------------------------------
PLUGIN_VERSION=$(grep -oP 'VERSION\s*=\s*"\K[^"]+' \
    kong-plugin-ddtrace/kong/plugins/ddtrace/handler.lua)

echo "${PLUGIN_VERSION}" > /builds/SYSTEM_TESTS_LIBRARY_VERSION
printf '{"status":"ok","library":{"name":"cpp_kong","version":"%s"}}' \
    "$PLUGIN_VERSION" > /builds/healthcheck.json

cat /builds/healthcheck.json
echo ""
echo "Kong plugin version: ${PLUGIN_VERSION}"
