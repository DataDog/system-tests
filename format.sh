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

echo "Running treefmt-nix ..."
if [ "$COMMAND" == "fix" ]; then
  nix fmt


else
  nix flake check
fi

if [ ! -d "venv/" ]; then
  echo "Runner is not installed, installing it (ETA 60s)"
  ./build.sh -i runner
fi

# shellcheck source=/dev/null 
source venv/bin/activate

pylint utils  # pylint does not have a fix mode

echo "All good, the system-tests CI will be happy! ✨ 🍰 ✨"