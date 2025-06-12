#!/bin/bash

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


##########################################################################################
# The purpose of this script is to download the latest development version of a component.
#
# Binaries sources:
#
# * Agent:      Docker hub datadog/agent-dev:master-py3
# * cpp_httpd:  Github action artifact
# * Golang:     github.com/DataDog/dd-trace-go/v2@main
# * .NET:       ghcr.io/datadog/dd-trace-dotnet
# * Java:       ghcr.io/datadog/dd-trace-java
# * PHP:        ghcr.io/datadog/dd-trace-php
# * Node.js:    Direct from github source
# * C++:        Direct from github source
# * Python:     Clone  locally the githu repo
# * Ruby:       Direct from github source
# * WAF:        Direct from github source, but not working, as this repo is now private
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

  if [[ -z "${TARGET_BRANCH:-}" ]]; then
    return 0
  fi

  echo "It is not possible to specify the '$TARGET_BRANCH' target branch for $TARGET library yet"

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
    PATTERN=$4

    # query filter seems not to be working ??
    WORKFLOWS=$(curl --silent --fail --show-error -H "Authorization: token $GH_TOKEN" "https://api.github.com/repos/$SLUG/actions/workflows/$WORKFLOW/runs?per_page=100")

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

get_github_release_asset() {
    SLUG=$1
    PATTERN=$2

    release=$(curl --silent --fail --show-error -H "Authorization: token $GH_TOKEN" "https://api.github.com/repos/$SLUG/releases/latest")

    name=$(echo $release | jq -r ".assets[].name | select(test(\"$PATTERN\"))")
    url=$(echo $release | jq -r ".assets[].browser_download_url | select(test(\"$PATTERN\"))")

    echo "Load $url"

    curl -H "Authorization: token $GH_TOKEN" --output $name -L $url
}

if test -f ".env"; then
    source .env
fi

TARGET=$1
VERSION=${2:-'dev'}

echo "Load $VERSION binary for $TARGET"

cd binaries/

if [ "$TARGET" = "java" ]; then
    assert_version_is_dev
    assert_target_branch_is_not_set
    ../utils/scripts/docker_base_image.sh ghcr.io/datadog/dd-trace-java/dd-trace-java:latest_snapshot .

elif [ "$TARGET" = "dotnet" ]; then
    assert_version_is_dev
    assert_target_branch_is_not_set
    rm -rf *.tar.gz
    ../utils/scripts/docker_base_image.sh ghcr.io/datadog/dd-trace-dotnet/dd-trace-dotnet:latest_snapshot .

elif [ "$TARGET" = "python" ]; then
    assert_version_is_dev

    TARGET_BRANCH="${TARGET_BRANCH:-main}"
    rm -rf dd-trace-py/
    # do not use `--depth 1`, setuptools_scm, does not like it
    git clone --branch $TARGET_BRANCH https://github.com/DataDog/dd-trace-py.git
    cd dd-trace-py
    echo "Checking out the ref"
    git log -1 --format=%H

elif [ "$TARGET" = "ruby" ]; then
    assert_version_is_dev

    TARGET_BRANCH="${TARGET_BRANCH:-master}"
    echo "gem 'datadog', require: 'datadog/auto_instrument', git: 'https://github.com/Datadog/dd-trace-rb.git', branch: '$TARGET_BRANCH'" > ruby-load-from-bundle-add
    echo "Using $(cat ruby-load-from-bundle-add)"

elif [ "$TARGET" = "php" ]; then
    rm -rf *.tar.gz
    if [ $VERSION = 'dev' ]; then
        ../utils/scripts/docker_base_image.sh ghcr.io/datadog/dd-trace-php/dd-library-php:latest_snapshot ./temp
    elif [ $VERSION = 'prod' ]; then
        ../utils/scripts/docker_base_image.sh ghcr.io/datadog/dd-trace-php/dd-library-php:latest ./temp
    else
        echo "Don't know how to load version $VERSION for $TARGET"
    fi
    assert_target_branch_is_not_set
    mv ./temp/dd-library-php*.tar.gz . && mv ./temp/datadog-setup.php . && rm -rf ./temp

elif [ "$TARGET" = "golang" ]; then
    assert_version_is_dev
    rm -rf golang-load-from-go-get
    set -o pipefail

    TARGET_BRANCH="${TARGET_BRANCH:-main}"
    echo "load last commit on $TARGET_BRANCH for DataDog/dd-trace-go"
    COMMIT_ID=$(curl -sS --fail "https://api.github.com/repos/DataDog/dd-trace-go/branches/$TARGET_BRANCH" | jq -r .commit.sha)

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

    echo "Using github.com/DataDog/orchestrion@main"
    echo "github.com/DataDog/orchestrion@main" > orchestrion-load-from-go-get

elif [ "$TARGET" = "cpp" ]; then
    assert_version_is_dev
    # get_circleci_artifact "gh/DataDog/dd-opentracing-cpp" "build_test_deploy" "build" "TBD"
    # PROFILER: The main version is stored in s3, though we can not access this in CI
    # Not handled for now for system-tests. this handles artifact for parametric
    TARGET_BRANCH="${TARGET_BRANCH:-main}"
    echo "https://github.com/DataDog/dd-trace-cpp@$TARGET_BRANCH" > cpp-load-from-git
    echo "Using $(cat cpp-load-from-git)"

elif [ "$TARGET" = "cpp_httpd" ]; then
    assert_version_is_dev
    get_github_action_artifact "DataDog/httpd-datadog" "dev.yml" "main" "mod_datadog.so"

elif [ "$TARGET" = "cpp_nginx" ]; then
    assert_version_is_dev
    echo "Nowhere to load cpp_nginx from"
    exit 1

elif [ "$TARGET" = "agent" ]; then
    assert_version_is_dev
    TARGET_BRANCH="${TARGET_BRANCH:-master-py3}"
    echo "datadog/agent-dev:$TARGET_BRANCH" > agent-image
    echo "Using $(cat agent-image) image"

elif [ "$TARGET" = "nodejs" ]; then
    assert_version_is_dev

    TARGET_BRANCH="${TARGET_BRANCH:-master}"
    # NPM builds the package, so we put a trigger file that tells install script to get package from github#master
    echo "DataDog/dd-trace-js#$TARGET_BRANCH" > nodejs-load-from-npm
    echo "Using $(cat nodejs-load-from-npm)"

elif [ "$TARGET" = "waf_rule_set_v1" ]; then
    exit 1

elif [ "$TARGET" = "waf_rule_set_v2" ]; then
    assert_version_is_dev
    assert_target_branch_is_not_set
    curl --silent \
        -H "Authorization: token $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        --output "waf_rule_set.json" \
        https://api.github.com/repos/DataDog/appsec-event-rules/contents/build/recommended.json

elif [ "$TARGET" = "waf_rule_set" ]; then
    assert_version_is_dev
    assert_target_branch_is_not_set
    curl --fail --output "waf_rule_set.json" \
        -H "Authorization: token $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        https://api.github.com/repos/DataDog/appsec-event-rules/contents/build/recommended.json

else
    echo "Unknown target: $1"
    exit 1
fi;
