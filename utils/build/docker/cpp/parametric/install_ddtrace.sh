#!/bin/bash

set -eu

get_latest_release() {
    wget -qO- "https://api.github.com/repos/$1/releases/latest" | jq -r '.tag_name'
}


git_clone(){
    url_to_clone=$1
    branch_to_clone=$2
    git clone --branch $branch_to_clone $url_to_clone /binaries/dd-trace-cpp
}
get_version_from_binaries() {

    version_line=$(cat /binaries/dd-trace-cpp/src/datadog/version.cpp | grep '^#define VERSION *')
    current_version=$(echo $version_line |  awk -F'VERSION' '{ print $2 }')
    echo $current_version | tr -d '"'> SYSTEM_TESTS_LIBRARY_VERSION
    
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
    url=$(echo $target | cut -d "@" -f 1)
    branch=$(echo $target | cut -d "@" -f 2)
    #Clone from git, get version from file version.cpp and configure make to use binaries/dd-trace-cpp folder
    git_clone $url $branch
    get_version_from_binaries
    configure_cmake_to_fetch_from_dir
 
elif [ -e /binaries/dd-trace-cpp ]; then
    echo "install from local folder /binaries/dd-trace-cpp"
    get_version_from_binaries
    configure_cmake_to_fetch_from_dir

else
    echo "install from prod"
    target="v1.9.99"
    echo $target>SYSTEM_TESTS_LIBRARY_VERSION
fi

