#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

# Send changelog update to Slack
# Takes argument from env:
#   SLACK_WEBHOOK
#   CHANGELOG_PATH (optional, defaults to CHANGELOG.md)

set -eu

CHANGELOG_PATH=${CHANGELOG_PATH:-CHANGELOG.md}

if [ ! -f "$CHANGELOG_PATH" ]; then
    echo "Error: CHANGELOG.md not found at $CHANGELOG_PATH"
    exit 1
fi

if [ -z "${SLACK_WEBHOOK:-}" ]; then
    echo "Error: SLACK_WEBHOOK environment variable is not set"
    exit 1
fi

# Extract the latest changelog entry (first section after header)
# The format is: header (4 lines) then ### YYYY-MM section
# We want to get everything from the first ### until the next ### or end of file

# Read the changelog and extract the latest entry
LATEST_ENTRY=$(awk '
    BEGIN { in_entry = 0; entry_lines = "" }
    /^### [0-9]{4}-[0-9]{2}/ {
        if (in_entry) {
            exit
        }
        in_entry = 1
    }
    in_entry {
        entry_lines = entry_lines $0 "\n"
    }
    END {
        print entry_lines
    }
' "$CHANGELOG_PATH")

if [ -z "$LATEST_ENTRY" ]; then
    echo "Error: Could not extract latest changelog entry"
    exit 1
fi

# Create a temporary file for the JSON payload to avoid escaping issues
TEMP_FILE=$(mktemp)
trap 'rm -f "$TEMP_FILE"' EXIT

# Format the changelog entry for Slack
# Convert markdown header (###) to bold (*text*)
# Convert markdown links to Slack format: [text](url) -> <url|text>
# Replace leading asterisks with bullet points for Slack list formatting
# shellcheck disable=SC2001  # sed is appropriate for regex replacement
FORMATTED_ENTRY=$(echo "$LATEST_ENTRY" | sed 's/^### \(.*\)$/*\1*/' | sed 's/\[\([^]]*\)](\([^)]*\))/<\2|\1>/g' | sed 's/^\* /• /g')

# Build JSON payload using Python for proper escaping
# Pass the formatted entry as an environment variable to avoid shell escaping issues
# shellcheck disable=SC2016
FORMATTED_ENTRY="$FORMATTED_ENTRY" python3 << 'PYTHON_EOF' > "$TEMP_FILE"
import json
import os

formatted_entry = os.environ.get('FORMATTED_ENTRY', '')

message = {
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📋 Changelog Updated"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": formatted_entry
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "<https://github.com/DataDog/system-tests/blob/main/CHANGELOG.md|View full changelog>"
            }
        }
    ]
}

print(json.dumps(message))
PYTHON_EOF

curl -X POST -H 'Content-type: application/json' --data @"$TEMP_FILE" "$SLACK_WEBHOOK"
