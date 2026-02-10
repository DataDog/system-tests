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

if [ ! -d "venv/" ]; then
  echo "Runner is not installed, installing it (ETA 60s)"
  ./build.sh -i runner
elif ! diff requirements.txt venv/requirements.txt; then
  ./build.sh -i runner
fi

source venv/bin/activate

# Create temp directory for parallel execution output
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Ensure yamlfmt is installed before parallel execution
if ! which yamlfmt > /dev/null; then
  echo "yamlfmt is not installed, installing it (ETA 5s)"
  YAMLFMT_VERSION="0.16.0"

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

  YAMLFMT_URL="https://github.com/google/yamlfmt/releases/download/v${YAMLFMT_VERSION}/yamlfmt_${YAMLFMT_VERSION}_${YAMLFMT_OS}_${YAMLFMT_ARCH}.tar.gz"
  curl -Lo "$PWD"/venv/bin/yamlfmt.tar.gz $YAMLFMT_URL
  tar -xzf "$PWD"/venv/bin/yamlfmt.tar.gz -C "$PWD"/venv/bin/
  chmod +x "$PWD"/venv/bin/yamlfmt
fi

# Function to run mypy type checks
run_mypy() {
  echo "Running mypy type checks..."
  if ! mypy --config pyproject.toml; then
    echo "Mypy type checks failed. Please fix the errors above. 💥 💔 💥"
    return 1
  fi
}

# Function to run ruff formatter
run_ruff_format() {
  echo "Running ruff formatter..."
  if [ "$COMMAND" == "fix" ]; then
    ruff format
  else
    ruff format --check --diff
  fi
}

# Function to run ruff checks
run_ruff_check() {
  if [ "$COMMAND" == "fix" ]; then
    ruff_args="--fix"
  else
    ruff_args=""
  fi

  if ! ruff check $ruff_args; then
    echo "ruff checks failed. Please fix the errors above. 💥 💔 💥"
    return 1
  fi
}

# shim for sed -i on GNU sed (Linux) and BSD sed (macOS)
_sed_i() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' -r "$@"
  else
    sed -i "$@"
  fi
}

# Function to check/fix trailing whitespaces
run_trailing_whitespace() {
  echo "Checking trailing whitespaces..."
  INCLUDE_PATTERN='.*\.(md|yml|yaml|sh|cs|Dockerfile|java|sql|ts|js|php)$'
  EXCLUDE_PATTERN='utils/build/virtual_machine'

  # Optimized parallel grep using xargs
  FILES="$(git ls-files | grep -v -E "$EXCLUDE_PATTERN" | grep -E "$INCLUDE_PATTERN" | xargs -P 4 -I {} grep -l ' $' {} 2>/dev/null || true)"

  if [ "$COMMAND" == "fix" ]; then
    echo "$FILES" | while read -r file ; do
      if [[ -n "$file" ]]; then
        echo "Fixing $file"
        _sed_i 's/  *$//g' "$file"
      fi
    done
  else
    if [ -n "$FILES" ]; then
      echo "Some trailing white spaces has been found, please fix them 💥 💔 💥"
      echo "$FILES"
      return 1
    fi
  fi
}

# Function to run yamlfmt
run_yamlfmt() {
  echo "Running yamlfmt formatter..."
  if [ "$COMMAND" == "fix" ]; then
    yamlfmt manifests/
  else
    yamlfmt -lint manifests/
  fi
}

# Function to run yamllint
run_yamllint() {
  echo "Running yamllint checks..."
  if ! ./venv/bin/yamllint -s manifests/; then
    echo "yamllint checks failed. Please fix the errors above. 💥 💔 💥"
    return 1
  fi
}

# Function to run manifest format/validate
run_manifest() {
  echo "Running parser checks..."
  if [ "$COMMAND" == "fix" ]; then
    if ! python utils/manifest/format.py; then
      echo "Manifest parser failed. Please fix the errors above. 💥 💔 💥"
      return 1
    fi
  else
    if ! python utils/manifest/validate.py; then
      echo "Manifest parser failed. Please fix the errors above. 💥 💔 💥"
      return 1
    fi
  fi
}

# Function to run shellcheck
run_shellcheck() {
  echo "Running shellcheck checks..."
  if ! ./utils/scripts/shellcheck.sh; then
    echo "shellcheck checks failed. Please fix the errors above. 💥 💔 💥"
    return 1
  fi
}

# Function to run Node.js linters
run_nodejs_lint() {
  local dir=$1
  if ! docker run \
    --rm \
    -w /app \
    -v "$PWD"/utils/build/docker/nodejs/"$dir":/app \
    -e NODE_NO_WARNINGS=1 \
    node:18-alpine \
    sh -c "npm install --silent && npm run --silent ${COMMAND}_lint"; then
    echo "$dir linter failed. Please fix the errors above. 💥 💔 💥"
    return 1
  fi
}

# Helper function to monitor and display output progressively
wait_and_display() {
  local pid=$1
  local output_file=$2
  local name=$3
  local start_time=$(date +%s)

  # Show spinner while waiting
  local spin='-\|/'
  local i=0
  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i+1) %4 ))
    printf "\r[${spin:$i:1}] Waiting for %s..." "$name"
    sleep 0.1
  done

  # Get exit status
  wait "$pid"
  local exit_code=$?

  # Calculate duration
  local end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Clear spinner line and show result
  printf "\r\033[K"  # Clear line

  # Display the output
  cat "$output_file"

  # Show completion status with timing
  if [ $exit_code -eq 0 ]; then
    echo "✓ $name completed (${duration}s)"
  else
    echo "✗ $name failed (${duration}s)"
  fi

  return $exit_code
}

