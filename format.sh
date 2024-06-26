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

echo "Checking Python files..."
if [ "$COMMAND" == "fix" ]; then
  black .
else
  black --check --diff .
fi
pylint utils  # pylint does not have a fix mode

# not py, as it's handled by black
INCLUDE_EXTENSIONS=("*.md" "*.yml" "*.yaml" "*.sh" "*.cs" "*.Dockerfile" "*.java" "*.sql" "*.ts" "*.js" "*.php")
EXCLUDE_DIRS=("logs*" "*/node_modules/*" "./venv/*" "./manifests/*" "./utils/build/virtual_machine/*")

INCLUDE_ARGS=()
for ext in "${INCLUDE_EXTENSIONS[@]}"; do
  INCLUDE_ARGS+=(-name "$ext" -o)
done
unset 'INCLUDE_ARGS[${#INCLUDE_ARGS[@]}-1]'  # remove last -o

EXCLUDE_ARGS=()
for dir in "${EXCLUDE_DIRS[@]}"; do
  EXCLUDE_ARGS+=(-not -path "$dir")
done

echo "Checking tailing whitespaces..."
FILES=$(find . "${EXCLUDE_ARGS[@]}" \( "${INCLUDE_ARGS[@]}" \) -exec grep -l ' $' {} \;)
if [ "$COMMAND" == "fix" ]; then
  echo "$FILES" | xargs -I {} sed -i 's/  *$//g' '{}'
else
  if [ -n "$FILES" ]; then
    echo "Some tailing white spaces has been found, please fix them 💥 💔 💥"
    echo "$FILES"
    exit 1
  fi
fi

echo "All good, the system-tests CI will be happy! ✨ 🍰 ✨"