#!/bin/bash

set -eu

git_clone(){
    url_to_clone=$1
    branch_to_clone=$2
    git clone --branch "$branch_to_clone" "$url_to_clone" /binaries/dd-trace-cpp
}

git_clone_latest_release (){
   url_to_clone="https://github.com/DataDog/dd-trace-cpp"
   latest_release=$(curl -s  https://api.github.com/repos/DataDog/dd-trace-cpp/releases/latest | jq '.tag_name'| tr -d '"')
   echo "$latest_release" > SYSTEM_TESTS_LIBRARY_VERSION
   git_clone "$url_to_clone" "$latest_release"    
}

get_version_from_binaries() {
    # shellcheck disable=SC2002
    version_line=$(cat /binaries/dd-trace-cpp/src/datadog/version.cpp | grep '^#define VERSION *')
    current_version=$(echo "$version_line" |  awk -F'VERSION' '{ print $2 }')
    echo "$current_version" | tr -d '"'> SYSTEM_TESTS_LIBRARY_VERSION
}

configure_cmake_to_fetch_from_dir() {
    sed -i 's@GIT_REPOSITORY@SOURCE_DIR "/binaries/dd-trace-cpp" #GIT_REPOSITORY@g' /usr/app/CMakeLists.txt
    sed -i "s/GIT_TAG/#GIT_TAG/g" /usr/app/CMakeLists.txt
    sed -i "s/GIT_SHALLOW/#GIT_SHALLOW/g" /usr/app/CMakeLists.txt
    sed -i "s/GIT_PROGRESS/#GIT_PROGRESS/g" /usr/app/CMakeLists.txt
}


cd /usr/app

if [ -e /binaries/cpp-load-from-git ]; then
    echo "install from file cpp-load-from-git"
    target=$(cat /binaries/cpp-load-from-git) 
    url=$(echo "$target" | cut -d "@" -f 1)
    branch=$(echo "$target" | cut -d "@" -f 2)
    #Clone from git, get version from file version.cpp and configure make to use binaries/dd-trace-cpp folder
    git_clone "$url" "$branch"
    get_version_from_binaries
elif [ -e /binaries/dd-trace-cpp ]; then
    echo "install from local folder /binaries/dd-trace-cpp"
    get_version_from_binaries
else
    echo "install from latest tracer release"
    git_clone_latest_release
fi
configure_cmake_to_fetch_from_dir