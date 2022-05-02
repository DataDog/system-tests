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

    if [ -z "$ARTIFACT_URL" ]; then
        echo "Oooops, I did not found any artifact that satisfy this pattern: $ARTIFACT_PATTERN. Here is the list:"
        echo $ARTIFACTS | jq -r ".items[] | .path"
        exit 1
    fi

    ARTIFACT_NAME=$(echo $ARTIFACTS | jq -r "$QUERY | .path" | sed -E 's/libs\///')
    echo "Artifact URL: $ARTIFACT_URL"
    echo "Artifact name: $ARTIFACT_NAME"
    echo "Downloading artifact..."

    curl --silent -L $ARTIFACT_URL --output $ARTIFACT_NAME
}


get_github_action_artifact() {
    rm -rf artifacts artifacts.zip

    SLUG=$1
    WORKFLOW=$2
    BRANCH=$3
    PATTERN=$4

    # query filter seems not to be working ??
    WORKFLOWS=$(curl --silent -H "Authorization: token $GH_TOKEN" "https://api.github.com/repos/$SLUG/actions/workflows/$WORKFLOW/runs?per_page=100")

    QUERY="[.workflow_runs[] | select(.conclusion != \"failure\" and .head_branch == \"$BRANCH\" and .status == \"completed\")][0]"
    ARTIFACT_URL=$(echo $WORKFLOWS | jq -r "$QUERY | .artifacts_url")
    HTML_URL=$(echo $WORKFLOWS | jq -r "$QUERY | .html_url")
    echo "Load artifact $HTML_URL" 
    ARTIFACTS=$(curl --silent -H "Authorization: token $GH_TOKEN" $ARTIFACT_URL)

    ARCHIVE_URL=$(echo $ARTIFACTS | jq -r '.artifacts[0].archive_download_url')
    echo "Load archive $ARCHIVE_URL"

    curl -H "Authorization: token $GH_TOKEN" --output artifacts.zip -L $ARCHIVE_URL 

    mkdir -p artifacts/
    unzip artifacts.zip -d artifacts/

    find artifacts/ -type f -name $PATTERN -exec cp '{}' . ';'

    rm -rf artifacts artifacts.zip
}

fetch_latest_repo_commit_hashes() {
    REPO=${1:-"https://github.com/DataDog/datadog-agent"}
    BRANCH=${2:-"main"}
    NB_OF_REVS=${3:-100}
    TMP_DIR=$(mktemp -d)
    PWD=$(pwd)
    echo "working in $TMP_DIR" >&2
    cd "$TMP_DIR"
    git clone --depth "$NB_OF_REVS" --branch "$BRANCH" --single-branch "$REPO" ./repo
    cd repo
    git log -n 100 --pretty=format:"%H" main |
        xargs -I {} sh -c 'echo {} | head -c 8 ; echo'
    cd "$PWD"
    rm -rf "$TMP_DIR"
}

fetch_tags() {
    if [ -z "${GITLAB_CI-}" ]; then
        aws-vault exec build-stable-developer -- \
        aws ecr describe-images \
        --registry-id  486234852809 \
        --region us-east-1 \
        --repository-name ci/datadog-agent/agent \
        --page-size 200        
    else
        aws ecr describe-images \
        --registry-id  486234852809 \
        --region us-east-1 \
        --repository-name ci/datadog-agent/agent \
        --page-size 200
    fi
}

