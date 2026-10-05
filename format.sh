#!/bin/bash
set -eu

readonly CYAN='\033[0;36m'
readonly NC='\033[0m'
readonly WHITE_BOLD='\033[1;37m'

print_usage() {
    echo -e "${WHITE_BOLD}DESCRIPTION${NC}"
    echo -e "  Try to fix everything that can be fixed to make the system-tests CI happy."
    echo
    echo -e "${WHITE_BOLD}USAGE${NC}"
    echo -e "  ./format.sh [options...]"
    echo
    echo -e "${WHITE_BOLD}OPTIONS${NC}"
    echo -e "  ${CYAN}--check${NC}     Only performs checks without modifying files. Command unsed in the CI."
    echo -e "  ${CYAN}--help${NC}      Prints this message and exits."
    echo
}

COMMAND=fix

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -c|--check) COMMAND=check ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Invalid argument: ${1:-}"; echo; print_usage; exit 1 ;;
    esac
    shift
done

if [[ -z "${IN_NIX_SHELL:-}" ]]; then
  if [ ! -d "venv/" ]; then
    echo "Runner is not installed, installing it (ETA 60s)"
    ./build.sh -i runner
  elif ! diff requirements.txt venv/requirements.txt; then
    ./build.sh -i runner
  fi

  source venv/bin/activate
fi

echo "Running mypy type checks..."
if ! mypy --config pyproject.toml; then
  echo "Mypy type checks failed. Please fix the errors above. 💥 💔 💥"
  exit 1
fi

echo "Running import policy checks..."
if ! lint-imports; then
  echo "Import policy checks failed. Please fix the errors above. 💥 💔 💥"
  exit 1
fi

echo "Running ruff formatter..."
if [ "$COMMAND" == "fix" ]; then
  ruff format
else
  ruff format --check --diff
fi

if [ "$COMMAND" == "fix" ]; then
  ruff_args="--fix"
else
  ruff_args=""
fi

if ! ruff check $ruff_args; then
  echo "ruff checks failed. Please fix the errors above. 💥 💔 💥"
  exit 1
fi

echo "Checking trailing whitespaces..."
INCLUDE_PATTERN='.*\.(md|yml|yaml|sh|cs|Dockerfile|java|sql|ts|js|php)$'
EXCLUDE_PATTERN='utils/build/virtual_machine|/node_modules/'
# Check all files tracked by git, and matching include/exclude patterns
FILES="$(git ls-files | grep -v -E "$EXCLUDE_PATTERN" | grep -E "$INCLUDE_PATTERN" | while read f ; do grep -l ' $' "$f" || true ; done)"

# shim for sed -i on GNU sed (Linux) and BSD sed (macOS)
_sed_i() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' -r "$@"
  else
    sed -i "$@"
  fi
}

if [ "$COMMAND" == "fix" ]; then
  echo "$FILES" | while read file ; do
    if [[ -n "$file" ]]; then
      echo "Fixing $file"
      _sed_i 's/  *$//g' "$file"
    fi
  done
else
  if [ -n "$FILES" ]; then
    echo "Some trailing white spaces has been found, please fix them 💥 💔 💥"
    echo "$FILES"
    exit 1
  fi
fi

echo "Running yamlfmt checks..."
YAMLFMT_VERSION="0.21.0"

if [[ -n "${IN_NIX_SHELL:-}" ]]; then
  # yamlfmt is provided (and version-pinned) by the nix flake, use it as-is
  YAMLFMT_BIN="$(which yamlfmt)"
