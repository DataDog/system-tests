#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# The purpose of this script is to download the latest development version of a component.
#
# Binaries sources:
#
# * Agent:         Docker hub datadog/agent-dev:master-py3
# * cpp_httpd:     Github action artifact
# * Golang:        github.com/DataDog/dd-trace-go/v2@main
# * .NET:          ghcr.io/datadog/dd-trace-dotnet
# * Java:          S3
# * PHP:           ghcr.io/datadog/dd-trace-php
# * Node.js:       Direct from github source
# * C++:           Direct from github source
# * Python:        Clone locally the github repo
# * Ruby:          Direct from github source
# * WAF:           Direct from github source, but not working, as this repo is now private
# * Python Lambda: Fetch from GitHub Actions artifact
# * Rust:          Clone locally the github repo
##########################################################################################

set -eu

assert_version_is_dev() {

  if [ $VERSION = 'dev' ]; then
    return 0
  fi

  echo "Don't know how to load version $VERSION for $TARGET"

  exit 1
}

assert_target_branch_is_not_set() {

  if [[ -z "${LIBRARY_TARGET_BRANCH:-}" ]]; then
    return 0
  fi

  echo "It is not possible to specify the '$LIBRARY_TARGET_BRANCH' target branch for $TARGET library yet"

  exit 1
}

