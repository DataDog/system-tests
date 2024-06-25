#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


# Send a notif to slack
# Take argument from env:
#   TITLE
#   URL
#   GITHUB_REPOSITORY
#   GITHUB_SHA
#   GITHUB_REF
#   STATUS
#   SLACK_WEBHOOK

set -eu

BRANCH=${GITHUB_REF#refs/heads/}
TITLE=${TITLE:-System tests}
TEXT_MESSAGE="*<$URL|$TITLE>: $STATUS*\nRef: <https://github.com/$GITHUB_REPOSITORY/tree/$BRANCH|$BRANCH>, SHA: <https://github.com/$GITHUB_REPOSITORY/commit/$GITHUB_SHA|${GITHUB_SHA:0:7}>"

if [ "$STATUS" = "success" ]; then
    COLOR="#00FF00"
elif [ "$STATUS" = "failure" ]; then
    COLOR="#FF0000"
elif [ "$STATUS" = "cancelled" ]; then
    COLOR="#800080"
else
    COLOR="#888888"
fi

MESSAGE="{
    \"attachments\": [
        {
            \"color\": \"$COLOR\",
	        \"blocks\": [{
                \"type\": \"section\",
                \"text\": {
                    \"type\": \"mrkdwn\",
                    \"text\": \"$TEXT_MESSAGE\"
                }
            }]
        }
    ]
}"

curl -X POST -H 'Content-type: application/json' --data "${MESSAGE}" $SLACK_WEBHOOK
