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
fi

source venv/bin/activate

echo "Running mypy type checks..."
if ! mypy --config pyproject.toml; then
  echo "Mypy type checks failed. Please fix the errors above. 💥 💔 💥"
  exit 1
fi

echo "Running ruff checks..."
if ! which ruff > /dev/null; then
  echo "ruff is not installed, installing it (ETA 5s)"
  ./build.sh -i runner > /dev/null
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
EXCLUDE_PATTERN='utils/build/virtual_machine'
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
if ! which yamlfmt > /dev/null; then
  echo "yamlfmt is not installed, installing it (ETA 60s)"
  go install github.com/google/yamlfmt/cmd/yamlfmt@v0.16.0
fi

echo "Running yamlfmt formatter..."
if [ "$COMMAND" == "fix" ]; then
  yamlfmt manifests/
else
  yamlfmt -lint manifests/
fi

echo "Running yamllint checks..."
if ! yamllint -s manifests/; then
  echo "yamllint checks failed. Please fix the errors above. 💥 💔 💥"
  exit 1
fi


echo "All good, the system-tests CI will be happy! ✨ 🍰 ✨"
