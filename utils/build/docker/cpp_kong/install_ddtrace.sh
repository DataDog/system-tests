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
      -DDD_TRACE_BUILD_C_BINDING=ON \
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
      -DDD_TRACE_BUILD_C_BINDING=ON \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_CXX_FLAGS="-Wno-error=unused-variable"
  cmake --build build --target dd_trace_c -j"$(nproc)"
  cp build/binding/c/libdd_trace_c.so "$DEST"
  cd /binaries

else
  # The C binding is on main but not yet in a release.  Once a release
  # ships with it, switch to get_latest_release.
  DD_TRACE_CPP_BRANCH="${DD_TRACE_CPP_BRANCH:-main}"
  echo "Build libdd_trace_c.so from dd-trace-cpp branch ${DD_TRACE_CPP_BRANCH}"
  git clone --depth 1 --branch "$DD_TRACE_CPP_BRANCH" \
      https://github.com/DataDog/dd-trace-cpp.git dd-trace-cpp
  cd dd-trace-cpp
  cmake -S . -B build \
      -DDD_TRACE_BUILD_C_BINDING=ON \
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
KONG_IS_RELEASE=false

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
  TAG=$(get_latest_release "DataDog/kong-plugin-ddtrace")
  echo "Installing kong-plugin-ddtrace from latest release ${TAG}"
  curl -sL "https://github.com/DataDog/kong-plugin-ddtrace/archive/refs/tags/${TAG}.tar.gz" \
      | tar -xz
  mv "kong-plugin-ddtrace-${TAG#v}" kong-plugin-ddtrace
  KONG_IS_RELEASE=true
fi

# ---------------------------------------------------------------------------
# 3. Determine plugin version and write metadata
# ---------------------------------------------------------------------------
PLUGIN_VERSION=$(grep -oP 'VERSION\s*=\s*"\K[^"]+' \
    kong-plugin-ddtrace/kong/plugins/ddtrace/handler.lua)

if [ "$KONG_IS_RELEASE" = "false" ]; then
  COMMIT_SHA=""
  # Prefer local git SHA when the plugin source has a .git directory
  if [ -d kong-plugin-ddtrace/.git ]; then
    COMMIT_SHA=$(git -C kong-plugin-ddtrace rev-parse --short=7 HEAD 2>/dev/null || true)
  fi
  # Fall back to the GitHub API for the latest commit on main
  if [ -z "$COMMIT_SHA" ]; then
    auth_header=$(get_authentication_header)
    COMMIT_SHA=$(eval "curl --silent --fail --retry 3 $auth_header \
        https://api.github.com/repos/DataDog/kong-plugin-ddtrace/commits/main" \
        | grep '"sha"' | head -1 | cut -d'"' -f4 | cut -c1-7)
  fi
  if [ -n "$COMMIT_SHA" ]; then
    PLUGIN_VERSION="${PLUGIN_VERSION}-dev+${COMMIT_SHA}"
  fi
fi

echo "${PLUGIN_VERSION}" > /builds/SYSTEM_TESTS_LIBRARY_VERSION
printf '{"status":"ok","library":{"name":"cpp_kong","version":"%s"}}' \
    "$PLUGIN_VERSION" > /builds/healthcheck.json

cat /builds/healthcheck.json
echo ""
echo "Kong plugin version: ${PLUGIN_VERSION}"
