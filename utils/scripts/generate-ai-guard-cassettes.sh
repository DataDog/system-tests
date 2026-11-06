#!/usr/bin/env bash
set -eu

if [[ -z "${DD_API_KEY:-}" ]] || [[ -z "${DD_APP_KEY:-}" ]]; then
    echo "Error: DD_API_KEY and DD_APP_KEY environment variables are required"
    echo ""
    echo "Usage:"
    echo "  DD_API_KEY=<key> DD_APP_KEY=<key> $0 [options]"
    echo ""
    echo "Options are passed through to run.sh (e.g. -L java, -v, etc.)"
    exit 1
fi

if [[ ! " $* " =~ " -L " ]] && [[ ! " $* " =~ " --library " ]]; then
    set -- -L python "$@"
fi

echo "Generating AI Guard cassettes"
echo "⚠️  This will make real API calls to the AI Guard endpoint"
echo ""

CASSETTES_SRC="logs_ai_guard/recorded_cassettes/aiguard"
CASSETTES_DST="utils/build/docker/vcr/cassettes/aiguard"

./run.sh AI_GUARD \
    --generate-cassettes \
    "$@" \
    -v

echo ""

# Copy recorded cassettes to the cassettes directory
if [[ -d "$CASSETTES_SRC" ]] && ls "$CASSETTES_SRC"/*.json &>/dev/null; then
    cp "$CASSETTES_SRC"/*.json "$CASSETTES_DST/"
    echo "Cassettes copied to $CASSETTES_DST/"
    echo "Review the changes with 'git diff' and commit them if they look correct"
else
    echo "No cassettes were recorded in $CASSETTES_SRC"
    exit 1
fi