get_latest_agent_image_tag() {
    AGENT_REPO="$1"
    AGENT_BRANCH="$2"
    AGENT_FLAVOR="$3"

    echo "Fetching datadog-agent main branch commits" >&2
    latest_commits=$(fetch_latest_repo_commit_hashes "$AGENT_REPO" "$AGENT_BRANCH")

    echo "Fetching available image tags in ci repo" >&2
    available_images=$(
        fetch_tags |
        jq -r '.imageDetails[].imageTags[]' |
        sed -E 's/^v([0-9]+)(.*)$/\1 v\1\2/' |
        sort -nr |
        cut -d ' ' -f2 |
        while read -r image_tag; do
            image_flavor=$(echo $image_tag | sed -E 's/^v[0-9]+-([^-]+)-(.*)$/\2/')
            if [ "$image_flavor" = "$AGENT_FLAVOR" ]; then
                echo "$image_tag"
            fi
        done
    )

    latest_image=$(echo "$latest_commits" | while read -r commit; do
        latest_image=$(echo "$available_images" | while read -r image_tag; do
            image_commit=$(echo $image_tag | sed -E 's/^v[0-9]+-([^-]+)-(.*)$/\1/')
            image_flavor=$(echo $image_tag | sed -E 's/^v[0-9]+-([^-]+)-(.*)$/\2/')
            if [ $commit = $image_commit ]; then
                echo "Found latest image for main branch" >&2
                echo "$image_tag"
                break
            fi
        done)
        if [ ! -z "$latest_image" ]; then
            echo "$latest_image"
            break
        fi
    done)

    if [ -z "$latest_image" ]; then
        echo "Didn't find latest image for main branch" >&2
    else
        echo "$latest_image"
    fi
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

    get_circleci_artifact "gh/DataDog/dd-trace-java" "nightly" "build" "libs/dd-java-agent-.*(-SNAPSHOT)?.jar"

elif [ "$TARGET" = "dotnet" ]; then
    rm -rf *.tar.gz

    SHA=$(curl --silent https://apmdotnetci.blob.core.windows.net/apm-dotnet-ci-artifacts-master/sha.txt)
    ARCHIVE=$(curl --silent https://apmdotnetci.blob.core.windows.net/apm-dotnet-ci-artifacts-master/index.txt | grep '^datadog-dotnet-apm-[0-9.]*\.tar\.gz$')
    URL=https://apmdotnetci.blob.core.windows.net/apm-dotnet-ci-artifacts-master/$SHA/$ARCHIVE

    echo "Load $URL"
    curl -L --silent $URL --output $ARCHIVE

elif [ "$TARGET" = "python" ]; then
    echo "ddtrace @ git+https://github.com/DataDog/dd-trace-py.git" > python-load-from-pip

elif [ "$TARGET" = "ruby" ]; then
    echo "gem 'ddtrace', require: 'ddtrace/auto_instrument', git: 'https://github.com/Datadog/dd-trace-rb.git'" > ruby-load-from-bundle-add
    echo "Using $(cat ruby-load-from-bundle-add)"

elif [ "$TARGET" = "php" ]; then
    rm -rf *.tar.gz
    get_circleci_artifact "gh/DataDog/dd-trace-php" "build_packages" "package extension" "datadog-php-tracer-.*-nightly.x86_64.tar.gz"

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
    if [ -z "${GITLAB_CI-}" ]; then
        echo "Loging into build-stable ecr" >&2
        aws-vault exec build-stable-developer -- aws ecr get-login-password |
            docker login --username AWS --password-stdin 486234852809.dkr.ecr.us-east-1.amazonaws.com >&2
    else
        aws ecr get-login-password --region us-east-1 |
            docker login --username AWS --password-stdin 486234852809.dkr.ecr.us-east-1.amazonaws.com >&2
    fi

    image_tag=$(get_latest_agent_image_tag "https://github.com/Datadog/datadog-agent" "main" "7-amd64")
    image=486234852809.dkr.ecr.us-east-1.amazonaws.com/ci/datadog-agent/agent:"$image_tag"
    docker pull "$image"
    echo "$image" > agent-image

elif [ "$TARGET" = "nodejs" ]; then
    # NPM builds the package, so we put a trigger file that tells install script to get package from github#master
    echo "DataDog/dd-trace-js#master" > nodejs-load-from-npm

elif [ "$TARGET" = "waf_rule_set_v1" ]; then
    exit 1

elif [ "$TARGET" = "waf_rule_set_v2" ]; then
    curl --silent \
        -H "Authorization: token $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        --output "waf_rule_set.json" \
        https://api.github.com/repos/DataDog/appsec-event-rules/contents/build/recommended.json

elif [ "$TARGET" = "waf_rule_set" ]; then
    curl --silent \
        -H "Authorization: token $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        --output "waf_rule_set.json" \
        https://api.github.com/repos/DataDog/appsec-event-rules/contents/build/recommended.json

elif [ "$TARGET" = "php_appsec" ]; then
    get_github_action_artifact "DataDog/dd-appsec-php" "package.yml" "master" "dd-appsec-php-*-amd64.tar.gz"

else
    echo "Unknown target: $1"
    exit 1
fi;