get_circleci_artifact() {

    SLUG=$1
    WORKFLOW_NAME=$2
    JOB_NAME=$3
    ARTIFACT_PATTERN=$4

    echo "CircleCI: https://app.circleci.com/pipelines/$SLUG?branch=master"
    PIPELINES=$(curl --silent https://circleci.com/api/v2/project/$SLUG/pipeline?branch=master -H "Circle-Token: $CIRCLECI_TOKEN")

    for i in {0..30}; do
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
    ARTIFACT_NAME=$4
    PATTERN=$5

    # query filter seems not to be working ??
    WORKFLOWS=$(curl --silent --fail --show-error -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/repos/$SLUG/actions/workflows/$WORKFLOW/runs?per_page=100")

    QUERY="[.workflow_runs[] | select(.conclusion != \"failure\" and .head_branch == \"$BRANCH\" and .status == \"completed\")][0]"
    ARTIFACT_URL=$(echo $WORKFLOWS | jq -r "$QUERY | .artifacts_url")
    HTML_URL=$(echo $WORKFLOWS | jq -r "$QUERY | .html_url")
    echo "Load artifact $HTML_URL"
    ARTIFACTS=$(curl --silent -H "Authorization: token $GITHUB_TOKEN" $ARTIFACT_URL)
    ARCHIVE_URL=$(echo $ARTIFACTS | jq -r --arg ARTIFACT_NAME "$ARTIFACT_NAME" '.artifacts | map(select(.name | contains($ARTIFACT_NAME))) | .[0].archive_download_url')
    echo "Load archive $ARCHIVE_URL"

    curl -H "Authorization: token $GITHUB_TOKEN" --output artifacts.zip -L $ARCHIVE_URL

    mkdir -p artifacts/
    unzip artifacts.zip -d artifacts/

    find artifacts/ -type f -name "$PATTERN" -exec cp '{}' . ';'

    rm -rf artifacts artifacts.zip
}

get_github_release_asset() {
    SLUG=$1
    PATTERN=$2

    release=$(curl --silent --fail --show-error -H "Authorization: token $GITHUB_TOKEN" "https://api.github.com/repos/$SLUG/releases/latest")

    name=$(echo $release | jq -r ".assets[].name | select(test(\"$PATTERN\"))")
    url=$(echo $release | jq -r ".assets[].browser_download_url | select(test(\"$PATTERN\"))")

    echo "Load $url"

    curl -H "Authorization: token $GITHUB_TOKEN" --output $name -L $url
}

if test -f ".env"; then
    source .env
fi

TARGET=$1
VERSION=${2:-'dev'}

GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_AUTH_HEADER=()
if [ -n "$GITHUB_TOKEN" ]; then
  GITHUB_AUTH_HEADER=(-H "Authorization: Bearer $GITHUB_TOKEN")
fi

echo "Load $VERSION binary for $TARGET"

cd binaries/

if [ "$TARGET" = "java" ]; then
    assert_version_is_dev

    TARGET_BRANCH="${TARGET_BRANCH:-master}"

    curl --fail --location --silent --show-error --output dd-java-agent.jar "https://s3.us-east-1.amazonaws.com/dd-trace-java-builds/${TARGET_BRANCH}/dd-java-agent.jar"

elif [ "$TARGET" = "dotnet" ]; then
    assert_version_is_dev

    LIBRARY_TARGET_BRANCH="${LIBRARY_TARGET_BRANCH:-latest_snapshot}"
    # Normalize branch name for image tag: replace '/' with '_'
    NORMALIZED_BRANCH=$(echo "$LIBRARY_TARGET_BRANCH" | sed 's/\//_/g')

    rm -rf *.tar.gz
    if [ -n "$GITHUB_TOKEN" ]; then
        echo "Log to GHCR with token"
        echo "$GITHUB_TOKEN" | docker login ghcr.io --password-stdin -u "actor"  # username is ignored
    fi

    ../utils/scripts/docker_base_image.sh ghcr.io/datadog/dd-trace-dotnet/dd-trace-dotnet:${NORMALIZED_BRANCH} .

elif [ "$TARGET" = "python" ]; then
    assert_version_is_dev

    LIBRARY_TARGET_BRANCH="${LIBRARY_TARGET_BRANCH:-main}"
    get_github_action_artifact "DataDog/dd-trace-py" "build_deploy.yml" $LIBRARY_TARGET_BRANCH "wheels-cp313-manylinux_x86_64" "*.whl"
    get_github_action_artifact "DataDog/dd-trace-py" "build_deploy.yml" $LIBRARY_TARGET_BRANCH "wheels-cp312-manylinux_x86_64" "*.whl"
    get_github_action_artifact "DataDog/dd-trace-py" "build_deploy.yml" $LIBRARY_TARGET_BRANCH "wheels-cp311-manylinux_x86_64" "*.whl"

elif [ "$TARGET" = "ruby" ]; then
    assert_version_is_dev

    LIBRARY_TARGET_BRANCH="${LIBRARY_TARGET_BRANCH:-master}"
    echo "gem 'datadog', require: 'datadog/auto_instrument', git: 'https://github.com/Datadog/dd-trace-rb.git', branch: '$LIBRARY_TARGET_BRANCH'" > ruby-load-from-bundle-add
    echo "Using $(cat ruby-load-from-bundle-add)"

elif [ "$TARGET" = "php" ]; then
    rm -rf *.tar.gz
    mkdir -p temp
    if [ $VERSION = 'dev' ]; then
        URL="https://s3.us-east-1.amazonaws.com/dd-trace-php-builds/latest/datadog-setup.php"
        echo "Downloading datadog-setup.php from: $URL"
        curl --fail --location --silent --show-error --output ./temp/datadog-setup.php "$URL"
        echo "datadog-setup.php downloaded"

        VERSION_HASH=$(grep "define('RELEASE_VERSION'" ./temp/datadog-setup.php | sed -E "s/.*urlencode\('([^']+)'\).*/\1/")
        if [ -z "$VERSION_HASH" ]; then
            echo "Failed to extract VERSION_HASH from datadog-setup.php"
            exit 1
        fi

        VERSION_HASH_ENCODED=$(echo "$VERSION_HASH" | sed 's/+/%2B/g')

        URL="https://s3.us-east-1.amazonaws.com/dd-trace-php-builds/${VERSION_HASH_ENCODED}/dd-library-php-${VERSION_HASH_ENCODED}-x86_64-linux-gnu.tar.gz"
        echo "Downloading dd-library-php from: $URL"
        curl --fail --location --silent --show-error --output ./temp/dd-library-php-${VERSION_HASH}-x86_64-linux-gnu.tar.gz "$URL"
        echo "dd-library-php downloaded"
    elif [ $VERSION = 'prod' ]; then
        ../utils/scripts/docker_base_image.sh ghcr.io/datadog/dd-trace-php/dd-library-php:latest ./temp
    else
        echo "Don't know how to load version $VERSION for $TARGET"
    fi
    mv ./temp/dd-library-php*.tar.gz . && mv ./temp/datadog-setup.php . && rm -rf ./temp

elif [ "$TARGET" = "golang" ]; then
    assert_version_is_dev
    rm -rf golang-load-from-go-get
    set -o pipefail

    LIBRARY_TARGET_BRANCH="${LIBRARY_TARGET_BRANCH:-main}"
    echo "load last commit on $LIBRARY_TARGET_BRANCH for DataDog/dd-trace-go"
    COMMIT_ID=$(curl -sS --fail "${GITHUB_AUTH_HEADER[@]}" "https://api.github.com/repos/DataDog/dd-trace-go/branches/$LIBRARY_TARGET_BRANCH" | jq -r .commit.sha)

    echo "Using github.com/DataDog/dd-trace-go/v2@$COMMIT_ID"
    echo "github.com/DataDog/dd-trace-go/v2@$COMMIT_ID" > golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/database/sql/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/net/http/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/google.golang.org/grpc/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/99designs/gqlgen/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/gin-gonic/gin/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/graphql-go/graphql/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/graph-gophers/graphql-go/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/go-chi/chi.v5/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/IBM/sarama/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/labstack/echo.v4/v2@$COMMIT_ID" >> golang-load-from-go-get
    echo "github.com/DataDog/dd-trace-go/contrib/sirupsen/logrus/v2@$COMMIT_ID" >> golang-load-from-go-get

    echo "Using ghcr.io/datadog/dd-trace-go/service-extensions-callout:dev"
    echo "ghcr.io/datadog/dd-trace-go/service-extensions-callout:dev" > golang-service-extensions-callout-image

    echo "Using github.com/DataDog/orchestrion@latest"
    echo "github.com/DataDog/orchestrion@latest" > orchestrion-load-from-go-get

elif [ "$TARGET" = "cpp" ]; then
    assert_version_is_dev
    # get_circleci_artifact "gh/DataDog/dd-opentracing-cpp" "build_test_deploy" "build" "TBD"
    # PROFILER: The main version is stored in s3, though we can not access this in CI
    # Not handled for now for system-tests. this handles artifact for parametric
    LIBRARY_TARGET_BRANCH="${LIBRARY_TARGET_BRANCH:-main}"
    echo "https://github.com/DataDog/dd-trace-cpp@$LIBRARY_TARGET_BRANCH" > cpp-load-from-git
    echo "Using $(cat cpp-load-from-git)"

elif [ "$TARGET" = "cpp_httpd" ]; then
    assert_version_is_dev
    get_github_action_artifact "DataDog/httpd-datadog" "dev.yml" "main" "mod_datadog_artifact" "mod_datadog.so"

elif [ "$TARGET" = "cpp_nginx" ]; then
    assert_version_is_dev
    echo "Nowhere to load cpp_nginx from"
    exit 1

elif [ "$TARGET" = "agent" ]; then
    assert_version_is_dev
    AGENT_TARGET_BRANCH="${AGENT_TARGET_BRANCH:-master-py3}"
    echo "datadog/agent-dev:$AGENT_TARGET_BRANCH" > agent-image
    echo "Using $(cat agent-image) image"

elif [ "$TARGET" = "nodejs" ]; then
    assert_version_is_dev

    LIBRARY_TARGET_BRANCH="${LIBRARY_TARGET_BRANCH:-master}"
    # NPM builds the package, so we put a trigger file that tells install script to get package from github#master
    echo "DataDog/dd-trace-js#$LIBRARY_TARGET_BRANCH" > nodejs-load-from-npm
    echo "Using $(cat nodejs-load-from-npm)"

elif [ "$TARGET" = "rust" ]; then
    assert_version_is_dev

    LIBRARY_TARGET_BRANCH="${LIBRARY_TARGET_BRANCH:-main}"
    echo "$LIBRARY_TARGET_BRANCH" > rust-load-from-git
    echo "Using $(cat rust-load-from-git)"

elif [ "$TARGET" = "waf_rule_set_v1" ]; then
    exit 1

elif [ "$TARGET" = "waf_rule_set_v2" ]; then
    assert_version_is_dev
    assert_target_branch_is_not_set
    curl --silent \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        --output "waf_rule_set.json" \
        https://api.github.com/repos/DataDog/appsec-event-rules/contents/build/recommended.json

elif [ "$TARGET" = "waf_rule_set" ]; then
    assert_version_is_dev
    assert_target_branch_is_not_set
    curl --fail --output "waf_rule_set.json" \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        https://api.github.com/repos/DataDog/appsec-event-rules/contents/build/recommended.json
elif [ "$TARGET" = "python_lambda" ]; then
    assert_version_is_dev
    assert_target_branch_is_not_set

    get_github_action_artifact "DataDog/datadog-lambda-python" "build_layer.yml" "main" "datadog-lambda-python-3.13-amd64" "datadog_lambda_py-amd64-3.13.zip"
else
    echo "Unknown target: $1"
    exit 1
fi;
