#!/bin/bash
# shellcheck disable=SC2164
#Check the commit message to figure out if we are merging a PR.
#We extract the PR number and using GitHub API we check the PR labels.
#If the PR contains the label "build-buddies-images" we launch the build and push process

PR_PATTERN='#[0-9]+'

if [[ $CI_COMMIT_MESSAGE =~ ($PR_PATTERN) ]]; then
    PR_NUMBER=${BASH_REMATCH[1]:1}
    echo "Merged the PR number: [$PR_NUMBER]"; 
    #search for labels
    PR_DATA=$(curl -L \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/DataDog/system-tests/issues/$PR_NUMBER/labels");

    echo "We found PR labels: $PR_DATA"    

    is_build_buddies=$(echo "$PR_DATA" | jq -c '.[] | select(.name | contains("build-buddies-images"))');
    is_build_lib_injections_apps=$(echo "$PR_DATA" | jq -c '.[] | select(.name | contains("build-lib-injection-app-images"))');

    if [ -z "$is_build_buddies" ]
    then
        echo "The PR $PR_NUMBER doesn't contain the 'build-buddies-images' label "
    else
        echo "The PR $PR_NUMBER contains the 'build-buddies-images' label. Launching the images generation process "
        echo "$DOCKER_LOGIN_PASS" | docker login --username "$DOCKER_LOGIN" --password-stdin
        ./utils/build/build_tracer_buddies.sh --push
    fi


    if [ -z "$is_build_lib_injections_apps" ]
    then
        echo "The PR $PR_NUMBER doesn't contain the 'build-lib-injection-app-images' label "
    else
        echo "The PR $PR_NUMBER contains the 'build-lib-injection-app-images' label. Launching the images generation process "
        echo "$DOCKER_LOGIN_PASS" | docker login --username "$DOCKER_LOGIN" --password-stdin
        export DOCKER_IMAGE_WEBLOG_TAG="latest"

        echo "Building and pushing the lib-injection apps for java"
        export APP_DOCKER_IMAGE_REPO=ghcr.io/datadog/system-tests/dd-lib-java-init-test-app
        cd lib-injection/build/docker/java/dd-lib-java-init-test-app
        LIBRARY_INJECTION_TEST_APP_IMAGE=$APP_DOCKER_IMAGE_REPO:latest ./build.sh
        cd ../../../../..

        echo "Building and pushing the lib-injection apps for nodejs"
        export APP_DOCKER_IMAGE_REPO=ghcr.io/datadog/system-tests/sample-app
        cd lib-injection/build/docker/nodejs/sample-app
        LIBRARY_INJECTION_TEST_APP_IMAGE=$APP_DOCKER_IMAGE_REPO:latest ./build.sh
        cd ../../../../..

        echo "Building and pushing the lib-injection apps for python"
        export APP_DOCKER_IMAGE_REPO=ghcr.io/datadog/system-tests/dd-lib-python-init-test-django
        cd lib-injection/build/docker/python/dd-lib-python-init-test-django
        LIBRARY_INJECTION_TEST_APP_IMAGE=$APP_DOCKER_IMAGE_REPO:latest ./build.sh
        cd ../../../../..
    fi
else
    echo "The commit message $CI_COMMIT_MESSAGE doesn't contain the PR number."
fi