# Execute operations based on mode
if [ "$COMMAND" == "check" ]; then
  # Check mode: Run all operations in parallel with progressive output
  run_mypy > "$TEMP_DIR/mypy.out" 2>&1 & pid_mypy=$!
  run_ruff_format > "$TEMP_DIR/ruff_fmt.out" 2>&1 & pid_ruff_format=$!
  run_ruff_check > "$TEMP_DIR/ruff_check.out" 2>&1 & pid_ruff_check=$!
  run_trailing_whitespace > "$TEMP_DIR/whitespace.out" 2>&1 & pid_whitespace=$!
  run_yamlfmt > "$TEMP_DIR/yamlfmt.out" 2>&1 & pid_yamlfmt=$!
  run_yamllint > "$TEMP_DIR/yamllint.out" 2>&1 & pid_yamllint=$!
  run_manifest > "$TEMP_DIR/manifest.out" 2>&1 & pid_manifest=$!
  run_shellcheck > "$TEMP_DIR/shellcheck.out" 2>&1 & pid_shellcheck=$!
  run_nodejs_lint "express" > "$TEMP_DIR/express.out" 2>&1 & pid_express=$!
  run_nodejs_lint "fastify" > "$TEMP_DIR/fastify.out" 2>&1 & pid_fastify=$!

  # Display outputs progressively as operations complete
  FAILED=0

  # Wait for operations in order, displaying output as each completes
  wait_and_display "$pid_mypy" "$TEMP_DIR/mypy.out" "mypy" || FAILED=1
  wait_and_display "$pid_ruff_format" "$TEMP_DIR/ruff_fmt.out" "ruff format" || FAILED=1
  wait_and_display "$pid_ruff_check" "$TEMP_DIR/ruff_check.out" "ruff check" || FAILED=1
  wait_and_display "$pid_whitespace" "$TEMP_DIR/whitespace.out" "trailing whitespace" || FAILED=1
  wait_and_display "$pid_yamlfmt" "$TEMP_DIR/yamlfmt.out" "yamlfmt" || FAILED=1
  wait_and_display "$pid_yamllint" "$TEMP_DIR/yamllint.out" "yamllint" || FAILED=1
  wait_and_display "$pid_manifest" "$TEMP_DIR/manifest.out" "manifest" || FAILED=1
  wait_and_display "$pid_shellcheck" "$TEMP_DIR/shellcheck.out" "shellcheck" || FAILED=1
  echo "Running Node.js linters"
  wait_and_display "$pid_express" "$TEMP_DIR/express.out" "express lint" || FAILED=1
  wait_and_display "$pid_fastify" "$TEMP_DIR/fastify.out" "fastify lint" || FAILED=1

  if [ "$FAILED" -eq 1 ]; then
    exit 1
  fi
else
  # Fix mode: Run dependency chains in parallel with progressive output

  # Chain 1: Python formatting → checking
  (
    run_ruff_format > "$TEMP_DIR/ruff_fmt.out" 2>&1 || exit 1
    run_ruff_check > "$TEMP_DIR/ruff_check.out" 2>&1 || exit 1
  ) & pid_ruff_chain=$!

  # Chain 2: YAML formatting → linting
  (
    run_yamlfmt > "$TEMP_DIR/yamlfmt.out" 2>&1 || exit 1
    run_yamllint > "$TEMP_DIR/yamllint.out" 2>&1 || exit 1
  ) & pid_yaml_chain=$!

  # Chain 3: Manifest formatting → validation
  run_manifest > "$TEMP_DIR/manifest.out" 2>&1 & pid_manifest=$!

  # Independent operations
  run_mypy > "$TEMP_DIR/mypy.out" 2>&1 & pid_mypy=$!
  run_shellcheck > "$TEMP_DIR/shellcheck.out" 2>&1 & pid_shellcheck=$!
  run_trailing_whitespace > "$TEMP_DIR/whitespace.out" 2>&1 & pid_whitespace=$!
  run_nodejs_lint "express" > "$TEMP_DIR/express.out" 2>&1 & pid_express=$!
  run_nodejs_lint "fastify" > "$TEMP_DIR/fastify.out" 2>&1 & pid_fastify=$!

  # Display outputs progressively as operations complete
  FAILED=0

  wait_and_display "$pid_mypy" "$TEMP_DIR/mypy.out" "mypy" || FAILED=1
  wait_and_display "$pid_ruff_chain" "$TEMP_DIR/ruff_fmt.out" "ruff format + check" || FAILED=1
  cat "$TEMP_DIR/ruff_check.out"  # Show ruff check output (part of chain)
  wait_and_display "$pid_whitespace" "$TEMP_DIR/whitespace.out" "trailing whitespace" || FAILED=1
  wait_and_display "$pid_yaml_chain" "$TEMP_DIR/yamlfmt.out" "yamlfmt + yamllint" || FAILED=1
  cat "$TEMP_DIR/yamllint.out"  # Show yamllint output (part of chain)
  wait_and_display "$pid_manifest" "$TEMP_DIR/manifest.out" "manifest" || FAILED=1
  wait_and_display "$pid_shellcheck" "$TEMP_DIR/shellcheck.out" "shellcheck" || FAILED=1
  echo "Running Node.js linters"
  wait_and_display "$pid_express" "$TEMP_DIR/express.out" "express lint" || FAILED=1
  wait_and_display "$pid_fastify" "$TEMP_DIR/fastify.out" "fastify lint" || FAILED=1

  if [ "$FAILED" -eq 1 ]; then
    exit 1
  fi
fi

echo "All good, the system-tests CI will be happy! ✨ 🍰 ✨"