else
  YAMLFMT_BIN="$PWD/venv/bin/yamlfmt"

  if [ -x "$YAMLFMT_BIN" ]; then
    YAMLFMT_INSTALLED_VERSION="$("$YAMLFMT_BIN" -version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
    if [ "$YAMLFMT_INSTALLED_VERSION" != "$YAMLFMT_VERSION" ]; then
      echo "$YAMLFMT_BIN is version $YAMLFMT_INSTALLED_VERSION, expected $YAMLFMT_VERSION, reinstalling it"
      rm -f "$YAMLFMT_BIN"
    fi
  fi

  if [ ! -x "$YAMLFMT_BIN" ]; then
    echo "yamlfmt is not installed, installing it (ETA 5s)"

    YAMLFMT_OS=""
    case "$(uname -s)" in
      Darwin) YAMLFMT_OS="Darwin" ;;
      Linux) YAMLFMT_OS="Linux" ;;
      CYGWIN*|MINGW*|MSYS*) YAMLFMT_OS="Windows" ;;
      *) echo "Unsupported OS"; return 1 ;;
    esac

    YAMLFMT_ARCH=""
    case "$(uname -m)" in
      arm64|aarch64) YAMLFMT_ARCH="arm64" ;;
      x86_64) YAMLFMT_ARCH="x86_64" ;;
      i386|i686) YAMLFMT_ARCH="i386" ;;
      *) echo "Unsupported architecture"; return 1 ;;
    esac

    YAMLFMT_SHA256=""
    case "${YAMLFMT_OS}_${YAMLFMT_ARCH}" in
      Darwin_arm64)   YAMLFMT_SHA256="4b417ecb94339d57e4c122ecc948c1a00fe328b5853266de9806e652a92858fa" ;;
      Darwin_x86_64)  YAMLFMT_SHA256="060e943bcb8583c456810eb1ff4721b4f46c4a0c1a4432449d5dc3bbfe29a22b" ;;
      Linux_arm64)    YAMLFMT_SHA256="5b2689c963b177271330c5ce8ca7396751107e5a826be46f03d2cb9b6f0c7784" ;;
      Linux_i386)     YAMLFMT_SHA256="c559e93f2a0d12c063b6c989d612318146cc92ea47f44eba8b265f814e008dcd" ;;
      Linux_x86_64)   YAMLFMT_SHA256="1f300d9257b232bb3b541d7fb1b0e6b3c121bcbab381c86cd38cb8722be8a566" ;;
      Windows_arm64)  YAMLFMT_SHA256="c1e64d1c72ca8986bc5b8c8edd4ec89f0627804e7e08f8de9f4b484cb5cad897" ;;
      Windows_i386)   YAMLFMT_SHA256="3bc1faface507713109a608cf8812d3f46d2d722dda5ab1f9fe99a203985b952" ;;
      Windows_x86_64) YAMLFMT_SHA256="07f80ce5d741eb4b0a9380ac78a19c7cb5bd44e2a9a47a5a04839e3ba54dd463" ;;
      *) echo "No known checksum for ${YAMLFMT_OS}_${YAMLFMT_ARCH}"; return 1 ;;
    esac

    YAMLFMT_URL="https://github.com/google/yamlfmt/releases/download/v${YAMLFMT_VERSION}/yamlfmt_${YAMLFMT_VERSION}_${YAMLFMT_OS}_${YAMLFMT_ARCH}.tar.gz"
    curl -Lo "$YAMLFMT_BIN.tar.gz" "$YAMLFMT_URL"

    # Validate checksum of downloaded archive
    if command -v sha256sum > /dev/null; then
      echo "$YAMLFMT_SHA256 *$YAMLFMT_BIN.tar.gz" | sha256sum --check --strict
    elif command -v shasum > /dev/null; then
      echo "$YAMLFMT_SHA256 *$YAMLFMT_BIN.tar.gz" | shasum -a 256 --check --strict
    else
      echo "ERROR: no sha256sum or shasum found, cannot verify download"; return 1
    fi

    tar -xzf "$YAMLFMT_BIN.tar.gz" -C "$PWD"/venv/bin/
    chmod +x "$YAMLFMT_BIN"
  fi
fi

echo "Running yamlfmt formatter..."
if [ "$COMMAND" == "fix" ]; then
 "$YAMLFMT_BIN" manifests/
else
 "$YAMLFMT_BIN" -lint manifests/
fi

echo "Running yamllint checks..."
if ! yamllint -s manifests/ utils/ci/gitlab/ .gitlab-ci.yml; then
  echo "yamllint checks failed. Please fix the errors above. 💥 💔 💥"
  exit 1
fi

echo "Running parser checks..."
if [ "$COMMAND" == "fix" ]; then
    if ! python utils/manifest/format.py; then
      echo "Manifest parser failed. Please fix the errors above. 💥 💔 💥"
      exit 1
    fi
else
    if ! python utils/manifest/validate.py; then
      echo "Manifest parser failed. Please fix the errors above. 💥 💔 💥"
      exit 1
    fi
fi

echo "Checking AI Guard redaction fixtures..."
# The redaction scenarios and their VCR cassettes are generated together, and the cassettes are
# addressed by a hash of the request body: editing one side by hand silently stops the mock backend
# from ever matching the requests the tests send. The generator is deterministic, so it can report
# drift on its own; --check compares against the files it owns without writing any of them.
if [ "$COMMAND" == "check" ]; then
  gen_redaction_args="--check"
else
  gen_redaction_args=""
fi

if ! gen_redaction_output="$(python utils/scripts/gen_redaction_cassettes.py $gen_redaction_args 2>&1)"; then
  echo "$gen_redaction_output"
  echo "AI Guard redaction fixtures are out of date or invalid. Regenerate them with"
  echo "python utils/scripts/gen_redaction_cassettes.py 💥 💔 💥"
  exit 1
fi

echo "Running shellcheck checks..."
if ! ./utils/scripts/shellcheck.sh; then
  echo "shellcheck checks failed. Please fix the errors above. 💥 💔 💥"
  exit 1
fi

echo "Running Node.js linters"
# currently only fastify requires linting
# this can be added later
nodejs_dirs=("express" "fastify")

for dir in "${nodejs_dirs[@]}"; do

  docker run \
    --rm \
    -w /app \
    -v "$PWD"/utils/build/docker/nodejs/"$dir":/app \
    -e NODE_NO_WARNINGS=1 \
    node:18-alpine \
    sh -c "npm install --silent && npm run --silent ${COMMAND}_lint"

  if [ $? -ne 0 ]; then
    echo "$dir linter failed. Please fix the errors above. 💥 💔 💥"
    exit 1
  fi
done

echo "All good, the system-tests CI will be happy! ✨ 🍰 ✨"
