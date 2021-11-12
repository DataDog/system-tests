#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# The purpose of this script is to download the latest development version of a component.
#
# Binaries sources:
# 
# * C++:    Circle CI      (needs auth)
# * .NET:   windows.net
# * Golang: github repo
# * Java:   Circle CI      (needs auth)
# * NodeJS: github repo
# * PHP:    Circle CI      (needs auth)
# * Python: github actions
# * Ruby:   github repo
#
##########################################################################################

set -eu

get_circleci_artifact() {

    SLUG=$1
    WORKFLOW_NAME=$2
    JOB_NAME=$3
    ARTIFACT_PATTERN=$4

    echo "CircleCI: https://app.circleci.com/pipelines/$SLUG?branch=master"
    PIPELINES=$(curl --silent https://circleci.com/api/v2/project/$SLUG/pipeline?branch=master -H "Circle-Token: $CIRCLECI_TOKEN")

    for i in {1..30}; do
        PIPELINE_ID=$(echo $PIPELINES| jq -r ".items[$i].id")
        PIPELINE_NUMBER=$(echo $PIPELINES | jq -r ".items[$i].number")

        echo "Trying pipeline #$i $PIPELINE_NUMBER/$PIPELINE_ID"
        WORKFLOWS=$(curl --silent https://circleci.com/api/v2/pipeline/$PIPELINE_ID/workflow -H "Circle-Token: $CIRCLECI_TOKEN")

        QUERY=".items[] | select(.name == \"$WORKFLOW_NAME\") | .id"
        WORKFLOW_IDS=$(echo $WORKFLOWS | jq -r "$QUERY")

        if [ ! -z "$WORKFLOW_IDS" ]; then

            for WORKFLOW_ID in $WORKFLOW_IDS; do
                echo "=> https://app.circleci.com/pipelines/$SLUG/$PIPELINE_NUMBER/workflows/$WORKFLOW_ID"

                JOBS=$(curl --silent https://circleci.com/api/v2/workflow/$WORKFLOW_ID/job -H "Circle-Token: $CIRCLECI_TOKEN")

                QUERY=".items[] | select(.name == \"$JOB_NAME\" and .status==\"success\")"
                JOB=$(echo $JOBS | jq "$QUERY")

                if [ ! -z "$JOB" ]; then
                    break
                fi
            done

            if [ ! -z "$JOB" ]; then
                break
            fi
        fi
    done

    if [ -z "$JOB" ]; then
        echo "Oooops, I did not found any successful pipeline"
        exit 1
    fi

    JOB_NUMBER=$(echo $JOB | jq -r ".job_number")
    JOB_ID=$(echo $JOB | jq -r ".id")

    echo "Job number/ID: $JOB_NUMBER/$JOB_ID"
    echo "Job URL: https://app.circleci.com/pipelines/$SLUG/$PIPELINE_NUMBER/workflows/$WORKFLOW_ID/jobs/$JOB_NUMBER"

    ARTIFACTS=$(curl --silent https://circleci.com/api/v2/project/$SLUG/$JOB_NUMBER/artifacts -H "Circle-Token: $CIRCLECI_TOKEN")
    QUERY=".items[] | select(.path | test(\"$ARTIFACT_PATTERN\"))"
    ARTIFACT_URL=$(echo $ARTIFACTS | jq -r "$QUERY | .url")
    ARTIFACT_NAME=$(echo $ARTIFACTS | jq -r "$QUERY | .path" | sed -E 's/libs\///')
    echo "Artifact URL: $ARTIFACT_URL"
    echo "Artifact name: $ARTIFACT_NAME"
    echo "Downloading artifact..."

    curl --silent -L $ARTIFACT_URL --output $ARTIFACT_NAME
}

if test -f ".env"; then
    source .env
fi

TARGET=$1
echo "Load binary for $TARGET"

cd binaries/

if [ "$TARGET" = "java" ]; then
    rm -rf *.jar
    OWNER=DataDog
    REPO=dd-trace-java

    get_circleci_artifact "gh/DataDog/dd-trace-java" "nightly" "build" "libs/dd-java-agent-.*-SNAPSHOT.jar"

elif [ "$TARGET" = "dotnet" ]; then
    rm -rf *.tar.gz

    SHA=$(curl --silent https://apmdotnetci.blob.core.windows.net/apm-dotnet-ci-artifacts-master/sha.txt)
    ARCHIVE=$(curl --silent https://apmdotnetci.blob.core.windows.net/apm-dotnet-ci-artifacts-master/index.txt | grep '^datadog-dotnet-apm-[0-9.]*\.tar\.gz$')
    URL=https://apmdotnetci.blob.core.windows.net/apm-dotnet-ci-artifacts-master/$SHA/$ARCHIVE

    echo "Load $URL"
    curl -L --silent $URL --output $ARCHIVE

elif [ "$TARGET" = "python" ]; then
    rm -rf *.whl

    OWNER=DataDog
    REPO=dd-trace-py

    # sudo apt-get install unzip
    # sudo apt-get install jq

    curl --silent "https://api.github.com/repos/$OWNER/$REPO/actions/workflows/build_deploy.yml/runs?branch=master&event=schedule&per_page=1" > workflows.json

    ARTIFACT_URL=$(jq -r '.workflow_runs[0].artifacts_url' workflows.json)
    echo "Load $ARTIFACT_URL" 
    curl --silent "$ARTIFACT_URL" > artifacts.json

    ARCHIVE_URL=$(jq -r '.artifacts[0].archive_download_url' artifacts.json)
    echo "Load $ARCHIVE_URL" 
    curl --silent -H "Authorization: token $GH_TOKEN" -L "$ARCHIVE_URL" --output artifacts.zip

    mkdir -p artifacts/
    unzip artifacts.zip -d artifacts/

    find artifacts/ -type f -name 'ddtrace-*-cp39-cp39-manylinux2010_x86_64.whl' -exec cp '{}' . ';'

    rm -rf artifacts artifacts.zip 

    jq '.workflow_runs[0].created_at' workflows.json
    jq '.workflow_runs[0].head_commit.id' workflows.json
    jq '.workflow_runs[0].head_commit.timestamp' workflows.json

elif [ "$TARGET" = "ruby" ]; then
    # echo 'ddtrace --git "https://github.com/Datadog/dd-trace-rb" --branch "master"' > ruby-load-from-bundle-add
    echo "gem 'ddtrace', require: 'ddtrace/auto_instrument', github: 'Datadog/dd-trace-rb', branch: 'appsec'" > ruby-load-from-bundle-add
    echo "Using $(cat ruby-load-from-bundle-add)"

elif [ "$TARGET" = "php" ]; then
    rm -rf *.apk
    get_circleci_artifact "gh/DataDog/dd-trace-php" "build_packages" "package extension" "datadog-php-tracer_.*-nightly_noarch.apk"

elif [ "$TARGET" = "golang" ]; then
    rm -rf golang-load-from-go-get

    # COMMIT_ID=$(curl -s 'https://api.github.com/repos/DataDog/dd-trace-go/commits' | jq -r .[0].sha)
    COMMIT_ID=$(curl -s 'https://api.github.com/repos/DataDog/dd-trace-go/branches/v1' | jq -r .commit.sha)

    echo "Using gopkg.in/DataDog/dd-trace-go.v1@$COMMIT_ID"
    echo "gopkg.in/DataDog/dd-trace-go.v1@$COMMIT_ID" > golang-load-from-go-get

elif [ "$TARGET" = "cpp" ]; then
    # get_circleci_artifact "gh/DataDog/dd-opentracing-cpp" "build_test_deploy" "build" "TBD"
    x=1

elif [ "$TARGET" = "agent" ]; then
    # ???
    x=1

elif [ "$TARGET" = "nodejs" ]; then
    # NPM builds the package, so we put a trigger file that tells install script to get package from github#master
    # echo "DataDog/dd-trace-js#master" > nodejs-load-from-npm
    echo "DataDog/dd-trace-js#vdeturckheim/iaw-bindings" > nodejs-load-from-npm

else
    echo "Unknown target: $1"
    exit 1
fi;
