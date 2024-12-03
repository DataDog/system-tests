#!/bin/bash
# shellcheck disable=SC2164
#Check the commit message to figure out if we are merging a PR.
#We extract the PR number and using GitHub API we check the PR labels.
#If the PR contains the label "build-buddies-images" we launch the build and push process



        echo "The PR $PR_NUMBER contains the 'build-lib-injection-app-images' label. Launching the images generation process "
        echo "$GH_TOKEN" | docker login ghcr.io --username "publisher" --password-stdin
        ./lib-injection/build/build_lib_injection_images.sh
        echo "------------- The lib injection weblog images have been built and pushed ------------- "
